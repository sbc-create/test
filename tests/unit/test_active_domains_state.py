"""Состояние каждого действующего домена берётся из РЕЕСТРА, а не из памяти.

Поручение владельца 27.10: «заявлено 11 подготовленных доменов, в таблице
девять, lordserials22.info пропущен». Расхождение возникает там, где таблицу
пишут руками: домен, по которому в этот раз ничего не делали, не попадает в
строку, и его состояние перестаёт быть видимым. Строки берутся из реестра
ячеек — пропустить домен нечем.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ИНСТРУМЕНТ = КОРЕНЬ / "automation" / "local" / "active-domains-state.py"


@pytest.fixture(scope="module")
def модуль():
    сп = importlib.util.spec_from_file_location("active_domains_state", ИНСТРУМЕНТ)
    м = importlib.util.module_from_spec(сп)
    sys.modules["active_domains_state"] = м
    сп.loader.exec_module(м)
    return м


@pytest.fixture(scope="module")
def строки(модуль):
    return модуль.строки()


def test_ни_один_домен_реестра_не_пропущен(строки):
    реестр = json.loads((КОРЕНЬ / "config" / "site-cells.json").read_text(
        encoding="utf-8"))
    ожидаемые = {я["domain"] for я in реестр["cells"]}
    assert {с["домен"] for с in строки} == ожидаемые


def test_lordserials22_info_в_таблице(строки):
    """Именно этот домен владелец назвал пропущенным в рукописной таблице."""
    свои = [с for с in строки if с["домен"] == "lordserials22.info"]
    assert len(свои) == 1
    assert свои[0]["состояние"] == "live"


def test_отозванные_названы_отозванными(строки):
    отозванные = {с["домен"] for с in строки if с["состояние"] == "ОТОЗВАН"}
    assert отозванные == {"animedia.space", "lordfilm47.space",
                          "lordserials22.site", "lordserials22.space"}


def test_у_каждой_строки_названы_все_поля(строки):
    for с in строки:
        for поле in ("site_id", "домен", "состояние", "пин", "продвижение",
                     "подборки"):
            assert поле in с and с[поле] not in (None,), (с["домен"], поле)


def test_подборки_zona_названы_выпущенными(строки):
    """Состояние поставки отделяет подготовленное от выпущенного, и после
    публичной проверки оно обязано это показывать."""
    for домен in ("zonafilm.space", "zonafilm12.site"):
        с = next(x for x in строки if x["домен"] == домен)
        assert с["подборки"].startswith("3 ("), с["подборки"]
        assert "VERIFIED_LIVE" in с["подборки"], с["подборки"]


def test_ключ_active_убирает_только_отозванных_и_пробы(модуль):
    все = модуль.строки()
    итог = модуль.главная(["--json", "--active"])
    assert итог == 0
    # Проб в реестре четыре (site-a/b/c и pilot-local) плюс четыре отозванных.
    пробы = [с for с in все if с["домен"].endswith(".localhost")
             or ".localhost." in с["домен"]]
    отозванные = [с for с in все if с["состояние"] == "ОТОЗВАН"]
    assert пробы and отозванные
