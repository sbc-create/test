"""Слот под адреса действующих витрин: схема и отсутствие выдуманных значений.

Файл существует до адресов намеренно. Пустое поле — не разрешение подставить
значение по умолчанию: пока адреса нет, приёмка помечается
`BLOCKED_OWNER_URLS`, то есть ожиданием входа, а не провалом продукта.

Проверка сторожит ровно это: что слот соответствует схеме и что в нём не
появилось адреса, которого владелец не называл.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config" / "live-acceptance.json"
SCHEMA = ROOT / "schemas" / "live-acceptance.schema.json"

ПРОДУКТЫ = {"zona-cinema", "animedia-portal", "basis-video", "yummy"}


@pytest.fixture(scope="module")
def настройки() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def test_схема_компилируется():
    jsonschema.Draft202012Validator.check_schema(
        json.loads(SCHEMA.read_text(encoding="utf-8")))


def test_слот_соответствует_схеме(настройки):
    jsonschema.validate(настройки, json.loads(SCHEMA.read_text(encoding="utf-8")))


def test_названы_все_четыре_продукта(настройки):
    assert set(настройки["products"]) == ПРОДУКТЫ


def test_адрес_либо_передан_владельцем_либо_пуст(настройки):
    """Промежуточного состояния нет: выдуманный адрес хуже пустого.

    Пустой адрес останавливает приёмку и называет причину. Выдуманный — ведёт
    проверку на чужой сайт и выдаёт её результат за результат продукта.
    """
    for имя, запись in настройки["products"].items():
        адрес = запись["base_url"]
        assert адрес is None or адрес.startswith("https://"), f"{имя}: {адрес!r}"
        if адрес is not None:
            assert "localhost" not in адрес and ".test" not in адрес and ".invalid" not in адрес, (
                f"{имя}: локальный или служебный адрес приёмкой продукта не является")


def test_маршруты_относительные(настройки):
    """Абсолютный маршрут увёл бы приёмку с проверяемого сайта."""
    for имя, запись in настройки["products"].items():
        for маршрут in запись["routes"]:
            assert маршрут.startswith("/"), f"{имя}: {маршрут!r}"
            assert not маршрут.startswith("//"), f"{имя}: {маршрут!r} уводит на другой хост"


def test_у_yummy_маршруты_не_выдуманы(настройки):
    """Приложение вне фабрики: угаданный путь дал бы отказ за дефект продукта."""
    assert настройки["products"]["yummy"]["routes"] == []
