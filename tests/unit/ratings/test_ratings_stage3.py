"""Unit tests for Stage 3 coverage, scheduler, queue gates, qwen sanitize."""

from __future__ import annotations

import json
from pathlib import Path

from factory.ratings.coverage_policy import (
    FINAL_DAILY_ACCEPTED_TARGET,
    STAGE3_ACCEPTED_TARGET,
    STAGE3_CANDIDATE_CAP,
    compute_daily_target,
    is_covered_row,
    zero_score_retry_after,
)
from factory.ratings.formula import FORMULA_VERSION, combine_amd_local
from factory.ratings.qwen_report import QWEN_PERMISSIONS, sanitize_report, write_qwen_report
from factory.ratings.scheduler import (
    DEFAULT_STATE,
    SchedulerConfig,
    assert_disabled,
    save_scheduler,
)
from factory.ratings.secrets import redact_headers


def test_stage3_and_final_gates():
    assert STAGE3_ACCEPTED_TARGET == 100
    assert STAGE3_CANDIDATE_CAP == 150
    assert FINAL_DAILY_ACCEPTED_TARGET == 500


def test_coverage_target_full():
    t = compute_daily_target(eligible_total=200, covered_valid=200)
    assert t.daily_accepted_target == 0
    assert t.full_coverage


def test_coverage_target_partial_remainder():
    t = compute_daily_target(eligible_total=100, covered_valid=80, accepted_cap=500)
    assert t.eligible_uncovered == 20
    assert t.daily_accepted_target == 20


def test_coverage_target_capped_at_500():
    t = compute_daily_target(eligible_total=5000, covered_valid=100)
    assert t.daily_accepted_target == 500


def test_zero_score_not_covered():
    assert not is_covered_row(score=0, vote_count=0)
    assert not is_covered_row(score=None, vote_count=None)
    assert is_covered_row(score=9.5, vote_count=10)


def test_zero_score_retry_seven_days():
    after = zero_score_retry_after("2026-09-19T00:00:00Z")
    assert after.startswith("2026-09-26")


def test_scheduler_default_disabled(tmp_path):
    path = tmp_path / "sched.json"
    save_scheduler(SchedulerConfig(state="ENABLED", current_daily_limit=100), path)
    data = json.loads(path.read_text())
    assert data["state"] == "DISABLED"
    assert data["current_daily_limit"] == 0
    st = assert_disabled()
    assert st["SCHEDULER_ENABLED"] == "NO"
    assert DEFAULT_STATE == "DISABLED"


def test_blend_policy_version_retained():
    assert FORMULA_VERSION == "animedia_blend_v1"
    r = combine_amd_local(amd_score="9.0", amd_vote_count=50, accepted_local_vote_sum=0, accepted_local_vote_count=0)
    assert r.combined_ui == "9.00"


def test_qwen_proposal_only_and_redaction(tmp_path):
    assert QWEN_PERMISSIONS["may_write_db"] is False
    assert QWEN_PERMISSIONS["may_enable_scheduler"] is False
    dirty = {"run_id": "x", "token": "secret", "Authorization": "Bearer x", "accepted": 1}
    clean = sanitize_report(dirty)
    assert clean["token"] == "***REDACTED***"
    paths = write_qwen_report({"run_id": "t", "accepted": 1, "password": "nope"}, tmp_path)
    assert paths["delivery"] == "BLOCKED_NO_CONFIG"
    body = json.loads(Path(paths["json"]).read_text())
    assert body["password"] == "***REDACTED***"
    assert body["QWEN_WRITE_PERMISSIONS"] == 0


def test_secret_header_redaction():
    red = redact_headers({"Authorization": "Bearer abc", "User-Agent": "x"})
    assert "abc" not in json.dumps(red)


def test_shadow_plan_dedupe():
    from factory.ratings.stage3_canary import shadow_plan

    urls = [
        "https://amd.online/2-b.html",
        "https://amd.online/1-a.html",
        "https://amd.online/1-a.html",
    ]
    plan = shadow_plan(urls, cap=150)
    assert len(plan) == 2
    assert [p["external_id"] for p in plan] == ["2", "1"]


def test_backlog_aging_stable_tiebreak():
    from factory.ratings.queue import apply_backlog_aging

    items = [(9, "archive", "amd_online:b"), (9, "archive", "amd_online:a")]
    aged = apply_backlog_aging(items, age_days={"amd_online:a": 30, "amd_online:b": 0})
    # a boosted above b
    assert aged[0][2] == "amd_online:a"
    assert aged[0][0] < 9
