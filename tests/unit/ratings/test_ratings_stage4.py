"""Stage 4 unit tests — coverage, policy, restore, qwen outbox, pilot closeout."""

from __future__ import annotations

import json

from factory.ratings.coverage_policy import compute_daily_target
from factory.ratings.db_hardening import restore_drill
from factory.ratings.global_coverage import build_global_inventory
from factory.ratings.pilot import (
    PilotConfig,
    coverage_aware_target,
    deterministic_cycle_id,
    should_auto_stop,
)
from factory.ratings.qwen_delivery import discover_config, enqueue_and_dry_run
from factory.ratings.source_policy import amd_policy, gate_summary, shikimori_policy
from factory.ratings.stage4_closeout import evaluate_closeout
from factory.ratings.store import RatingsStore


def test_amd_disabled_permission_missing():
    p = amd_policy()
    assert p.decision == "AMD_SOURCE_DISABLED_PERMISSION_MISSING"
    assert p.new_fetches_allowed is False
    assert p.permission_status == "NOT_PROVIDED"


def test_shikimori_policy_resolved_no_html():
    p = shikimori_policy()
    assert "SHIKIMORI_SOURCE_POLICY_RESOLVED" in p.decision
    assert p.access_method == "official_graphql"
    assert "html_fallback" not in p.challenge_policy.lower() or "no_html_fallback" in p.challenge_policy


def test_source_gate_authorized_or_disabled():
    g = gate_summary()
    assert g["AMD_SOURCE_AUTHORIZED_OR_DISABLED"] == "YES"
    assert g["SHIKIMORI_SOURCE_POLICY_RESOLVED"] == "YES"


def test_global_inventory_not_canary_denominator(tmp_path):
    # tiny catalog fixture
    catalog = tmp_path / "cat.json"
    catalog.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "external_id": "1",
                        "name": "A",
                        "year": 2020,
                        "is_series": True,
                        "external_ids": {"myanimelist": "10"},
                        "created_at": "2026-09-01T00:00:00Z",
                    },
                    {
                        "external_id": "2",
                        "name": "B",
                        "year": 2010,
                        "is_series": False,
                        "external_ids": {},
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    db = tmp_path / "r.sqlite"
    RatingsStore(db).close()
    inv = build_global_inventory(catalog_path=catalog, db_path=db)
    assert inv["GLOBAL_TITLE_TOTAL"] == 2
    assert inv["SHIKIMORI_ELIGIBLE_TOTAL"] == 1
    assert inv["STAGE3_CANARY_COHORT_NOT_GLOBAL"] is True
    assert inv["GLOBAL_TITLE_TOTAL"] != 150


def test_coverage_aware_daily_shortfall_ok():
    t = coverage_aware_target(uncovered=12, due_refresh=0, cap=100)
    assert t["effective_target"] == 12
    assert t["shortfall_allowed"] is True


def test_compute_daily_full_coverage_zero_target():
    c = compute_daily_target(eligible_total=100, covered_valid=100)
    assert c.daily_accepted_target == 0


def test_qwen_outbox_dry_run_and_dedupe(tmp_path):
    db = tmp_path / "outbox.sqlite"
    r1 = enqueue_and_dry_run(outbox_db=db, report={"run_id": "a", "accepted": 0}, cycle_id="c1")
    r2 = enqueue_and_dry_run(outbox_db=db, report={"run_id": "a", "accepted": 0}, cycle_id="c1")
    assert r1["QWEN_DRY_RUN_RECEIPT_PASS"] is True
    assert r2["duplicate"] is True
    assert discover_config()["QWEN_DELIVERY_CONFIGURED"] == "NO"


def test_pilot_auto_stop_after_seven():
    cfg = PilotConfig(cycles_completed=7)
    assert should_auto_stop(cfg) is True
    assert should_auto_stop(PilotConfig(cycles_completed=3)) is False


def test_deterministic_cycle_id_stable():
    a = deterministic_cycle_id("2026-09-19", "abc", 100)
    b = deterministic_cycle_id("2026-09-19", "abc", 100)
    assert a == b
    assert a != deterministic_cycle_id("2026-09-20", "abc", 100)


def test_restore_drill_on_isolated_copy(tmp_path):
    prod = tmp_path / "prod.sqlite"
    RatingsStore(prod).close()
    bak = tmp_path / "prod.bak"
    bak.write_bytes(prod.read_bytes())
    result = restore_drill(prod_db=prod, backup_path=bak, scratch_dir=tmp_path / "drill")
    assert result["DB_BACKUP_DIGEST_MATCH"] is True
    assert result["SQLITE_INTEGRITY_CHECK"] == "ok"
    assert result["DB_RESTORE_DRILL_PASS"] is True
    assert result["PRODUCTION_DB_MUTATED"] is False


def test_closeout_incomplete_without_seven_cycles(tmp_path):
    root = tmp_path
    (root / "var" / "ratings").mkdir(parents=True)
    cycles = tmp_path / "cycles.json"
    cycles.write_text(json.dumps({"cycles": []}), encoding="utf-8")
    out = evaluate_closeout(root, cycles)
    assert out["closeout_ready"] is False
    assert out["READY_FOR_DAILY_500"] is False
