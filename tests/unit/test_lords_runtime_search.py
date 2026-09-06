"""REQ-LORDS-SEARCH-SSR: поиск отвечает на сервере, а не обещает на странице.

На боевой витрине `/search/?q=матрица`, `?q=матрца` и `?q=vfnhbwf` отдавали
один и тот же ответ в 5 268 байт: страница обещала «поиск идёт по 52 742
записям» и не применяла запрос вовсе. Набор для клиентского поиска при каталоге
больше двухсот записей не отдаётся, то есть искать было нечем.

Здесь проверяется рантайм в том виде, в каком он поедет на витрину: результаты
собираются на сервере, страница открывается без JavaScript, а отсутствие
указателя называется отказом, а не пустой выдачей.
"""

from __future__ import annotations

import importlib.util
import json
import sys

import pytest

from factory.lords import search_index as си
from factory.lords.bundle import RUNTIME

ЗАПИСИ = [
    {"name": "Матрица", "original_name": "The Matrix", "url": "/title/matrica/", "year": 1999},
    {"name": "Ёжик в тумане", "original_name": "", "url": "/title/yozhik/", "year": 1975},
    {"name": "Интерстеллар", "original_name": "Interstellar",
     "url": "/title/interstellar/", "year": 2014},
]

СТРАНИЦА = ('<html><body><h1>Поиск</h1>'
            '<p class="count" id="search-count">Введите название: поиск идёт по 3 записям.</p>'
            '</body></html>')


@pytest.fixture()
def витрина(tmp_path, monkeypatch):
    релиз = tmp_path / "releases" / "aaaa1111"
    (релиз / "site" / "search").mkdir(parents=True)
    (релиз / "site" / "index.html").write_text("<h1>витрина</h1>", encoding="utf-8")
    (релиз / "site" / "search" / "index.html").write_text(СТРАНИЦА, encoding="utf-8")

    # Оснастка поиска едет вместе с релизом: рантайм не имеет права зависеть от
    # дерева фабрики, которого на витрине нет.
    lib = релиз / "lib" / "factory" / "lords"
    lib.mkdir(parents=True)
    (релиз / "lib" / "factory" / "__init__.py").write_text("", encoding="utf-8")
    (lib / "__init__.py").write_text("", encoding="utf-8")
    корень = __import__("pathlib").Path(си.__file__).parent
    for имя in ("search.py", "search_index.py"):
        (lib / имя).write_text((корень / имя).read_text(encoding="utf-8"), encoding="utf-8")

    индекс = си.build(ЗАПИСИ)
    индекс["items"] = ЗАПИСИ
    (релиз / "search-index.json").write_text(json.dumps(индекс, ensure_ascii=False),
                                             encoding="utf-8")
    (tmp_path / "current").symlink_to(релиз)

    файл = релиз / "serve.py"
    файл.write_text(RUNTIME, encoding="utf-8")
    monkeypatch.setenv("LORDS_SITE_ROOT", str(tmp_path / "current"))
    спец = importlib.util.spec_from_file_location("lords_runtime_поиск", файл)
    модуль = importlib.util.module_from_spec(спец)
    sys.modules["lords_runtime_поиск"] = модуль
    спец.loader.exec_module(модуль)
    return модуль, релиз


def _вызов(модуль, path, query=""):
    собрано = {}

    def начать(status, headers):
        собрано["status"] = status
        собрано["headers"] = dict(headers)

    тело = b"".join(модуль.app({"PATH_INFO": path, "QUERY_STRING": query}, начать))
    return собрано["status"], собрано["headers"], тело


def test_api_находит_по_точному_названию(витрина):
    модуль, _ = витрина
    статус, _, тело = _вызов(модуль, "/api/search", "q=матрица")
    assert статус.startswith("200")
    данные = json.loads(тело)
    assert данные["count"] == 1
    assert данные["results"][0]["url"] == "/title/matrica/"


@pytest.mark.parametrize("запрос", ["матрца", "vfnhbwf", "the matrix", "ежик"])
def test_api_находит_с_опечаткой_раскладкой_латиницей_и_без_ё(витрина, запрос):
    модуль, _ = витрина
    _, _, тело = _вызов(модуль, "/api/search", f"q={запрос}")
    assert json.loads(тело)["count"] >= 1, f"запрос {запрос!r} не нашёл ничего"


def test_пустой_запрос_не_возвращает_каталог(витрина):
    модуль, _ = витрина
    _, _, тело = _вызов(модуль, "/api/search", "q=")
    assert json.loads(тело)["count"] == 0


def test_мусор_не_даёт_результатов(витрина):
    модуль, _ = витрина
    _, _, тело = _вызов(модуль, "/api/search", "q=щщъфывzzz")
    assert json.loads(тело)["count"] == 0


def test_ответ_ограничен_и_предел_не_растягивается(витрина):
    модуль, _ = витрина
    _, _, тело = _вызов(модуль, "/api/search", "q=матрица&limit=99999")
    assert len(json.loads(тело)["results"]) <= модуль.SEARCH_MAX_LIMIT


def test_страница_поиска_собирается_на_сервере(витрина):
    модуль, _ = витрина
    статус, заголовки, тело = _вызов(модуль, "/search/", "q=матрица")
    страница = тело.decode("utf-8")
    assert статус.startswith("200")
    assert "text/html" in заголовки["Content-Type"]
    assert "/title/matrica/" in страница, "результатов нет в разметке — значит, нужен JavaScript"
    assert "Найдено: 1" in страница


def test_страница_поиска_честна_про_пустой_результат(витрина):
    модуль, _ = витрина
    _, _, тело = _вызов(модуль, "/search/", "q=щщъфывzzz")
    assert "ничего не найдено" in тело.decode("utf-8")


def test_разметка_запроса_экранируется(витрина):
    модуль, _ = витрина
    _, _, тело = _вызов(модуль, "/search/", "q=%3Cscript%3Ealert(1)%3C/script%3E")
    страница = тело.decode("utf-8")
    assert "<script>alert(1)" not in страница


def test_без_указателя_отказ_а_не_пустая_выдача(витрина):
    модуль, релиз = витрина
    (релиз / "search-index.json").unlink()
    статус, _, тело = _вызов(модуль, "/api/search", "q=матрица")
    assert статус.startswith("503")
    assert json.loads(тело)["error"] == "search_index_unavailable"

    _, _, страница = _вызов(модуль, "/search/", "q=матрица")
    assert "недоступен" in страница.decode("utf-8"), (
        "страница молча ответила бы «ничего не найдено» — витрина выглядела бы "
        "исправной и не находила ничего никогда")


def test_обычные_страницы_не_задеты(витрина):
    модуль, _ = витрина
    статус, _, тело = _вызов(модуль, "/")
    assert статус.startswith("200")
    assert b"<h1>" in тело
