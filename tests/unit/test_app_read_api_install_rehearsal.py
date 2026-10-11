"""Репетиция установки целиком: фактический результат, а не план.

Зачем отдельно от остальных проверок установщика. Сухой прогон показывает ПЛАН:
он не создаёт файлов и поэтому не ловит ни ошибок записи, ни прав, ни поведения
при повторном запуске. Боевой прогон требует root, systemd и nginx. Здесь копия
сценария получает временные пути вместо боевых, а `systemctl`, `nginx`, `curl`,
`su` и `id` подменяются заглушками в PATH — и проверяется ФАКТ: какие файлы
появились, с какими правами, что делает повторный запуск, что делает поворот
ключа и что делает откат.

Повод. Установка 2026-10-11 остановилась на проверке доступа к ключу, оставив
хост в частичном состоянии: ключ создан, служба и маршрут — нет. Владелец
спросил прямо, безопасен ли повторный запуск. Ответ обязан быть измерен.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
СЦЕНАРИЙ = КОРЕНЬ / "automation" / "host" / "install-app-read-api.sh"

#: Раскладка конфигурации витрины — та же, что на боевом хосте: два серверных
#: блока, пять location, HTTPS объявлен вторым.
КОНФИГ_ВИТРИНЫ = """upstream cell_animedia_01 { server 127.0.0.1:9121; }

