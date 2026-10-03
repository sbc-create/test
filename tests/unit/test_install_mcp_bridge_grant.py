"""Исполнение установщика канала MCP в изолированном окружении.

Зачем исполнение, а не `bash -n`. Первый запуск установщика у владельца упал на
строке `КОРЕНЬ="/home/claude/..."` с `No such file or directory` (rc=127):
кириллическое имя не является идентификатором bash, поэтому строка разбирается
как ЗАПУСК КОМАНДЫ. Конструкция синтаксически законна — `bash -n` её
пропускает. Такой дефект ловится только исполнением.

Здесь скрипт исполняется целиком в песочнице: пути перенаправлены в временный
каталог, привилегированные команды (`systemctl`, `useradd`, `passwd`, `sshd`,
`curl`, `id`) подставные, а всё, что составляет суть установщика —
`grep`, `install`, `cp`, `ssh-keygen`, запись файлов, heredoc, резервные копии —
работает по-настоящему.

Проверяются три прохода: первая установка, повтор (идемпотентность и сохранение
чужих ключей) и отказ `sshd -t` (возврат конфигурации без перезагрузки службы).
"""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import textwrap

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
УСТАНОВЩИК = КОРЕНЬ / "automation" / "host" / "install-mcp-bridge-grant.sh"

ТЕЛО_КЛЮЧА = "AAAAC3NzaC1lZDI1NTE5AAAAIBdXYS9HsyXBfoYfC1fSpJGYkhQq2ap8y2Zcx+gXZ9AR"
ОЖИДАЕМАЯ_СТРОКА = (
    'restrict,port-forwarding,permitopen="127.0.0.1:9000",command="/bin/false" '
    f"ssh-ed25519 {ТЕЛО_КЛЮЧА} site-factory-bridge@srv-qwen"
)
#: Ответ подставного curl на system_readiness: источник и непустой реестр.
ОТВЕТ_РЕЕСТРА = (
    '{"jsonrpc":"2.0","id":1,"result":{"content":[{"type":"text","text":'
    '"{\\"registry\\": {\\"valid\\": true, \\"sites\\": 23, '
    '\\"sites_digest\\": \\"4511cf3add1b3e88\\"}, '
    '\\"sources\\": {\\"site_cells\\": {\\"path\\": \\"config/site-cells.json\\"}}}"}]}}'
)

ЗАГЛУШКИ = {
    # `id -u` без аргумента — проверка root; с аргументом — существование
    # учётной записи, которое отмечает подставной useradd.
    "id": """
        if [ "${1:-}" = -u ] && [ -z "${2:-}" ]; then echo 0; exit 0; fi
        if [ "${1:-}" = -u ] && [ -n "${2:-}" ]; then
          [ -f "$SB_STATE/account" ] && { echo 4242; exit 0; } || exit 1
        fi
        exit 0
    """,
    "useradd": """
        echo "useradd $*" >> "$SB_STATE/calls.log"
        while [ $# -gt 0 ]; do
          [ "$1" = --home-dir ] && mkdir -p "$2"
          shift
        done
        : > "$SB_STATE/account"
    """,
    "passwd": 'echo "passwd $*" >> "$SB_STATE/calls.log"',
    "systemctl": """
        echo "systemctl $*" >> "$SB_STATE/calls.log"
        case "${1:-}" in
          is-active)  echo active ;;
          is-enabled) echo enabled ;;
        esac
    """,
    # Отказ конфигурации включается файлом-признаком: так проверяется ветка
    # возврата из резервной копии.
    "sshd": """
        echo "sshd $*" >> "$SB_STATE/calls.log"
        if [ -f "$SB_STATE/sshd-fail" ]; then
          echo "/etc/ssh/sshd_config.d/20-site-factory-bridge.conf: Bad configuration option" >&2
          exit 1
        fi
    """,
    "curl": """
        echo "curl $*" >> "$SB_STATE/calls.log"
        case "$*" in
          *healthz*) echo '{"ready": true, "read_only": true}' ;;
          *)         cat "$SB_STATE/registry.json" ;;
        esac
    """,
    # Настоящий install, но без смены владельца: в песочнице нет root.
    "install": """
        args=()
        while [ $# -gt 0 ]; do
          case "$1" in
            -o|-g) shift 2 ;;
            *) args+=("$1"); shift ;;
          esac
        done
        exec /usr/bin/install "${args[@]}"
    """,
}


