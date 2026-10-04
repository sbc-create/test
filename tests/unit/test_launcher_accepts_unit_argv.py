"""Лаунчер сайта обязан принимать ту командную строку, которую даёт юнит ячейки.

Повод. Юнит исполнителя всегда стартует ячейку как
`run.py --port <порт> --data-dir <каталог>`. Лаунчер zona-02 отдавал `sys.argv[1:]`
точке входа целиком, а та про `--data-dir` не знала: процесс падал на разборе
аргументов до первого запроса. Исполнитель видел «процесс не работает», честно
откатывал выпуск и записывал причину, которая ни на что не указывает; настоящая
лежала в системном журнале, куда у подающего заявку прав нет. Так ушли в откат
два выпуска подряд.

Здесь проверяется само свойство проверки: она ловит непринятый аргумент и НЕ
трогает всё остальное. Второе не менее важно первого — `player.json` в рабочую
копию не коммитится, и лаунчер, честно отказавший из-за его отсутствия, обязан
пройти пробу: иначе проверка блокировала бы исправные выпуски.
"""
from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

import pytest

from factory.cell import queue as q
from factory.cell import registry as реестр_ячеек

ЛАУНЧЕР_НЕ_РАЗБИРАЕТ = '''\
import os, sys
точка = os.path.join(os.path.dirname(os.path.abspath(__file__)), "entry.py")
os.execv(sys.executable, [sys.executable, точка, *sys.argv[1:]])
'''

ЛАУНЧЕР_РАЗБИРАЕТ = '''\
import argparse, os, sys
п = argparse.ArgumentParser()
п.add_argument("--port", type=int)
п.add_argument("--data-dir")
а = п.parse_args()
точка = os.path.join(os.path.dirname(os.path.abspath(__file__)), "entry.py")
os.execv(sys.executable, [sys.executable, точка, "--port", str(а.port)])
'''

ЛАУНЧЕР_НЕТ_ДАННЫХ = '''\
import argparse, sys
п = argparse.ArgumentParser()
п.add_argument("--port", type=int)
п.add_argument("--data-dir")
п.parse_args()
print("нет config/player.json: плеер без publisher_id не заработает", file=sys.stderr)
raise SystemExit(78)
'''

#: Лаунчер, который после разбора аргументов загружает снимок каталога. Так
#: ведёт себя любая настоящая витрина: измерено 927 МиБ на lords-01.
ЛАУНЧЕР_ТЯЖЁЛЫЙ = '''\
import argparse, os, pathlib, socketserver, http.server
п = argparse.ArgumentParser()
п.add_argument("--port", type=int)
п.add_argument("--data-dir")
а = п.parse_args()
метки = pathlib.Path(os.environ["МЕТКИ"])
(метки / "разобрал").write_text("1")
снимок = bytearray(600 * 1024 * 1024)      # «каталог» в памяти
for i in range(0, len(снимок), 4096):      # касаемся страниц: память реальна
    снимок[i] = 120
(метки / "загрузил").write_text(str(len(снимок)))
with socketserver.TCPServer(("127.0.0.1", а.port),
                            http.server.SimpleHTTPRequestHandler) as с:
    с.serve_forever()
'''

ТОЧКА_ВХОДА = '''\
import argparse, http.server, socketserver
п = argparse.ArgumentParser()
п.add_argument("--port", type=int, required=True)
а = п.parse_args()
with socketserver.TCPServer(("127.0.0.1", а.port), http.server.SimpleHTTPRequestHandler) as с:
    с.serve_forever()
'''


