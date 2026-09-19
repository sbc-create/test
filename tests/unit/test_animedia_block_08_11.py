"""BLOCK_08–11: catalog cards, search ranking, collections, footer."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.unit.test_animedia_visual_finalization import _load, _вид  # noqa: E402


@pytest.fixture
def fe(tmp_path):
    return _load(tmp_path, version="1.2.4")


class TestBlock08Catalog:
    def test_catalog_cards_have_no_full_description(self, fe):
        mod, catalog, details = fe
        html = _вид(mod, catalog, details).список("/catalog", {})
        assert 'class="zt"' in html
        assert 'class="zr__d"' not in html
        # cards must not embed a description panel
        assert html.count('id="title-desc"') == 0


class TestBlock09Search:
    def test_multi_token_outranks_single_token_prefix(self, fe):
        mod, _, _ = fe
        items = [
            {"slug": "a", "title": "Воин Мегамен", "kind": "Аниме", "year": 2000,
             "published_at": "2020-01-01T00:00:00Z", "poster": "", "url": "/title/a/", "id": "1"},
            {"slug": "b", "title": "Звёздные войны", "kind": "Аниме", "year": 2000,
             "published_at": "2020-01-02T00:00:00Z", "poster": "", "url": "/title/b/", "id": "2"},
            {"slug": "c", "title": "Звёздные войны: Видения", "kind": "Аниме", "year": 2000,
             "published_at": "2020-01-03T00:00:00Z", "poster": "", "url": "/title/c/", "id": "3"},
        ]
        данные = mod.Данные.__new__(mod.Данные)
        данные.items = []
        for з in items:
            з = dict(з)
            з["_n"] = mod.нормализовать(з["title"])
            з["_формы"] = [з["_n"]] + [mod.нормализовать(т) for т in з["title"].split()]
            данные.items.append(з)
        res = данные.искать("Звёздные войны")
        titles = [з["title"] for з in res]
        assert titles[0] == "Звёздные войны"
        assert "Воин Мегамен" not in titles[:3]


class TestBlock11Footer:
    def test_footer_mobile_two_col_css(self, fe):
        mod, _, _ = fe
        assert "grid-template-columns:repeat(2,minmax(0,1fr))" in mod.АНИМЕДИА_СТИЛЬ
        assert ".zft__nav" in mod.АНИМЕДИА_СТИЛЬ
