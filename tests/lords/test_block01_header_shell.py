"""Block 01 — Lords page shell + header contract vs lordfilm-hit tokens."""

from __future__ import annotations

import pathlib
import re

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ИСХОДНИК = КОРЕНЬ / "automation" / "host" / "lords-frontend.py"


def _lords_css() -> str:
    текст = ИСХОДНИК.read_text(encoding="utf-8")
    m = re.search(r"ЛОРДС_СТИЛЬ = \"\"\"(.*?)\"\"\"", текст, re.S)
    assert m, "ЛОРДС_СТИЛЬ missing"
    return m.group(1)


class TestBlock01Container:
    def test_sheet_max_width_1440(self):
        css = _lords_css()
        assert "max-width:1440px" in css.replace(" ", "") or "max-width:1440px" in css

    def test_no_dead_top_margin_118(self):
        css = _lords_css()
        assert "margin-top:118px" not in css

    def test_html_overflow_clip(self):
        текст = ИСХОДНИК.read_text(encoding="utf-8")
        assert "overflow-x:clip" in текст


class TestBlock01Header:
    def test_header_not_sticky(self):
        css = _lords_css()
        # Only .hd rule — must be relative (reference lordfilm-hit).
        m = re.search(r"\.hd\{([^}]+)\}", css)
        assert m, ".hd rule missing"
        assert "position:relative" in m.group(1)
        assert "position:sticky" not in m.group(1)

    def test_desktop_header_height_70(self):
        css = _lords_css()
        assert "height:70px" in css
        assert "min-height:70px" in css

    def test_desktop_nav_nowrap(self):
        css = _lords_css()
        assert "flex-wrap:nowrap" in css
        # Desktop row starts at the fit-breakpoint (~1024), not the old 768.
        assert re.search(
            r"@media\(min-width:1024px\)\{\.hd__nav\{[^}]*flex-wrap:nowrap", css)

    def test_touch_targets_44(self):
        css = _lords_css()
        assert "width:44px;height:44px" in css.replace("\n", "") or "width:44px" in css
        assert "min-height:44px" in css

    def test_search_capped_on_desktop(self):
        css = _lords_css()
        assert re.search(
            r"@media\(min-width:1024px\)\{\.hd__s\{[^}]*max-width:200px", css)
