"""Block 03 — unified Lords card component contract."""

from __future__ import annotations

import pathlib
import re

ИСХОДНИК = pathlib.Path(__file__).resolve().parents[2] / "automation" / "host" / "lords-frontend.py"


def _css() -> str:
    текст = ИСХОДНИК.read_text(encoding="utf-8")
    m = re.search(r"ЛОРДС_СТИЛЬ = \"\"\"(.*?)\"\"\"", текст, re.S)
    assert m
    return m.group(1)


def _карточка_src() -> str:
    текст = ИСХОДНИК.read_text(encoding="utf-8")
    i = текст.index("class ВидЛордс")
    j = текст.index("def карточка(self, запись: dict)", i)
    k = текст.index("\n    def ", j + 1)
    return текст[j:k]


class TestBlock03Card:
    def test_poster_ratio_2_3(self):
        assert "aspect-ratio:2/3" in _css()

    def test_object_fit_cover(self):
        assert "object-fit:cover" in _css()

    def test_title_two_line_clamp(self):
        css = _css()
        assert "-webkit-line-clamp:2" in css
        assert "height:66px" in css  # fixed caption band

    def test_grid_columns_by_viewport(self):
        css = _css()
        assert "repeat(2,1fr)" in css
        assert "repeat(4,1fr)" in css
        assert "repeat(6,1fr)" in css

    def test_missing_rating_not_zero(self):
        src = _карточка_src()
        assert "aria-hidden=\"true\"" in src
        assert 'КП<i>0</i>' not in src
        assert "if кп or им:" in src

    def test_rating_has_source_label(self):
        src = _карточка_src()
        assert "КП" in src and "IMDb" in src
