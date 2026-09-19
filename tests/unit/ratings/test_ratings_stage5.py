"""Stage 5 unit tests — queue, mapping, source isolation, sim, no live network."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.ratings.models import CatalogTitle
from factory.ratings.stage5_constants import CANDIDATE_CAP, RATE_LIMIT_RPS, SOURCE_ALLOWED
from factory.ratings.stage5_policy import (
    UnauthorizedSourceError,
    assert_live_source_allowed,
    source_isolation_gates,
)
from factory.ratings.stage5_queue import build_priority_queue, classify_tier, replay_digest
from factory.ratings.stage5_sim import run_31_day_simulation
from factory.ratings.store import RatingsStore


def test_source_isolation_rejects_amd():
    with pytest.raises(UnauthorizedSourceError):
        assert_live_source_allowed("amd_online")
    with pytest.raises(UnauthorizedSourceError):
        assert_live_source_allowed("animemedia")
    assert assert_live_source_allowed("shikimori") == "shikimori"
    g = source_isolation_gates()
    assert g["ACTIVE_SOURCE_COUNT"] == 1
    assert g["ACTIVE_SOURCE"] == SOURCE_ALLOWED
    assert g["SOURCE_RATE_LIMIT_RPS"] == RATE_LIMIT_RPS
    assert g["SOURCE_CONCURRENCY"] == 1


def test_priority_tier_order():
    ongoing = CatalogTitle(canonical_title_id="a", is_ongoing=True)
    season = CatalogTitle(canonical_title_id="b", is_seasonal=True, kind="tv", days_since_release=60)
    new30 = CatalogTitle(canonical_title_id="c", days_since_release=10)
    assert classify_tier(ongoing)[0] > classify_tier(season)[0] > classify_tier(new30)[0]


def test_queue_excludes_covered_and_caps(tmp_path: Path):
    catalog = tmp_path / "cat.json"
    items = []
    for i in range(20):
        items.append(
            {
                "id": f"t{i}",
                "name": f"Title {i}",
                "year": 2024,
                "type": "tv",
                "external_ids": {"myanimelist": str(1000 + i)},
                "is_popular": i < 3,
                "created_at": "2026-09-01T00:00:00Z",
            }
        )
    catalog.write_text(json.dumps(items), encoding="utf-8")
    db = tmp_path / "r.sqlite"
    store = RatingsStore(db)
    # Mark first title covered
    store.conn.execute(
        """INSERT INTO rating_current (
            canonical_title_id, source_key, normalized_score, vote_count, freshness,
            payload_sha256, observed_at)
           VALUES ('nova:t0','shikimori',8.1,10,'FRESH','x','2026-09-19T00:00:00Z')"""
    )
    store.conn.commit()

    q = build_priority_queue(
        catalog_path=catalog,
        store=store,
        candidate_cap=10,
        accepted_target=100,
        run_id="test-run",
        frozen_catalog_digest="abc",
    )
    assert q["QUEUE_SOURCE"] == "shikimori"
    assert q["QUEUE_CANDIDATE_COUNT"] <= 10
    assert q["QUEUE_DUPLICATE_IDS"] == 0
    assert q["QUEUE_COVERED_TITLE_COUNT"] == 0
    assert "nova:t0" not in q["candidate_ids"]
    assert replay_digest(q) == q["queue_digest"]
    store.close()


def test_queue_cap_150(tmp_path: Path):
    catalog = tmp_path / "cat.json"
    items = [
        {
            "id": f"x{i}",
            "name": f"X {i}",
            "year": 2020,
            "type": "tv",
            "external_ids": {"myanimelist": str(i + 1)},
        }
        for i in range(200)
    ]
    catalog.write_text(json.dumps(items), encoding="utf-8")
    q = build_priority_queue(
        catalog_path=catalog,
        store=None,
        candidate_cap=CANDIDATE_CAP,
        run_id="cap",
    )
    assert q["QUEUE_CANDIDATE_COUNT"] == CANDIDATE_CAP
    assert len(set(q["candidate_ids"])) == CANDIDATE_CAP


def test_fuzzy_not_auto_queued(tmp_path: Path):
    catalog = tmp_path / "cat.json"
    # No external ids → unmatched, not queued
    catalog.write_text(
        json.dumps([{"id": "n1", "name": "No Map", "year": 2020, "type": "tv", "external_ids": {}}]),
        encoding="utf-8",
    )
    q = build_priority_queue(catalog_path=catalog, store=None, candidate_cap=150, run_id="fz")
    assert q["QUEUE_CANDIDATE_COUNT"] == 0
    assert q["skipped"]["no_external_id"] >= 1


def test_31_day_simulation_gates():
    sim = run_31_day_simulation(days=31, start_uncovered=500)
    assert sim["SIMULATION_DAYS"] == 31
    assert sim["SIMULATION_DAILY_LIMIT_VIOLATIONS"] == 0
    assert sim["SIMULATION_CANDIDATE_CAP_VIOLATIONS"] == 0
    assert sim["SIMULATION_DUPLICATE_OBSERVATIONS"] == 0
    assert sim["SIMULATION_OVERLAPPING_RUNS"] == 0
    assert sim["SIMULATION_CATCH_UP_BURSTS"] == 0
    assert sim["AMD_CALLS"] == 0
    assert sim["ok"] is True


def test_supervised_claim_limit_is_accepted_target():
    """Regression: Stage5 must claim ≤100, not the full 150 candidate cap."""
    import inspect

    from factory.ratings import stage5_supervised as mod
    from factory.ratings.stage5_constants import ACCEPTED_TARGET

    src = inspect.getsource(mod.block_06_supervised_cycle)
    assert "limit=ACCEPTED_TARGET" in src
    assert ACCEPTED_TARGET == 100
