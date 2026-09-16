"""Посредник берёт решение об индексации из артефакта, а не из кода.

Прежде список открытых доменов был записан прямо в посреднике. Это работало, но
означало, что решение владельца живёт в одном из трёх независимых мест — и
совпадали они случайно, из-за чего обычный deploy закрывал живую витрину.

Здесь проверяется, что решение приходит из собранного артефакта, что ошибка
чтения закрывает всё, и что подделанный заголовок `Host` не открывает витрину.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ФРОНТ = КОРЕНЬ / "automation" / "host" / "yummy-frontend.py"
ПРОФИЛИ = КОРЕНЬ / "config" / "site-profiles"


def артефакт(tmp_path: Path) -> Path:
    import sys

    sys.path.insert(0, str(КОРЕНЬ))
    from factory.indexing.artifact import build, write

    return write(build(ПРОФИЛИ), tmp_path / "indexing-policy.json")


def загрузить(домен: str | None, политика: Path | None):
    """Загрузить посредник с заданным доменом экземпляра и файлом политики."""
    прежние = {k: os.environ.get(k) for k in ("YUMMY_VARIANT_DOMAIN", "LORDS_INDEXING_POLICY")}
    if домен is None:
        os.environ.pop("YUMMY_VARIANT_DOMAIN", None)
    else:
        os.environ["YUMMY_VARIANT_DOMAIN"] = домен
    os.environ["LORDS_INDEXING_POLICY"] = str(политика) if политика else "/нет/такого"
    try:
        имя = f"yf_{abs(hash((домен, str(политика))))}"
        загрузчик = importlib.machinery.SourceFileLoader(имя, str(ФРОНТ))
        модуль = importlib.util.module_from_spec(
            importlib.util.spec_from_loader(имя, загрузчик)
        )
        загрузчик.exec_module(модуль)
        return модуль
    finally:
        for k, v in прежние.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# --- решение приходит из артефакта -------------------------------------------

def test_список_доменов_больше_не_записан_в_коде() -> None:
    исходник = ФРОНТ.read_text(encoding="utf-8")
    assert "ДОМЕНЫ_С_ОТКРЫТОЙ_ИНДЕКСАЦИЕЙ" not in исходник, (
        "решение владельца не должно жить в коде посредника"
    )
    assert "LORDS_INDEXING_POLICY" in исходник


def test_открытый_домен_открыт(tmp_path: Path) -> None:
    м = загрузить("yummyani.site", артефакт(tmp_path))
    assert м.индексация_открыта("yummyani.site") is True


@pytest.mark.parametrize("домен", ["yummyani.org", "yummyani.biz", "lordfilm47.space"])
def test_закрытые_домены_закрыты(tmp_path: Path, домен: str) -> None:
    м = загрузить(домен, артефакт(tmp_path))
    assert м.индексация_открыта(домен) is False


def test_незаданная_переменная_означает_закрыто(tmp_path: Path) -> None:
    """У ВАРИАНТ_ДОМЕНА умолчание yummyani.site — на решение оно влиять не должно."""
    м = загрузить(None, артефакт(tmp_path))
    assert м.СВОЙ_ДОМЕН == ""
    assert м.индексация_открыта("yummyani.site") is False


# --- ошибка чтения закрывает всё ---------------------------------------------

def test_отсутствующий_файл_политики_закрывает_всё(tmp_path: Path) -> None:
    м = загрузить("yummyani.site", None)
    assert м.ОТКРЫТЫЕ_ДОМЕНЫ == {}
    assert м.индексация_открыта("yummyani.site") is False


def test_повреждённый_файл_политики_закрывает_всё(tmp_path: Path) -> None:
    битый = tmp_path / "indexing-policy.json"
    битый.write_text('{"schema": ', encoding="utf-8")
    м = загрузить("yummyani.site", битый)
    assert м.индексация_открыта("yummyani.site") is False


def test_пустой_файл_политики_закрывает_всё(tmp_path: Path) -> None:
    пустой = tmp_path / "indexing-policy.json"
    пустой.write_text("", encoding="utf-8")
    assert загрузить("yummyani.site", пустой).индексация_открыта("yummyani.site") is False


def test_чужая_схема_закрывает_всё(tmp_path: Path) -> None:
    чужой = tmp_path / "indexing-policy.json"
    чужой.write_text(json.dumps({"schema": "иное/9.9", "domains": {
        "yummyani.site": {"indexing_expected": "open"}}}), encoding="utf-8")
    assert загрузить("yummyani.site", чужой).индексация_открыта("yummyani.site") is False


# --- Host не открывает того, что закрыто -------------------------------------

def test_подделанный_host_не_открывает_закрытую_витрину(tmp_path: Path) -> None:
    """Экземпляр обслуживает yummyani.org; заголовок называет открытый домен."""
    м = загрузить("yummyani.org", артефакт(tmp_path))
    assert м.индексация_открыта("yummyani.site") is False
    assert м.индексация_открыта("www.yummyani.site") is False


def test_чужой_host_на_открытом_экземпляре_закрыт(tmp_path: Path) -> None:
    """Открытость домена не распространяется на запросы с чужим Host."""
    м = загрузить("yummyani.site", артефакт(tmp_path))
    for чужой in ("example.invalid", "lordfilm47.space", "127.0.0.1", ""):
        assert м.индексация_открыта(чужой) is False, чужой


def test_алиасы_своего_домена_открыты(tmp_path: Path) -> None:
    м = загрузить("yummyani.site", артефакт(tmp_path))
    for вариант in ("yummyani.site", "www.yummyani.site", "YummyAni.Site",
                    "yummyani.site.", "yummyani.site:443"):
        assert м.индексация_открыта(вариант) is True, вариант


def test_отсутствие_заголовка_host_не_закрывает_свой_домен(tmp_path: Path) -> None:
    """`None` означает «спрашивают про сам экземпляр», а не «чужой хост»."""
    м = загрузить("yummyani.site", артефакт(tmp_path))
    assert м.индексация_открыта(None) is True
    assert загрузить("yummyani.org", артефакт(tmp_path)).индексация_открыта(None) is False


# --- производные слои ---------------------------------------------------------

def test_заголовок_и_robots_решаются_одной_функцией() -> None:
    """Два слоя не должны расходиться: у них один источник ответа."""
    исходник = ФРОНТ.read_text(encoding="utf-8")
    assert исходник.count("индексация_открыта(self.headers.get(\"Host\"))") == 2