server {
    listen 80;
    server_name animedia.icu www.animedia.icu;

    location ^~ /.well-known/acme-challenge/ { root /var/www/html; }
    location / { proxy_pass http://cell_animedia_01; }
    location = /healthz { proxy_pass http://cell_animedia_01/healthz; }
}

server {
    listen 443 ssl;
    server_name animedia.icu;

    add_header X-Robots-Tag $cell_robots_animedia_01 always;

    location / { proxy_pass http://cell_animedia_01; }
    location = /healthz { proxy_pass http://cell_animedia_01/healthz; }
}
"""

ЗАГЛУШКИ = {
    "systemctl": '#!/bin/sh\necho "systemctl $*" >> "$REHEARSAL_LOG"\nexit 0\n',
    "nginx": '#!/bin/sh\necho "nginx $*" >> "$REHEARSAL_LOG"\nexit 0\n',
    "curl": '#!/bin/sh\necho "curl $*" >> "$REHEARSAL_LOG"\nexit 0\n',
    # Проверка «читает ли учётная запись службы» должна ИСПОЛНИТЬСЯ, иначе
    # репетиция не проверяет доступ вовсе.
    "su": ('#!/bin/sh\necho "su $*" >> "$REHEARSAL_LOG"\n'
           'while [ $# -gt 0 ]; do case "$1" in -c) shift; exec sh -c "$1" ;; '
           'esac; shift; done\nexit 0\n'),
    # Все пути — в песочнице, поэтому сценарию отвечаем как root: иначе
    # проверялась бы застава «нужен root», а не сама установка.
    "id": ('#!/bin/sh\ncase "$1" in -u) echo 0 ;; -un) echo root ;; '
           '*) /usr/bin/id "$@" ;; esac\n'),
}


class Песочница:
    def __init__(self, корень: Path) -> None:
        self.корень = корень
        self.пути = {
            "KEY_DIR": корень / "etc/app-read-api",
            "KEY_FILE": корень / "etc/app-read-api/client-key",
            "ROTATION_LOG": корень / "etc/app-read-api/rotations.log",
            "INSTALL_DIR": корень / "usr/local/lib/site-factory",
            "UNIT_PATH": корень / "etc/systemd/system/app-read-api-animedia-01.service",
            "SNIPPET": корень / "etc/nginx/snippets/app-read-api-animedia-01.conf",
            "SITE_CONF": корень / "etc/nginx/lords/animedia-01.conf",
            "UPSTREAM_CONF": корень / "etc/nginx/conf.d/cells.conf",
            "LEAKED_KEY_FILE": корень / "etc/site-factory/secrets/app_client_key",
        }
        for имя in ("UNIT_PATH", "SNIPPET", "SITE_CONF", "UPSTREAM_CONF",
                    "LEAKED_KEY_FILE"):
            self.пути[имя].parent.mkdir(parents=True, exist_ok=True)
        self.пути["SITE_CONF"].write_text(КОНФИГ_ВИТРИНЫ, encoding="utf-8")
        self.пути["UPSTREAM_CONF"].write_text(
            "upstream cell_animedia_01 { server 127.0.0.1:9121; }\n",
            encoding="utf-8")
        self.пути["LEAKED_KEY_FILE"].write_text("РАСКРЫТОЕ", encoding="utf-8")

        корзина = корень / "bin"
        корзина.mkdir(parents=True)
        self.журнал = корень / "команды.log"
        for имя, тело in ЗАГЛУШКИ.items():
            (корзина / имя).write_text(тело, encoding="utf-8")
            (корзина / имя).chmod(0o755)
        self.окружение = {**os.environ,
                          "PATH": f"{корзина}:{os.environ['PATH']}",
                          "REHEARSAL_LOG": str(self.журнал)}

        текст = СЦЕНАРИЙ.read_text(encoding="utf-8")
        for имя, значение in self.пути.items():
            текст = re.sub(rf'^{имя}="[^"]*"$', f'{имя}="{значение}"', текст,
                           count=1, flags=re.M)
        текст = текст.replace('KEY_FILE="${KEY_DIR}/client-key"',
                              f'KEY_FILE="{self.пути["KEY_FILE"]}"')
        текст = текст.replace('ROTATION_LOG="${KEY_DIR}/rotations.log"',
                              f'ROTATION_LOG="{self.пути["ROTATION_LOG"]}"')
        текст = текст.replace(
            'INSTALLED_SCRIPT="${INSTALL_DIR}/app-read-api-${SITE_ID}.py"',
            f'INSTALLED_SCRIPT="{self.пути["INSTALL_DIR"]}/app-read-api-animedia-01.py"')
        текст = текст.replace('UNIT_PATH="/etc/systemd/system/${UNIT}"',
                              f'UNIT_PATH="{self.пути["UNIT_PATH"]}"')
        текст = re.sub(r'SRC_ROOT="\$\(cd[^\n]+\n', f'SRC_ROOT="{КОРЕНЬ}"\n',
                       текст, count=1)
        # Смена владельца без привилегий невозможна; проверяются ПРАВА, они и
        # были предметом отказа.
        for убрать in (" -o root -g root", ' -o root -g "$RUN_USER"'):
            текст = текст.replace(убрать, "")
        текст = текст.replace('chown "root:${RUN_USER}" "$KEY_FILE"', "true")
        текст = текст.replace('chown "root:${RUN_USER}" "$ROTATION_LOG"', "true")
        self.сценарий = корень / "install.sh"
        self.сценарий.write_text(текст, encoding="utf-8")

    def прогон(self, *аргументы: str) -> tuple[int, str]:
        р = subprocess.run(["bash", str(self.сценарий), *аргументы],
                           env=self.окружение, capture_output=True, text=True,
                           cwd=str(КОРЕНЬ), timeout=600)
        return р.returncode, re.sub(r"\033\[[0-9;]*m", "", р.stdout + р.stderr)

    def права(self, имя: str) -> int | None:
        try:
            return self.пути[имя].lstat().st_mode & 0o777
        except OSError:
            return None

    def конфиг(self) -> str:
        return self.пути["SITE_CONF"].read_text(encoding="utf-8")

    def копий_конфигурации(self) -> int:
        return len(list(self.пути["SITE_CONF"].parent.glob(
            "*before-app-read-api*")))


@pytest.fixture()
def частичная(tmp_path) -> Песочница:
    """Состояние боевого хоста после остановки 11.10: есть только ключ."""
    п = Песочница(tmp_path / "корень")
    п.пути["KEY_DIR"].mkdir(parents=True)
    п.пути["KEY_FILE"].write_text("КЛЮЧ-ОТ-ЧАСТИЧНОЙ-УСТАНОВКИ", encoding="utf-8")
    п.пути["KEY_FILE"].chmod(0o640)
    return п


def test_повторный_запуск_доделывает_установку(частичная):
    был_ключ = частичная.пути["KEY_FILE"].read_text(encoding="utf-8")
    код, вывод = частичная.прогон()
    assert код == 0, вывод
    assert частичная.пути["UNIT_PATH"].is_file(), "юнит не записан"
    assert частичная.пути["SNIPPET"].is_file(), "сниппет не записан"
    assert (частичная.пути["INSTALL_DIR"] / "app-read-api-animedia-01.py").is_file()
    assert частичная.конфиг().count("app-read-api-animedia-01") == 1
    assert частичная.копий_конфигурации() == 1, "копия конфигурации не снята"
    assert частичная.пути["KEY_FILE"].read_text(encoding="utf-8") == был_ключ, (
        "существующий ключ перезаписан без флага поворота")


def test_маршруты_витрины_не_меняются(частичная):
    было = частичная.конфиг()
    частичная.прогон()
    стало = частичная.конфиг()
    assert стало.count("location ") == было.count("location ")
    assert all(с in стало.splitlines() for с in было.splitlines()), "строка исчезла"
    assert стало.count("{") == стало.count("}")


def test_третий_запуск_ничего_не_удваивает(частичная):
    частичная.прогон()
    код, вывод = частичная.прогон()
    assert код == 0, вывод
    assert "include уже стоял" in вывод or "include уже стоит" in вывод
    assert частичная.конфиг().count("app-read-api-animedia-01") == 1
    assert частичная.копий_конфигурации() == 1, "повтор снял вторую копию"


def test_каталог_ключа_получает_проход_только_нужной_записи(частичная):
    частичная.прогон()
    assert частичная.права("KEY_DIR") == 0o710, oct(частичная.права("KEY_DIR"))
    assert частичная.права("KEY_FILE") == 0o640


def test_поворот_меняет_ключ_и_не_оставляет_копий(частичная):
    частичная.прогон()
    прежний = частичная.пути["KEY_FILE"].read_text(encoding="utf-8")
    код, вывод = частичная.прогон("--rotate-key")
    assert код == 0, вывод
    новый = частичная.пути["KEY_FILE"].read_text(encoding="utf-8")
    assert новый != прежний, "ключ не заменён"
    assert not list(частичная.пути["KEY_DIR"].glob("*before-rotate*")), (
        "копия раскрытого значения осталась на диске")
    журнал = частичная.пути["ROTATION_LOG"].read_text(encoding="utf-8")
    assert журнал.count("key-") == 1 and "rotated" in журнал
    assert новый.strip() not in журнал, "значение попало в журнал поворотов"
    assert "systemctl restart" in частичная.журнал.read_text(encoding="utf-8"), (
        "без перезапуска служба продолжит принимать прежний ключ")


def test_значение_ключа_не_появляется_в_выводе(частичная):
    частичная.прогон()
    _, вывод = частичная.прогон("--rotate-key")
    значение = частичная.пути["KEY_FILE"].read_text(encoding="utf-8").strip()
    assert значение not in вывод, "значение ключа напечатано"
    assert "sudo cat" in вывод, "не сказано, как получить значение для CI"


def test_раскрытый_прежний_ключ_назван_и_не_используется(частичная):
    _, вывод = частичная.прогон()
    assert "прежний файл ключа ещё на диске" in вывод
    assert "sudo rm -f" in вывод, "команда удаления не названа"
    юнит = частичная.пути["UNIT_PATH"].read_text(encoding="utf-8")
    assert str(частичная.пути["LEAKED_KEY_FILE"]) not in юнит, (
        "служба всё ещё читала бы раскрытый ключ")
    assert str(частичная.пути["KEY_FILE"]) in юнит


def test_откат_снимает_только_свои_изменения(частичная):
    частичная.прогон()
    код, вывод = частичная.прогон("--rollback")
    assert код == 0, вывод
    assert not частичная.пути["UNIT_PATH"].exists(), "юнит остался"
    assert not частичная.пути["SNIPPET"].exists(), "сниппет остался"
    assert частичная.конфиг().count("app-read-api-animedia-01") == 0
    assert частичная.конфиг().count("location ") == КОНФИГ_ВИТРИНЫ.count("location ")
    assert частичная.пути["KEY_FILE"].exists(), (
        "ключ снят откатом: это закрыло бы доступ приложению отдельным решением")


def test_установка_с_нуля_тоже_проходит(tmp_path):
    """Не только восстановление после частичной: чистый случай обязан работать."""
    п = Песочница(tmp_path / "корень")
    код, вывод = п.прогон()
    assert код == 0, вывод
    assert п.пути["KEY_FILE"].is_file(), "ключ не создан"
    assert п.права("KEY_DIR") == 0o710
    assert "key-created" in п.пути["ROTATION_LOG"].read_text(encoding="utf-8")
    значение = п.пути["KEY_FILE"].read_text(encoding="utf-8").strip()
    assert значение not in вывод, "значение нового ключа напечатано"