def _заглушки(каталог: pathlib.Path, состояние: pathlib.Path) -> None:
    каталог.mkdir(parents=True, exist_ok=True)
    for имя, тело in ЗАГЛУШКИ.items():
        путь = каталог / имя
        путь.write_text(
            "#!/usr/bin/env bash\n"
            f'SB_STATE="{состояние}"\n'
            + textwrap.dedent(тело).strip()
            + "\n",
            encoding="utf-8",
        )
        путь.chmod(0o755)


def _песочница(tmp_path: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path, dict]:
    """Копия установщика с перенаправленными путями + подставной PATH."""
    корень_фс = tmp_path / "root"
    состояние = tmp_path / "state"
    (корень_фс / "etc" / "systemd" / "system").mkdir(parents=True)
    (корень_фс / "etc" / "ssh" / "sshd_config.d").mkdir(parents=True)
    (корень_фс / "var" / "lib").mkdir(parents=True)
    состояние.mkdir()
    (состояние / "registry.json").write_text(ОТВЕТ_РЕЕСТРА, encoding="utf-8")
    (состояние / "calls.log").write_text("", encoding="utf-8")

    # Настоящий ключ хоста: его отпечаток скрипт печатает для known_hosts.
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "sandbox",
         "-f", str(корень_фс / "etc" / "ssh" / "ssh_host_ed25519_key")],
        check=True,
    )

    текст = УСТАНОВЩИК.read_text(encoding="utf-8")
    замены = {
        '"/etc/systemd/system/': f'"{корень_фс}/etc/systemd/system/',
        '"/etc/ssh/sshd_config.d/': f'"{корень_фс}/etc/ssh/sshd_config.d/',
        '"/var/lib/site-factory-bridge"': f'"{корень_фс}/var/lib/site-factory-bridge"',
        " /etc/ssh/ssh_host_ed25519_key.pub": f" {корень_фс}/etc/ssh/ssh_host_ed25519_key.pub",
        " /etc/ssh/ssh_host_ecdsa_key.pub": f" {корень_фс}/etc/ssh/ssh_host_ecdsa_key.pub",
    }
    for что, на_что in замены.items():
        assert что in текст, f"установщик изменил форму: не найдено {что!r}"
        текст = текст.replace(что, на_что)

    копия = tmp_path / "install.sh"
    копия.write_text(текст, encoding="utf-8")

    _заглушки(tmp_path / "bin", состояние)
    окружение = dict(os.environ)
    окружение["PATH"] = f"{tmp_path / 'bin'}:{окружение['PATH']}"
    окружение["TMPDIR"] = str(tmp_path / "tmp")
    (tmp_path / "tmp").mkdir()
    return копия, корень_фс, окружение


def _запуск(копия, окружение):
    return subprocess.run(
        ["bash", str(копия)], capture_output=True, text=True,
        env=окружение, cwd=str(копия.parent), timeout=180,
    )


@pytest.fixture()
def песочница(tmp_path):
    if not shutil.which("ssh-keygen"):
        pytest.skip("нет ssh-keygen")
    return _песочница(tmp_path)


def test_установщик_исполняется_а_не_падает_на_разборе_имён(песочница):
    """Дефект, сломавший первый запуск: имя переменной не ASCII."""
    копия, корень_фс, окружение = песочница
    итог = _запуск(копия, окружение)
    вывод = итог.stdout + итог.stderr
    assert итог.returncode == 0, вывод
    # Ровно те сообщения bash, которыми проявляется не-ASCII идентификатор.
    for признак in ("No such file or directory", "bad substitution",
                    "not a valid identifier", "command not found"):
        assert признак not in вывод, f"установщик снова ломается: {признак}\n{вывод}"
    assert "готово" in вывод


