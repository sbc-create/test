"""Каждый профиль витрины валиден по схеме манифеста.

Проверки не было, и это обнаружилось дорого: токены раскладки Lords были
объявлены в профилях, прочитаны отрисовщиком и попали бы в релиз, оставаясь
невалидными по схеме — `additionalProperties: false` их не допускала. Схема
и профили разъехались бы молча.

Здесь же закреплено обратное требование: токен, который отрисовщик умеет
читать, обязан быть объявлен в схеме. Иначе схема описывает не то, что
происходит, и перестаёт быть источником правды.
"""
from __future__ import annotations

import json
import pathlib

import jsonschema
import pytest
import yaml

from factory.lords import theme

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
СХЕМА = КОРЕНЬ / "schemas" / "template-manifest.schema.json"
ПРОФИЛИ = sorted((КОРЕНЬ / "blueprints" / "lords" / "profiles").glob("*.yaml"))


@pytest.fixture(scope="module")
def схема() -> dict:
    return json.loads(СХЕМА.read_text(encoding="utf-8"))


@pytest.mark.parametrize("файл", ПРОФИЛИ, ids=lambda ф: ф.stem)
def test_профиль_валиден(файл, схема):
    д = yaml.safe_load(файл.read_text(encoding="utf-8"))
    jsonschema.validate(д, схема)


def test_профилей_не_меньше_шести():
    assert len(ПРОФИЛИ) >= 6, [ф.name for ф in ПРОФИЛИ]


def test_каждый_читаемый_токен_объявлен_в_схеме(схема):
    """Схема описывает ровно то, что отрисовщик умеет прочитать."""
    объявлены = set(схема["$defs"]["design_tokens"]["properties"])
    читаемые = set(theme.DEFAULT_TOKENS)
    не_объявлены = читаемые - объявлены
    assert не_объявлены == set(), (
        f"отрисовщик читает токены, которых схема не знает: "
        f"{sorted(не_объявлены)}")


def test_схема_не_объявляет_лишнего(схема):
    """Обратное тоже верно: поле схемы без исполнителя — обещание впустую."""
    объявлены = set(схема["$defs"]["design_tokens"]["properties"])
    читаемые = set(theme.DEFAULT_TOKENS)
    лишние = объявлены - читаемые
    assert лишние == set(), (
        f"схема объявляет токены, которых отрисовщик не читает: {sorted(лишние)}")