@pytest.fixture()
def стенд(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Ячейка целиком на диске стенда: реестр, рабочая копия, каталог данных."""
    def собрать(лаунчер: str) -> str:
        репо = tmp_path / "repos" / "проба"
        (репо / "src").mkdir(parents=True, exist_ok=True)
        (репо / "run.py").write_text(textwrap.dedent(лаунчер), encoding="utf-8")
        (репо / "entry.py").write_text(textwrap.dedent(ТОЧКА_ВХОДА), encoding="utf-8")
        данные = tmp_path / "srv" / "проба-сайт" / "data"
        данные.mkdir(parents=True, exist_ok=True)
        (данные / "каталог.json").write_text("{}", encoding="utf-8")

        monkeypatch.setattr(q, "КОРЕНЬ_ПРОЕКТА", tmp_path)
        monkeypatch.setattr(q, "КОРЕНЬ_ЯЧЕЕК", tmp_path / "srv")
        monkeypatch.setattr(q, "ОЖИДАНИЕ_ЛАУНЧЕРА_С", 20)

        class Ячейка:
            site_id = "проба"
            domain = "проба-сайт"
            account = "проба-сайт"
            repo = {"path": "repos/проба"}

        monkeypatch.setattr(реестр_ячеек, "resolve", lambda _: Ячейка())
        return "проба"
    return собрать


def test_непринятый_аргумент_останавливает_заявку(стенд) -> None:
    site_id = стенд(ЛАУНЧЕР_НЕ_РАЗБИРАЕТ)
    with pytest.raises(q.RequestRejected) as отказ:
        q.проверить_лаунчер(site_id)
    текст = str(отказ.value)
    assert "--data-dir" in текст, "отказ не называет форму командной строки"
    assert "unrecognized" in текст.lower(), "в отказе нет ответа разбора аргументов"


def test_принятые_аргументы_пропускают_заявку(стенд) -> None:
    q.проверить_лаунчер(стенд(ЛАУНЧЕР_РАЗБИРАЕТ))


def test_нехватка_файлов_выпуска_не_считается_отказом(стенд) -> None:
    """`player.json` кладёт в выпуск исполнитель, в рабочей копии его нет.

    Лаунчер, остановившийся по этой причине, исправен. Проба отвечает только за
    форму аргументов и обязана промолчать.
    """
    q.проверить_лаунчер(стенд(ЛАУНЧЕР_НЕТ_ДАННЫХ))


def test_проба_не_даёт_витрине_съесть_память_вызывающего(стенд, tmp_path) -> None:
    """Проба не вправе тащить снимок каталога в память того, кто её вызвал.

    Случай измерен 2026-10-04 и стоил работающей службы. `release_plan` для
    lords-01 через MCP-мост обрывал соединение, служба умирала молча и
    поднималась обратно по `Restart=on-failure`; следующий вызов получал
    «Connection refused». Причина не в мосте: проба поднимает НАСТОЯЩУЮ витрину
    (`run.py --port … --data-dir …`), та загружает снимок каталога — замерено
    927 МиБ дочернего процесса, — а юнит моста ограничен `MemoryMax=512M`.
    cgroup упирался в предел и уничтожался целиком вместе со службой.

    Предмет пробы объявлен в её собственной документации: принимает ли цепочка
    «лаунчер → точка входа» форму аргументов юнита, и это «не зависит от
    наличия данных». Разбор аргументов укладывается в десятки мегабайт. Поэтому
    предел ставится дочернему процессу, а не службе: витрина в границах
    вызывающего не нужна никому, а её смерть по памяти пробой уже
    предусмотрена — «не поднялся за отведённое время» отказом не считается.
    """
    метки = tmp_path / "метки"
    метки.mkdir()
    import os
    os.environ["МЕТКИ"] = str(метки)
    try:
        q.проверить_лаунчер(стенд(ЛАУНЧЕР_ТЯЖЁЛЫЙ))
    finally:
        os.environ.pop("МЕТКИ", None)
    assert (метки / "разобрал").is_file(), (
        "лаунчер не дошёл до разбора аргументов — проба проверила не то")
    assert not (метки / "загрузил").is_file(), (
        "витрина загрузила снимок каталога в границах вызывающего: именно так "
        "cgroup моста упирался в MemoryMax и служба умирала")


def test_без_рабочей_копии_проверка_молчит(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Невозможность проверить — не отказ: за это отвечает проверить_рабочую_копию."""
    class Ячейка:
        site_id = "нет"
        domain = "нет.test"
        account = "нет"
        repo: dict = {}

    monkeypatch.setattr(реестр_ячеек, "resolve", lambda _: Ячейка())
    q.проверить_лаунчер("нет")


def test_проверка_стоит_в_обоих_путях_подачи() -> None:
    """Проверка, обходимая соседней командой, защищает одну дорогу, а не процесс.

    Так уже было: проверки стояли только в `cell submit`, а `cell trigger` шёл
    мимо — и заявки подавались именно им.
    """
    for файл in ("factory/cell/cli.py", "factory/cell/trigger.py"):
        текст = Path(файл).read_text(encoding="utf-8")
        assert "проверить_лаунчер" in текст, f"{файл} не вызывает проверить_лаунчер"


def test_реестр_ячеек_объявляет_лаунчер_каждой_витрине() -> None:
    """У ячейки с собственным репозиторием обязан быть run.py: его зовёт юнит."""
    реестр = json.loads(Path("config/site-cells.json").read_text(encoding="utf-8"))
    без_лаунчера = []
    for ячейка in реестр["cells"]:
        путь = (ячейка.get("repo") or {}).get("path")
        if not путь or not Path(путь).is_dir():
            continue
        if not (Path(путь) / "run.py").is_file():
            без_лаунчера.append(ячейка["site_id"])
    assert not без_лаунчера, f"ячейки с репозиторием, но без run.py: {без_лаунчера}"


def test_форма_аргументов_совпадает_с_шаблоном_юнита() -> None:
    """Проба обязана повторять шаблон юнита дословно.

    Если исполнитель сменит форму запуска, а проба останется прежней, она начнёт
    проверять несуществующую командную строку и молча перестанет защищать.
    """
    шаблон = Path("factory/cell/privileged.py").read_text(encoding="utf-8")
    assert "run.py --port {port} --data-dir {data}" in шаблон, (
        "шаблон юнита изменил форму запуска — проверить_лаунчер проверяет старую")
    проба = Path("factory/cell/queue.py").read_text(encoding="utf-8")
    assert '"--port", str(порт), "--data-dir", str(данные)' in проба


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
