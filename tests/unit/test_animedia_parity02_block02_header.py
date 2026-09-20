"""BLOCK_02: Animedia header taxonomy + side drawer."""

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


class TestBlock02HeaderDrawer:
    def test_taxonomy_and_drawer_markup(self, fe):
        mod, catalog, details = fe
        html = _вид(mod, catalog, details).главная()
        assert 'class="zhd__tax"' in html
        assert 'data-tax-toggle="genre"' in html or 'data-tax-toggle="lists"' in html
        assert 'id="zhd-drawer"' in html
        assert "data-drawer-toggle" in html
        assert "data-drawer-backdrop" in html
        assert "Premium" not in html
        assert "Telegram" not in html
        assert 'href="#"' not in html

    def test_logo_ani_accent(self, fe):
        mod, catalog, details = fe
        html = _вид(mod, catalog, details).главная()
        assert "<b>Ani</b>" in html or "<b>ani</b>" in html.lower()

    def test_drawer_script_a11y_contracts(self, fe):
        mod, _, _ = fe
        s = mod.СКРИПТ_АНИМЕДИА_ШАПКА
        assert "data-drawer-toggle" in s
        assert "Escape" in s
        assert "zhd-lock" in s
        assert "lastFocus" in s
        assert "aria-expanded" in s
        assert "data-drawer-backdrop" in s

    def test_type_index_and_filter(self, fe):
        mod, catalog, details = fe
        вид = _вид(mod, catalog, details)
        assert "tv" in (вид.индекс.get("type") or {})
        assert "movie" in (вид.индекс.get("type") or {})
        набор, _ = mod.отбор(вид.д, вид.индекс, {"type": ["movie"]}, "/catalog")
        assert набор
        assert all(з["slug"] in вид.индекс["type"]["movie"] for з in набор)

    def test_css_drawer_and_tax(self, fe):
        mod, _, _ = fe
        css = mod.АНИМЕДИА_СТИЛЬ
        assert ".zhd__drawer" in css
        assert ".zhd__tax" in css
        assert "body.zhd-lock" in css
        assert "max-height:88px" in css
