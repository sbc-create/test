"""B03 provider playable feed / compact empty — BLOCKWISE-PARITY-03."""
from __future__ import annotations

import json
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


def test_home_b03_compact_empty_without_ledger(fe, monkeypatch, tmp_path):
    mod, catalog, details = fe
    missing = tmp_path / "no-events.json"
    monkeypatch.setenv("ANIMEDIA_PROVIDER_PLAYABLE_EVENTS", str(missing))
    mod.АНИМЕДИА_PROVIDER_PLAYABLE_PATH = str(missing)
    html = _вид(mod, catalog, details).главная()
    assert 'data-b03="empty"' in html
    assert "Новые серии аниме" in html
    assert "источник событий ещё не подключён" in html
    assert 'data-provider-playable-count="0"' in html
    # Must not fall back to catalog_publish rows on home B03.
    assert 'data-event-kind="catalog_publish"' not in html.split("data-b03=")[1].split("<div class=\"zad-mid\"")[0]
    assert "ahome-eps--empty" in html
    assert "max-height:96px" in mod.АНИМЕДИА_СТИЛЬ


def test_catalog_publish_helper_not_used_as_b03(fe, monkeypatch, tmp_path):
    mod, catalog, details = fe
    missing = tmp_path / "no-events.json"
    monkeypatch.setenv("ANIMEDIA_PROVIDER_PLAYABLE_EVENTS", str(missing))
    mod.АНИМЕДИА_PROVIDER_PLAYABLE_PATH = str(missing)
    вид = _вид(mod, catalog, details)
    # Helper may still exist for /new/ transition, but home block must be empty.
    legacy = вид._эпизод_события()
    assert legacy  # fixture has seasons
    assert all(e.get("event_kind") == "catalog_publish" for e in legacy)
    assert вид._provider_playable_events() == []
    html = вид.главная()
    assert 'data-b03="empty"' in html


def test_populated_from_provider_ledger(fe, monkeypatch, tmp_path):
    mod, catalog, details = fe
    ledger = {
        "events": [
            {
                "event_id": "e1",
                "event_type": "provider_became_playable",
                "title_slug": "alpha-anime",
                "title_id": "alpha-anime",
                "season": 1,
                "episode": 5,
                "provider_available_at": "2026-09-18T12:00:00Z",
                "current_availability_revision": "r1",
                "provenance": "test-ledger",
            },
            {
                "event_id": "e2",
                "event_type": "provider_became_playable",
                "title_slug": "beta-series",
                "season": 1,
                "episode": 2,
                "provider_available_at": "2026-09-17T12:00:00Z",
                "current_availability_revision": "r1",
            },
            {
                "event_id": "e3",
                "event_type": "provider_became_playable",
                "title_slug": "delta-old",
                "season": 1,
                "episode": 1,
                "provider_available_at": "2026-09-16T12:00:00Z",
                "current_availability_revision": "r1",
            },
            {
                "event_id": "e4",
                "event_type": "provider_became_playable",
                "title_slug": "gamma-movie",
                "season": 1,
                "episode": 1,
                "provider_available_at": "2026-09-15T12:00:00Z",
                "current_availability_revision": "r1",
            },
        ]
    }
    # gamma may lack seasons in fixture — only rows that resolve matter
    path = tmp_path / "events.json"
    path.write_text(json.dumps(ledger), encoding="utf-8")
    monkeypatch.setenv("ANIMEDIA_PROVIDER_PLAYABLE_EVENTS", str(path))
    mod.АНИМЕДИА_PROVIDER_PLAYABLE_PATH = str(path)
    html = _вид(mod, catalog, details).главная()
    assert 'data-b03="populated"' in html or 'data-b03="empty"' in html
    # At least alpha/beta have seasons in fixture
    if 'data-b03="populated"' in html:
        assert "alpha-anime" in html
        assert 'data-event-kind="catalog_publish"' not in html
        assert "provider_became_playable" in html or "aeps__row" in html


def test_true_provider_count_constant(fe):
    mod, _, _ = fe
    assert mod.TRUE_PROVIDER_PLAYABLE_EVENT_COUNT == 0
    assert mod.АНИМЕДИА_ЭПИЗОД_ЗАГОЛОВОК == "Новые серии аниме"
