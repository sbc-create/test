"""B08 player shell + owner-resolved FIRST_PLAYABLE_DETERMINISTIC policy."""
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


def test_owner_policy_resolved(fe):
    mod, _, _ = fe
    assert mod.АНИМЕДИА_DEFAULT_EPISODE_POLICY == "FIRST_PLAYABLE_DETERMINISTIC"
    assert mod.DEFAULT_EPISODE_POLICY_DATA_GAP == 0
    assert mod.АНИМЕДИА_DEFAULT_EPISODE_OWNER_DECISION == "ANIMEDIA-B10-B16-20260920-01"
    assert Path(mod.АНИМЕДИА_DEFAULT_EPISODE_POLICY_PATH).is_file()


def test_first_playable_deterministic_not_latest(fe):
    mod, catalog, details = fe
    det = {
        "seasons": [
            {"n": 2, "eps": 10, "avail": 3},
            {"n": 1, "eps": 12, "avail": 5},
        ],
        "playable": True,
    }
    s, e = mod.выбрать_доступную_серию(det)
    assert (s, e) == (1, 1)


def test_generic_hub_flags_policy_and_keeps_title_url(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    item = next(з for з in catalog["items"] if з["slug"] == "alpha-anime")
    html = вид.тайтл(item, details["details"]["alpha-anime"])
    assert 'data-default-episode-policy="FIRST_PLAYABLE_DETERMINISTIC"' in html
    assert 'data-default-episode-decision="ANIMEDIA-B10-B16-20260920-01"' in html
    assert 'data-default-e="1"' in html  # alpha avail starts at 1
    # Generic URL identity — no auto-redirect to episode path in markup.
    assert 'rel="canonical" href="https://animedia.space/title/alpha-anime/"' in html
    assert "/season-" not in re.search(
        r'rel="canonical" href="([^"]+)"', html).group(1)


def test_exact_episode_preserved(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    item = next(з for з in catalog["items"] if з["slug"] == "alpha-anime")
    html = вид.серия(item, details["details"]["alpha-anime"], 1, 4)
    assert 'data-season="1"' in html
    assert 'data-episode="4"' in html
    assert "/season-1/episode-4/" in html
    # Must not swap to first playable (1).
    assert 'data-episode="1"' not in html.split('data-b09="player"')[1].split("</section>")[0]


def test_player_shell_single_instance_autoplay_off(fe):
    mod, catalog, details = fe
    вид = _вид(mod, catalog, details)
    item = next(з for з in catalog["items"] if з["slug"] == "alpha-anime")
    html = вид.тайтл(item, details["details"]["alpha-anime"])
    assert 'data-b08="player"' in html
    assert html.count('id="watch"') == 1
    assert html.count("<video-player") <= 1
    assert 'data-player-status=' in html
    if "<video-player" in html:
        assert 'autoplay="0"' in html
    else:
        state = re.search(r'data-state="([^"]+)"', html)
        assert state and state.group(1) in {
            "awaiting", "noaccess", "nosource", "unavailable", "provider", "error",
            "resolving",
        }


def test_css_player_16x9_no_fixed_640(fe):
    mod, _, _ = fe
    css = mod.АНИМЕДИА_СТИЛЬ
    assert "aspect-ratio:16/9" in css
    assert "[data-b08=\"player\"]" in css or 'data-b08="player"' in css
    assert not re.search(r"\.zpl__f[^{]*\{[^}]*width:\s*640px", css)


def test_heading_to_shell_margin(fe):
    mod, _, _ = fe
    css = mod.АНИМЕДИА_СТИЛЬ
    assert "max-height:24px" in css
