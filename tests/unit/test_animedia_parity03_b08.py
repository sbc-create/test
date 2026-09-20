"""B08 player shell geometry and single-instance contracts."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.unit.test_animedia_visual_finalization import _load, _вид  # noqa: E402

EV = ROOT / "artifacts/evidence/animedia-blockwise-parity-03-2026-09-20"
CONTRACT_SHA = (EV / "00-contract" / "CONTRACT_SHA256.txt").read_text(encoding="utf-8").strip()


@pytest.fixture
def fe(tmp_path):
    return _load(tmp_path, version="1.2.4")


def test_contract_digest_unchanged() -> None:
    assert CONTRACT_SHA == "5f2112e25ef974333c388bad405abfae3c3d460a713b028afa3c0e549b8eaeb3"


def test_player_shell_single_instance_autoplay_off(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    item = next(з for з in catalog["items"] if з["slug"] == "alpha-anime")
    html = вид.тайтл(item, details["details"]["alpha-anime"])
    assert 'data-b08="player"' in html
    assert html.count('data-player ') + html.count('data-player>') <= 2  # attr forms
    assert html.count('data-player') >= 1
    assert html.count("<video-player") <= 1
    assert 'autoplay="0"' in html
    assert 'data-player-status=' in html
    assert mod.DEFAULT_EPISODE_POLICY_DATA_GAP == 1
    assert 'data-default-episode-policy="absent"' in html


def test_css_player_16x9_no_fixed_640(fe):
    mod, _, _ = fe
    css = mod.АНИМЕДИА_СТИЛЬ
    assert "aspect-ratio:16/9" in css
    assert 'data-b08="player"' in css or "[data-b08=\"player\"]" in css
    # Must not pin media viewport to legacy 640×360 box.
    assert not re.search(r"\.zpl__f[^{]*\{[^}]*width:\s*640px", css)
    assert not re.search(r"video-player[^{]*\{[^}]*width:\s*640px", css)


def test_heading_to_shell_margin(fe):
    mod, _, _ = fe
    css = mod.АНИМЕДИА_СТИЛЬ
    assert "max-height:24px" in css  # title-gap
    assert ".zpl[data-b08=\"player\"] .zpl__h{margin:0 0 16px" in css.replace(" ", "") or \
           "margin:0 0 16px" in css