def test_первый_проход_создаёт_строку_ключа_с_port_forwarding(песочница):
    копия, корень_фс, окружение = песочница
    итог = _запуск(копия, окружение)
    assert итог.returncode == 0, итог.stdout + итог.stderr
    список = корень_фс / "var" / "lib" / "site-factory-bridge" / ".ssh" / "authorized_keys"
    строки = [с for с in список.read_text(encoding="utf-8").splitlines() if с.strip()]
    assert строки == [ОЖИДАЕМАЯ_СТРОКА], строки


def test_первый_проход_пишет_блок_match_и_проверяет_его_до_перезагрузки(песочница):
    копия, корень_фс, окружение = песочница
    итог = _запуск(копия, окружение)
    assert итог.returncode == 0, итог.stdout + итог.stderr
    фрагмент = (корень_фс / "etc" / "ssh" / "sshd_config.d"
                / "20-site-factory-bridge.conf").read_text(encoding="utf-8")
    for директива in ("Match User sfbridge", "AllowTcpForwarding local",
                      "PermitOpen 127.0.0.1:9000", "PermitListen none",
                      "PermitTTY no", "X11Forwarding no",
                      "AllowAgentForwarding no", "PermitTunnel no",
                      "AllowStreamLocalForwarding no"):
        assert директива in фрагмент, фрагмент
    вызовы = (копия.parent / "state" / "calls.log").read_text(encoding="utf-8").splitlines()
    проверка = next(i for i, с in enumerate(вызовы) if с.startswith("sshd -t"))
    # Именно перезагрузка sshd, а не `daemon-reload` службы моста.
    перезагрузка = next(i for i, с in enumerate(вызовы) if с.startswith("systemctl reload"))
    assert проверка < перезагрузка, вызовы


def test_повтор_не_дублирует_ключ_и_сохраняет_чужие(песочница):
    копия, корень_фс, окружение = песочница
    assert _запуск(копия, окружение).returncode == 0
    список = корень_фс / "var" / "lib" / "site-factory-bridge" / ".ssh" / "authorized_keys"
    # Чужой ключ и УСТАРЕВШАЯ редакция нашего — без port-forwarding.
    список.write_text(
        "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIChuzhoyKLYUCHA= someone@elsewhere\n"
        f'restrict,permitopen="127.0.0.1:9000" ssh-ed25519 {ТЕЛО_КЛЮЧА} site-factory-bridge@srv-qwen\n',
        encoding="utf-8",
    )
    итог = _запуск(копия, окружение)
    assert итог.returncode == 0, итог.stdout + итог.stderr
    строки = [с for с in список.read_text(encoding="utf-8").splitlines() if с.strip()]
    assert sum(ТЕЛО_КЛЮЧА in с for с in строки) == 1, строки
    assert ОЖИДАЕМАЯ_СТРОКА in строки, строки
    assert any("someone@elsewhere" in с for с in строки), строки
    копии = list((корень_фс / "var" / "lib" / "site-factory-bridge" / ".ssh").glob("authorized_keys.bak.*"))
    assert копии, "нет резервной копии списка ключей"


def test_отказ_sshd_возвращает_конфигурацию_и_не_перезагружает_службу(песочница):
    копия, корень_фс, окружение = песочница
    assert _запуск(копия, окружение).returncode == 0
    фрагмент = (корень_фс / "etc" / "ssh" / "sshd_config.d"
                / "20-site-factory-bridge.conf")
    было = фрагмент.read_text(encoding="utf-8")
    состояние = копия.parent / "state"
    (состояние / "sshd-fail").touch()
    (состояние / "calls.log").write_text("", encoding="utf-8")

    итог = _запуск(копия, окружение)
    assert итог.returncode != 0
    assert "sshd -t не прошёл" in итог.stdout + итог.stderr
    assert фрагмент.read_text(encoding="utf-8") == было, "конфигурация не возвращена"
    вызовы = (состояние / "calls.log").read_text(encoding="utf-8")
    assert "systemctl reload" not in вызовы, \
        f"служба перезагружена при неверной конфигурации: {вызовы}"
    # Резервная копия израсходована возвратом, дубликата рядом не осталось.
    assert not list((корень_фс / "etc" / "ssh" / "sshd_config.d").glob("*.bak.*"))
