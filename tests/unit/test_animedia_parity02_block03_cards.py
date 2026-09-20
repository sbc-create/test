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
    undeclared = found - declared
    assert undeclared == set(), undeclared
    assert "top-shelf" in found
    assert "catalog-title" in found
    assert "episode-row" in found


def test_grid_css_prevents_last_row_stretch(fe):
    mod, _, _ = fe
    css = mod.АНИМЕДИА_СТИЛЬ
    assert "align-items:start" in css or "align-items:flex-start" in css
    assert ".zg" in css
