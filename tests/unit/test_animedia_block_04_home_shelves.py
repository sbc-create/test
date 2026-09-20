"""BLOCK_04: home lower shelf density + hero refill."""

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


class TestBlock04HomeShelves:
    def test_seven_col_compact_cards(self, fe):
        mod, _, _ = fe
        css = mod.АНИМЕДИА_СТИЛЬ
        assert "repeat(7,minmax(0,1fr))" in css
        assert "max-height:320px" in css
        assert ".zt__t" in css and "-webkit-line-clamp:2" in css

    def test_first_shelf_survives_hero(self, fe):
        mod, catalog, details = fe
        # Space profile: recently_added feeds hero; must still render a first shelf.
        html = _вид(mod, catalog, details, host="animedia.space").главная()
        assert "Новые аниме на сайте" in html or "Популярное за неделю" in html or "Топ по оценкам" in html
        assert 'class="zg"' in html
        assert html.count('class="zt"') >= 2

    def test_domains_keep_distinct_shelf_keys(self, fe):
        mod, _, _ = fe
        space = mod.АНИМЕДИА_ДОМЕНЫ["animedia.space"]["home_shelves"]
        icu = mod.АНИМЕДИА_ДОМЕНЫ["animedia.icu"]["home_shelves"]
        assert space != icu
        assert "video_available" not in space
        assert "series_with_episodes" in icu
