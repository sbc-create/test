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
    def test_ahero_fixed_poster_contract(self, fe):
        mod, _, _ = fe
        css = mod.АНИМЕДИА_СТИЛЬ
        assert "width:152px;height:214px" in css
        assert "flex:0 0 152px" in css
        assert "min-width:152px" in css
        assert "max-height:300px" in css
        assert ".ahero .zt__m,.ahero .zt__r{display:none}" in css
        assert "scrollbar-width:none" in css

    def test_home_renders_ahero_when_posters_exist(self, fe):
        mod, catalog, details = fe
        html = _вид(mod, catalog, details).главная()
        # fixtures have posters on most items
        assert 'class="ahero"' in html
        assert "zrl__track" in html
        assert "data-rl" in html or "zrl__btn" in html
