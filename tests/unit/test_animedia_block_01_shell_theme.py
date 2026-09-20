"""BLOCK_01: Animedia shell, header, theme bootstrap."""

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


class TestBlock01ShellTheme:
    def test_theme_boot_before_css(self, fe):
        mod, catalog, details = fe
        html = _вид(mod, catalog, details).главная()
        boot_at = html.find("animedia-theme")
        style_at = html.find("<style>")
        assert boot_at > 0 and style_at > 0
        # Boot script appears before main stylesheet.
        first_script = html.find("<script>")
        assert first_script < style_at
        assert "СКРИПТ_АНИМЕДИА_ТЕМА_BOOT" in dir(mod) or "prefers-color-scheme" in mod.СКРИПТ_АНИМЕДИА_ТЕМА_BOOT
        assert "colorScheme" in mod.СКРИПТ_АНИМЕДИА_ТЕМА_BOOT

    def test_header_actions_and_touch_targets(self, fe):
        mod, catalog, details = fe
        html = _вид(mod, catalog, details).главная()
        assert 'class="zhd__actions"' in html
        assert "data-theme-toggle" in html
        assert "data-drawer-toggle" in html or "data-nav-toggle" in html
        css = mod.АНИМЕДИА_СТИЛЬ
        assert "flex:0 0 44px" in css
        assert "min-width:44px" in css
        assert "color-scheme:dark" in css
        assert "filter:none !important" in css

    def test_theme_script_persists_and_syncs_aria(self, fe):
        mod, _, _ = fe
        s = mod.СКРИПТ_АНИМЕДИА_ШАПКА
        assert "localStorage.setItem(TK,next)" in s
        assert "aria-pressed" in s
        assert "prefers-color-scheme" in s
        assert "addEventListener('change'" in s

    def test_nav_routes_real(self, fe):
        mod, catalog, details = fe
        html = _вид(mod, catalog, details).главная()
        assert 'href="#"' not in html
        assert "javascript:void" not in html
        for path in ("/", "/catalog/", "/new/", "/collections/"):
            assert f'href="{path}"' in html or f"href='{path}'" in html

    def test_dark_tokens_do_not_use_global_invert(self, fe):
        mod, _, _ = fe
        css = mod.АНИМЕДИА_СТИЛЬ
        assert "filter:invert" not in css
        assert "html[data-theme=dark]" in css
        assert "--a-page:#12141a" in css
