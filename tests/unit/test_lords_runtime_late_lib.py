"""REQ-SEARCH-STALE-PATH: указатель находится, даже если каталога не было при старте.

Служба витрины запускается раньше, чем раскладывается релиз: между стартом и
появлением `lib` проходят секунды. Python успевает запомнить путь как
отсутствующий в кэше импортёра и дальше туда не заглядывает — поиск отвечает
«указателя нет» при лежащем рядом указателе.

Измерено на боевой витрине lords-02: библиотека на месте, файл указателя на
месте, ответ 503.
"""

from __future__ import annotations

import importlib.util
import json
import sys

import pytest

from factory.lords import search_index as си
from factory.lords.bundle import RUNTIME
from factory.site_engine import fleet_registry  # noqa: F401  (общий импорт стиля)

ЗАПИСИ = [
    {"name": "Матрица", "original_name": "The Matrix", "url": "/title/m/", "year": 1999},
]
СТРАНИЦА = ('<html><body><p class="count" id="search-count">Введите название.</p>'
            "</body></html>")


@pytest.fixture()
def витрина(tmp_path, monkeypatch):
    релиз = tmp_path / "releases" / "rel1"
    (релиз / "site" / "search").mkdir(parents=True)
    (релиз / "site" / "index.html").write_text("<h1>витрина</h1>", encoding="utf-8")
    (релиз / "site" / "search" / "index.html").write_text(СТРАНИЦА, encoding="utf-8")
    (tmp_path / "current").symlink_to(релиз)
    файл = релиз / "serve.py"
    файл.write_text(RUNTIME, encoding="utf-8")

    monkeypatch.setenv("LORDS_SITE_ROOT", str(tmp_path / "current"))
    спец = importlib.util.spec_from_file_location("lords_runtime_поздний_lib", файл)
    модуль = importlib.util.module_from_spec(спец)
    sys.modules["lords_runtime_поздний_lib"] = модуль
    спец.loader.exec_module(модуль)
    return модуль, релиз


def _разложить_библиотеку(релиз):
    import pathlib

    lib = релиз / "lib" / "factory" / "lords"
    lib.mkdir(parents=True)
    (релиз / "lib" / "factory" / "__init__.py").write_text("", encoding="utf-8")
    (lib / "__init__.py").write_text("", encoding="utf-8")
    корень = pathlib.Path(си.__file__).parent
    for имя in ("search.py", "search_index.py"):
        (lib / имя).write_text((корень / имя).read_text(encoding="utf-8"), encoding="utf-8")
    индекс = си.build(ЗАПИСИ)
    индекс["items"] = ЗАПИСИ
    (релиз / "search-index.json").write_text(json.dumps(индекс, ensure_ascii=False),
                                             encoding="utf-8")


def _api(модуль, запрос):
    собрано = {}

    def начать(status, headers):
        собрано["status"] = status

    тело = b"".join(модуль.app({"PATH_INFO": "/api/search",
                                "QUERY_STRING": f"q={запрос}"}, начать))
    return собрано["status"], json.loads(тело)


def test_указатель_появившийся_после_старта_находится(витрина):
    модуль, релиз = витрина
    # Служба уже запущена, каталога lib ещё нет — как на боевой витрине.
    статус, тело = _api(модуль, "матрица")
    assert статус.startswith("503")
    assert тело["error"] == "search_index_unavailable"

    _разложить_библиотеку(релиз)

    статус, тело = _api(модуль, "матрица")
    assert статус.startswith("200"), (
        "указатель разложен рядом, а служба его не видит: кэш импортёра помнит, "
        "что каталога не было")
    assert тело["count"] == 1
    assert тело["results"][0]["url"] == "/title/m/"


def test_повторный_запрос_не_перечитывает_указатель(витрина):
    модуль, релиз = витрина
    _разложить_библиотеку(релиз)
    _api(модуль, "матрица")
    # Отпечаток файла не изменился — второй запрос обязан обойтись памятью.
    метка = модуль._search_cache["stamp"]
    _api(модуль, "матрица")
    assert модуль._search_cache["stamp"] == метка
