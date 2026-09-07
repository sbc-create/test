"""Слот под адреса витрин: состояние адреса — не готовность продукта.

Владелец передал два адреса и назвал третий ожидающим DNS. Три вещи здесь
обязаны не смешаться.

Отсутствие адреса — `BLOCKED_OWNER_URLS`, ожидание входа. Неразрешённое имя —
`PENDING_DNS`, тоже ожидание, и по прямому указанию владельца не отказ.
Отвечающий адрес, отдающий не нашу витрину, — состояние адреса, а не дефект
продукта.

Ни одно из трёх не является провалом витрины, и ни одно не даёт права
запустить приёмку: она измерила бы чужую работу и записала её в наш отчёт.
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
СЛУЖЕБНЫЕ = ("localhost", ".test", ".invalid", ".example")


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


class TestАдресаПереданыВладельцем:
    def test_адреса_соответствуют_продуктам(self, настройки):
        """Соответствие точное: адрес одной витрины под другой — худшая ошибка."""
        assert настройки["products"]["zona-cinema"]["base_url"] == "https://zonafilm.space"
        assert настройки["products"]["animedia-portal"]["base_url"] == "https://animedia.icu"

    def test_второй_домен_animedia_ожидает_dns(self, настройки):
        дополнительные = настройки["products"]["animedia-portal"]["additional_urls"]
        space = [a for a in дополнительные if a["url"] == "https://animedia.space"]
        assert space, "второй домен animedia не записан"
        assert space[0]["status"] == "PENDING_DNS", (
            "по указанию владельца это ожидание разрешения имени, а не отказ")

    def test_basis_video_остаётся_без_адреса(self, настройки):
        запись = настройки["products"]["basis-video"]
        assert запись["base_url"] is None
        assert запись["status"] == "BLOCKED_OWNER_URLS"

    def test_ни_один_адрес_не_выдуман(self, настройки):
        for имя, запись in настройки["products"].items():
            адреса = [запись["base_url"]] + [a["url"] for a in запись.get("additional_urls", [])]
            for адрес in filter(None, адреса):
                assert адрес.startswith("https://"), f"{имя}: {адрес!r}"
                assert not any(s in адрес for s in СЛУЖЕБНЫЕ), (
                    f"{имя}: служебный адрес приёмкой продукта не является")


class TestСостояниеАдресаОтделеноОтПродукта:
    def test_у_каждого_адреса_есть_состояние(self, настройки):
        for имя, запись in настройки["products"].items():
            assert запись["status"] in (
                "OWNER_SUPPLIED", "PENDING_DNS", "BLOCKED_OWNER_URLS"), имя

    def test_опознание_не_проставляется_рукой(self, настройки):
        """Поле подтверждает доказательство опознания, а не заменяет его."""
        for имя, запись in настройки["products"].items():
            if запись.get("identity_verified"):
                evidence = ROOT / "artifacts/evidence/products/live-identity.json"
                assert evidence.is_file(), f"{имя}: опознание объявлено без доказательства"
                данные = json.loads(evidence.read_text(encoding="utf-8"))
                primary = (данные.get(имя) or {}).get("primary") or {}
                assert primary.get("verdict") == "SERVES_OUR_STOREFRONT", (
                    f"{имя}: опознание объявлено, а доказательство говорит "
                    f"{primary.get('verdict')!r}")


class TestМаршруты:
    def test_маршруты_относительные(self, настройки):
        for имя, запись in настройки["products"].items():
            for маршрут in запись["routes"]:
                assert маршрут.startswith("/") and not маршрут.startswith("//"), f"{имя}"

    def test_у_yummy_маршруты_не_выдуманы(self, настройки):
        assert настройки["products"]["yummy"]["routes"] == []
