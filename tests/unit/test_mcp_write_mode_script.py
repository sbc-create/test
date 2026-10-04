"""Команда владельца, открывающая Qwen штатную операцию, — исполнением.

Скрипт `automation/host/enable-mcp-write-mode.sh` снимает `--read-only` у
службы моста. Опасность у него одна и названа прямо: не откроет ли режим
записи дорогу к production-домену. Поэтому главное утверждение проверяется не
чтением, а запуском: с НАСТОЯЩИМ мостом в режиме записи попытка открыть домен
обязана быть отклонена предпроверкой, состояние домена — не измениться, а при
неудаче этой проверки скрипт обязан САМ вернуть режим только чтения.

Песочница: systemd и root подставные, пути врезки — во временном каталоге,
порт моста свой. Настоящие здесь мост, протокол, `curl`, `grep` и вся логика
скрипта — то есть всё, чем он решает.
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import socket
import subprocess
import sys
import textwrap
import time
import urllib.error
import urllib.request

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
СКРИПТ = КОРЕНЬ / "automation" / "host" / "enable-mcp-write-mode.sh"
ДОМЕН = "lordserials22.info"

ЗАГЛУШКИ = {
    "id": 'echo 0',
    "systemctl": """
        echo "systemctl $*" >> "$SB_STATE/calls.log"
        case "${1:-}" in
          is-active)        echo active ;;
          list-unit-files)  echo "site-factory-mcp.service enabled" ;;
        esac
    """,
}


def _свободный_порт() -> int:
    с = socket.socket()
    с.bind(("127.0.0.1", 0))
    порт = с.getsockname()[1]
    с.close()
    return порт


@pytest.fixture()
def площадка(tmp_path):
    if not shutil.which("curl"):
        pytest.skip("нет curl")
    порт = _свободный_порт()
    состояние = tmp_path / "state"
    состояние.mkdir()
    (состояние / "calls.log").write_text("", encoding="utf-8")

    корзина = tmp_path / "bin"
    корзина.mkdir()
    for имя, тело in ЗАГЛУШКИ.items():
        п = корзина / имя
        п.write_text("#!/usr/bin/env bash\n"
                     f'SB_STATE="{состояние}"\n'
                     + textwrap.dedent(тело).strip() + "\n", encoding="utf-8")
        п.chmod(0o755)

    текст = СКРИПТ.read_text(encoding="utf-8")
    замены = {
        'DROPIN_DIR="/etc/systemd/system/${UNIT}.d"':
            f'DROPIN_DIR="{tmp_path}/systemd/${{UNIT}}.d"',
        "http://127.0.0.1:9000": f"http://127.0.0.1:{порт}",
    }
    for что, на in замены.items():
        assert что in текст, f"скрипт изменил форму: нет {что!r}"
        текст = текст.replace(что, на)
    копия = tmp_path / "enable.sh"
    копия.write_text(текст, encoding="utf-8")

    # НАСТОЯЩИЙ мост в режиме записи: проверяется отказ операции, а не подмена.
    окр = dict(os.environ)
    окр.pop("QWEN_MCP_READ_ONLY", None)
    окр["PATH"] = f"{корзина}:{окр['PATH']}"
    служба = subprocess.Popen(
        [sys.executable, "-m", "factory.qwen.mcp", "--http", f"127.0.0.1:{порт}"],
        cwd=str(КОРЕНЬ), env=окр, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True)
    try:
        for _ in range(80):
            time.sleep(0.25)
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{порт}/healthz",
                                            timeout=5) as r:
                    json.loads(r.read().decode())
                break
            except (urllib.error.URLError, OSError):
                continue
        else:
            pytest.skip("мост не поднялся в песочнице")
        yield {"копия": копия, "окр": окр, "порт": порт, "состояние": состояние,
               "tmp": tmp_path}
    finally:
        служба.terminate()
        try:
            служба.wait(timeout=10)
        except subprocess.TimeoutExpired:
            служба.kill()


def _запуск(п, *аргументы):
    return subprocess.run(["bash", str(п["копия"]), *аргументы],
                          capture_output=True, text=True, env=п["окр"],
                          cwd=str(п["tmp"]), timeout=900)


def test_скрипт_доходит_до_конца_и_доказывает_отказ_открытия(площадка):
    итог = _запуск(площадка)
    вывод = итог.stdout + итог.stderr
    assert итог.returncode == 0, вывод
    # Шаг 3: пишущие инструменты объявлены.
    for имя in ("set_indexing_mode", "rollback_indexing", "analytics_readiness"):
        assert f"объявлен {имя}" in вывод, вывод
    # Шаг 4: главное — отказ наступил в предпроверке и назвал разрешение.
    assert "открытие отклонено предпроверкой" in вывод, вывод
    assert "файл состояния и журнал домена не изменились" in вывод, вывод
    assert "готово" in вывод
    # Врезка написана и заменяет ExecStart целиком, а не добавляет второй.
    врезка = next((площадка["tmp"] / "systemd").rglob("10-write-mode.conf"))
    тело = врезка.read_text(encoding="utf-8")
    assert "ExecStart=\n" in тело, тело
    assert "--read-only" not in тело, тело


def test_при_неудаче_проверки_скрипт_сам_возвращает_только_чтение(площадка, tmp_path):
    """Если открытие вдруг НЕ отклонено, режим записи оставлять нельзя.

    Проверяется поведение, а не комментарий: мост подменяется ответом
    «успех», и скрипт обязан удалить врезку и перезапустить службу.
    """
    текст = (площадка["копия"]).read_text(encoding="utf-8")
    # Подмена одного ответа: на set_indexing_mode приходит успех.
    подделка = tmp_path / "fake-curl"
    подделка.write_text(
        "#!/usr/bin/env bash\n"
        'if printf "%s" "$*" | grep -q set_indexing_mode; then\n'
        '  echo "{\\"jsonrpc\\":\\"2.0\\",\\"id\\":1,'
        '\\"result\\":{\\"content\\":[{\\"type\\":\\"text\\",'
        '\\"text\\":\\"{}\\"}]}}"\n'
        "  exit 0\n"
        "fi\n"
        'exec /usr/bin/curl "$@"\n', encoding="utf-8")
    подделка.chmod(0o755)
    (tmp_path / "bin2").mkdir(exist_ok=True)
    shutil.copy2(подделка, tmp_path / "bin2" / "curl")
    for имя in ("id", "systemctl"):
        shutil.copy2(tmp_path / "bin" / имя, tmp_path / "bin2" / имя)
    окр = dict(площадка["окр"])
    окр["PATH"] = f"{tmp_path / 'bin2'}:{окр['PATH']}"
    итог = subprocess.run(["bash", str(площадка["копия"])], capture_output=True,
                          text=True, env=окр, cwd=str(tmp_path), timeout=900)
    вывод = итог.stdout + итог.stderr
    assert итог.returncode != 0, вывод
    assert "режим только чтения возвращён" in вывод, вывод
    # Врезки не осталось: иначе служба поднялась бы пишущей после перезапуска.
    assert not list((tmp_path / "systemd").rglob("10-write-mode.conf")), (
        "врезка осталась после неудачной проверки")


def test_undo_удаляет_врезку(площадка):
    assert _запуск(площадка).returncode == 0
    врезки = list((площадка["tmp"] / "systemd").rglob("10-write-mode.conf"))
    assert врезки, "врезки нет — нечего отменять"
    итог = _запуск(площадка, "--undo")
    вывод = итог.stdout + итог.stderr
    # В песочнице служба подставная и остаётся пишущей, поэтому проверка
    # `read_only: true` падает — это честно: скрипт не принимает на слово, что
    # отмена сработала. Главное: врезка удалена ДО проверки.
    assert not list((площадка["tmp"] / "systemd").rglob("10-write-mode.conf")), вывод
