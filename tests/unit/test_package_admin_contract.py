"""Раздел админки в пакете витрины: объявление контракта, а не движка.

Схема пакета закрыта для посторонних полей (`additionalProperties: false`), и
это правильно: поле, которого схема не знает, выглядит настройкой и ни на что
не влияет. Поэтому появление раздела `admin` — осознанная правка схемы, и она
приходит вместе с этими проверками, а не после них.

Что объявляется. Версия контракта, под которую написано потребление, и
поверхности, которые оператор вправе править. Движок админки принадлежит
другой полосе и в шаблоны не копируется — здесь только сторона потребителя.

Зачем объявлять вообще. Манифест — первый источник истины. Имена полей
настроек живут в компонентах строками, и расхождение версий сегодня заметно
лишь по исчезнувшему тексту на витрине. Объявленная версия делает расхождение
проверяемым до выкладки.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "schemas" / "site-package.schema.json").read_text(encoding="utf-8"))

#: Витрины на движке payload-next-multisite: контракт админки объявлен у них.
MULTISITE_SITES = ("site-a", "site-b", "site-c")


def _validator() -> Draft202012Validator:
    return Draft202012Validator(SCHEMA)


def _package(site: str) -> dict:
    return yaml.safe_load((ROOT / "sites" / site / "package.yaml").read_text(encoding="utf-8"))


class TestСхемаЗнаетРазделАдминки:
    def test_раздел_объявлен(self):
        assert "admin" in SCHEMA["properties"], "схема не знает раздела admin"

    def test_версия_контракта_обязательна(self):
        assert SCHEMA["properties"]["admin"]["required"] == ["contract"]

    def test_посторонние_поля_не_принимаются(self):
        """Иначе опечатка в имени поля выглядела бы настройкой."""
        assert SCHEMA["properties"]["admin"]["additionalProperties"] is False

    @pytest.mark.parametrize("value", ["site-admin/1.0.0", "site-admin/2.13.4"])
    def test_версия_принимается_в_объявленном_виде(self, value):
        errors = list(_validator().iter_errors({"admin": {"contract": value}}))
        assert [e for e in errors if "admin" in list(e.path)] == []

    @pytest.mark.parametrize("value", ["site-admin", "1.0.0", "admin/1.0.0", "site-admin/1.0"])
    def test_произвольная_строка_версией_не_считается(self, value):
        """Версия без формата не сравнима, а значит бесполезна."""
        errors = [e for e in _validator().iter_errors({"admin": {"contract": value}})
                  if "admin" in list(e.path)]
        assert errors, f"схема приняла «{value}» как версию контракта"

    def test_поверхность_вне_перечня_отвергается(self):
        errors = [e for e in _validator().iter_errors(
            {"admin": {"contract": "site-admin/1.0.0", "editable_surfaces": ["база"]}})
            if "admin" in list(e.path)]
        assert errors, "схема приняла неизвестную поверхность правки"


class TestПакетыОбъявляютКонтракт:
    @pytest.mark.parametrize("site", MULTISITE_SITES)
    def test_контракт_объявлен(self, site):
        admin = _package(site).get("admin") or {}
        assert admin.get("contract") == "site-admin/1.0.0", (
            f"{site}: контракт админки не объявлен в манифесте"
        )

    @pytest.mark.parametrize("site", MULTISITE_SITES)
    def test_объявленные_поверхности_осмысленны(self, site):
        surfaces = (_package(site).get("admin") or {}).get("editable_surfaces") or []
        assert surfaces, f"{site}: не сказано, что оператор вправе править"
        assert len(set(surfaces)) == len(surfaces), f"{site}: поверхность названа дважды"

    @pytest.mark.parametrize("site", MULTISITE_SITES)
    def test_пакет_проходит_схему(self, site):
        errors = [e for e in _validator().iter_errors(_package(site))
                  if "admin" in list(e.path)]
        assert errors == [], f"{site}: раздел admin не проходит схему: {errors[:1]}"


class TestДвижокАдминкиВШаблоныНеПопал:
    """Запрет прямой и проверяемый: backend админки в шаблонах не хранится."""

    def test_в_пакетах_нет_учётных_данных_админки(self):
        for site in MULTISITE_SITES:
            admin = _package(site).get("admin") or {}
            запрещено = {"password", "secret", "token", "users", "operators", "roles"}
            пересечение = запрещено & set(admin)
            assert not пересечение, f"{site}: в разделе admin оказалось {пересечение}"
