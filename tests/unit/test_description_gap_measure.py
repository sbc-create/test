"""Пробел описаний: порог, факты и то, чего замер не вправе утверждать."""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ПУТЬ = КОРЕНЬ / "automation" / "local" / "description-gap-measure.py"

спец = importlib.util.spec_from_file_location("description_gap", ПУТЬ)
модуль = importlib.util.module_from_spec(спец)
assert спец.loader is not None
спец.loader.exec_module(модуль)


def снимок(записи: dict) -> dict:
    return {"details": записи, "catalog_built_at": "2026-10-21T03:15:26Z"}


# --- порог -----------------------------------------------------------------

@pytest.mark.parametrize("текст", ["", "   ", None, "Нет", "Описания пока нет"])
def test_обрывок_описанием_не_считается(текст):
    assert модуль.описание_есть({"description": текст}) is False


def test_настоящее_описание_считается():
    assert модуль.описание_есть(
        {"description": "Девушка присоединяется к клубу исследователей"
                        " паранормального, и компания едет в деревню."}) is True


def test_порог_ровно_на_границе():
    assert модуль.описание_есть({"description": "я" * 39}) is False
    assert модуль.описание_есть({"description": "я" * 40}) is True


def test_пробелы_по_краям_в_длину_не_идут():
    # 60 пробелов плюс 30 знаков — это 30 знаков, то есть НЕ описание, хотя
    # строка длинная. Иначе отступы шаблона считались бы содержанием.
    assert модуль.описание_есть({"description": " " * 60 + "я" * 30}) is False
    assert модуль.описание_есть({"description": " " * 20 + "я" * 45}) is True
    assert модуль.описание_есть({"description": " " * 60}) is False


# --- факты -----------------------------------------------------------------

def test_пустые_значения_фактом_не_являются():
    assert модуль.факты_записи(
        {"genres": [], "year": None, "original_name": "  ",
         "imdb_rating": 0, "ratings_by_source": {}}) == set()


def test_факты_узнаются_по_своим_типам():
    найдено = модуль.факты_записи(
        {"genres": ["игра"], "year": 2023, "original_name": "Road to A Million",
         "imdb_rating": 6.8, "sources": [{"a": 1}], "type": "serial"})
    assert найдено == {"genres", "year", "original_name", "imdb_rating",
                       "sources", "type"}


def test_посторонние_поля_фактами_не_считаются():
    assert модуль.факты_записи({"description_source": "detail",
                                "id": "007"}) == set()


# --- разбор снимка ---------------------------------------------------------

def test_доля_и_число_считаются_вместе():
    замер = модуль.разобрать(снимок({
        "a": {"description": "я" * 100},
        "b": {"description": ""},
        "c": {"description": "коротко"},
        "d": {"description": "я" * 60},
    }))
    assert замер["записей"] == 4
    assert замер["без_описания"] == 2
    assert замер["доля_без_описания"] == 50.0


def test_медиана_считается_только_по_непустым():
    замер = модуль.разобрать(снимок({
        "a": {"description": "я" * 100},
        "b": {"description": "я" * 300},
        "c": {"description": ""},
    }))
    assert замер["длина_описания_медиана"] == 200


def test_бедной_считается_запись_без_жанров_и_оценок():
    замер = модуль.разобрать(снимок({
        "a": {"description": "", "year": 1983},
        "b": {"description": "", "genres": ["драма"]},
        "c": {"description": "", "imdb_rating": 7.1},
        "d": {"description": "", "ratings_by_source": {"imdb": 7.1}},
    }))
    # Год сам по себе страницу не наполняет: бедная здесь только первая.
    assert замер["без_описания_и_без_фактов"] == 1


def test_играбельность_считается_отдельно_от_описания():
    замер = модуль.разобрать(снимок({
        "a": {"description": "", "playable": True},
        "b": {"description": "", "playable": False},
        "c": {"description": "я" * 80, "playable": True},
    }))
    assert замер["без_описания"] == 2
    assert замер["играбельных_без_описания"] == 1


def test_месяц_добавления_берётся_из_каталога():
    замер = модуль.разобрать(
        снимок({"a": {"description": ""}, "b": {"description": ""}}),
        каталог={"items": [{"slug": "a", "published_at": "2026-10-04T10:00:00Z"},
                           {"slug": "b", "published_at": "2026-09-30"}]})
    assert замер["добавлены_по_месяцам"] == {"2026-10": 1, "2026-09": 1}


def test_без_каталога_месяцы_не_придумываются():
    замер = модуль.разобрать(снимок({"a": {"description": ""}}))
    assert замер["добавлены_по_месяцам"] == {}


def test_снимок_без_details_не_измерен():
    assert модуль.разобрать({"schema": "x"})["ошибка"]


def test_полный_снимок_даёт_нулевой_пробел():
    замер = модуль.разобрать(снимок({"a": {"description": "я" * 90}}))
    assert замер["без_описания"] == 0
    assert замер["доля_без_описания"] == 0.0
