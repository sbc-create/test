"""Country facet href and route parser must share one latin slug registry.

Regression for LORDS-MULTISITE-AUDIT-01 RC-COUNTRY-404:
UI emitted /country/великобритания/ while МАРШРУТ_СТРАНЫ only accepted [a-z0-9_-].
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import sys

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ИСХОДНИК = КОРЕНЬ / "automation" / "host" / "lords-frontend.py"


@pytest.fixture(scope="module")
def fe():
    спец = importlib.util.spec_from_file_location("lords_frontend_country", ИСХОДНИК)
    мод = importlib.util.module_from_spec(спец)
    sys.modules["lords_frontend_country"] = мод
    спец.loader.exec_module(мод)
    return мод


def test_country_code_is_latin_like_genre(fe):
    код = fe.нормализовать(fe.транслит("Великобритания"))
    assert код == "velikobritaniya"
    assert re.fullmatch(r"[a-z0-9_-]+", код)


def test_country_route_regex_accepts_latin_slug(fe):
    m = fe.Обработчик.МАРШРУТ_СТРАНЫ.match("/country/velikobritaniya/")
    assert m is not None
    assert m.group("code") == "velikobritaniya"


def test_index_countries_uses_translit(fe):
    src = ИСХОДНИК.read_text(encoding="utf-8")
    # Builder must transliterate country labels the same way as genres.
    assert "код = нормализовать(транслит(страна))" in src
    # Genre-style comment still documents the ASCII route contract.
    assert "МАРШРУТ_СТРАНЫ" in src
    assert "INTERNAL_LINK_404" in src or "Cyrillic path codes never matched" in src


def test_country_filter_resolves_aliases(fe):
    src = ИСХОДНИК.read_text(encoding="utf-8")
    # отбор must try translit aliases, not only exact key
    assert 'нормализовать(транслит(страна))' in src[src.index("def отбор"):src.index("def отбор")+2500]


def test_legacy_films_cartoons_redirects_declared(fe):
    assert fe.Обработчик.ПРЕЖНИЕ_АДРЕСА.get("/films/") == "/movies/"
    assert fe.Обработчик.ПРЕЖНИЕ_АДРЕСА.get("/cartoons/") == "/animation/"
