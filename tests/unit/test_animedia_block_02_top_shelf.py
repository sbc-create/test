"""BLOCK_02: Animedia top hero shelf geometry contracts."""

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


class TestBlock02TopShelf:
    def test_ahero_poster_width_is_locked_not_content_sized(self, fe):
        # BLOCK_02 of PARITY-03 (b74739f) replaced the hard 152x214 pair with a
        # rail divided into ten equal tracks. The contract is unchanged — a hero
        # card never takes its width from its content — but the mechanism is now
        # computed rather than fixed, so cards scale with the container instead
        # of leaving a ragged tail at wide viewports.
        mod, _, _ = fe
        css = mod.АНИМЕДИА_СТИЛЬ
        assert "flex:0 0 calc((100% - 144px)/10)" in css
        assert "width:calc((100% - 144px)/10)" in css
        assert "align-items:flex-start" in css
        assert ".ahero .zt__m,.ahero .zt__r{display:none}" in css
        assert "scrollbar-width:none" in css

    def test_home_hero_needs_an_approved_snapshot_not_just_posters(self, fe):
        # Posters in the catalog are not a reason to build a curated hero.
        # BLOCK_02 allows the weekly shelf only from an approved
        # WeeklyPopularSnapshot; otherwise it collapses to 0px and declares the
        # gap. Both branches are proven in test_animedia_parity03_b02.py — this
        # guard keeps the old "posters exist, therefore hero" shortcut closed.
        mod, catalog, details = fe
        html = _вид(mod, catalog, details).главная()
        assert 'data-popular-gap="1"' in html
        assert 'data-weekly-popular="1"' not in html
        assert 'class="ahero"' not in html or "ahero--gap" in html
        # Without the collapse rule an empty shelf would still occupy space.
        assert "ahero--gap" in mod.АНИМЕДИА_СТИЛЬ
