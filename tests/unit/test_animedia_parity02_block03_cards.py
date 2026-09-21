"""BLOCK_03: card variant registry completeness."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
EV = Path("artifacts/evidence/animedia-reference-parity-2026-09-20")

from tests.unit.test_animedia_visual_finalization import _load, _вид  # noqa: E402


@pytest.fixture
def fe(tmp_path):
    return _load(tmp_path, version="1.2.4")


def test_registry_declares_five_variants():
    reg = json.loads((EV / "CARD_VARIANT_REGISTRY.json").read_text())
    assert reg["CARD_VARIANTS_DECLARED"] == 5
    assert set(reg["variants"]) == {
        "top-shelf",
        "episode-row",
        "catalog-title",
        "recommendation",
        "collection-card",
    }
    assert reg["gates"]["CARD_VARIANT_ROUTE_MAPPING_COMPLETE"] == 1


def test_rendered_variants_are_declared(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    home = вид.главная()
    catalog_html = вид.список("/catalog", {})
    found = set(re.findall(r'data-card-variant="([^"]+)"', home + catalog_html))
    declared = set(json.loads((EV / "CARD_VARIANT_REGISTRY.json").read_text())["variants"])
    # The invariant that matters: nothing renders a variant the registry does
    # not declare.
    undeclared = found - declared
    assert undeclared == set(), undeclared
    assert "catalog-title" in found
    # top-shelf and episode-row are data-gated under PARITY-03: the hero needs
    # an approved WeeklyPopularSnapshot (B02) and the feed needs provider
    # playable events (B03). This fixture has neither, so both blocks collapse
    # honestly and their cards are absent by design. They must stay declared
    # for the day the data arrives; that they render then is proven in
    # test_animedia_parity03_b02.py and test_animedia_parity03_b03.py.
    assert {"top-shelf", "episode-row"} <= declared


def test_grid_css_prevents_last_row_stretch(fe):
    mod, _, _ = fe
    css = mod.АНИМЕДИА_СТИЛЬ
    assert "align-items:start" in css or "align-items:flex-start" in css
    assert ".zg" in css
