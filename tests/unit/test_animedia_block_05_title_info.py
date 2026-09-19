"""BLOCK_05: Animedia title info layout — semantic facts, single description."""

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


class TestBlock05TitleInfo:
    def test_facts_dl_not_raw_dot_join(self, fe):
        mod, catalog, details = fe
        вид = _вид(mod, catalog, details)
        item = next(з for з in вид.д.items if з["slug"] in details["details"])
        det = details["details"][item["slug"]]
        html = вид.тайтл(item, det)
        assert 'class="ztitle__facts"' in html
        assert "<dt>Год</dt>" in html or "<dt>Тип</dt>" in html
        assert 'class="ztitle__meta"' not in html
        assert "ztitle__poster" in html
        desc = (det.get("description") or det.get("short_description") or "").strip()
        if not desc:
            assert "ztitle__desc-panel" not in html
        elif len(desc) > 220:
            assert "Развернуть" in html
            assert html.count('id="title-desc"') == 1

    def test_css_facts_and_compact_poster(self, fe):
        mod, _, _ = fe
        css = mod.АНИМЕДИА_СТИЛЬ
        assert ".ztitle__facts" in css
        assert "clamp(180px,13vw,220px)" in css
        assert "max-width:70ch" in css
