"""Аллокация, зрелость, stop-loss, конфаундеры, keep/rollback."""
from datetime import date, timedelta

import pytest

from seo_operator.experiments.allocator import Allocator, split_cohort
from seo_operator.experiments.evaluator import (check_maturity, check_stop_loss,
                                                detect_confounders, evaluate)
from seo_operator.experiments.registry import Experiment, ExperimentRegistry
from seo_operator.guardrails import GuardrailViolation


def _exp(**kw):
    base = dict(
        id="EXP-20260822-demo-fixture-001", site_id="demo-fixture",
        hypothesis="Уточнение title повысит CTR на страницах тайтлов.",
        evidence="CTR на 40% ниже ожидаемого для позиции 6-8 в 120 запросах.",
        primary_variable="title_template", primary_kpi="clicks",
        baseline_start="2026-07-01", baseline_end="2026-07-28",
        guardrails=["indexed_coverage_drop", "soft_404_rate"],
        stop_loss={"clicks": 20}, min_sample={"clicks": 40},
        page_type="title", query_cohort="exact_title",
        rollback_payload={"executable": True, "kind": "cms_restore", "site_id": "demo-fixture"},
        before_snapshot={"title": "old"})
    base.update(kw)
    return Experiment(**base)


@pytest.fixture()
def registry(store):
    return ExperimentRegistry(store)


# --- валидация ----------------------------------------------------------------

@pytest.mark.parametrize("field,value", [
    ("hypothesis", ""),
    ("evidence", ""),
    ("primary_variable", ""),
    ("stop_loss", {}),
    ("guardrails", []),
    ("rollback_payload", None),
    ("before_snapshot", None),
])
def test_incomplete_experiment_is_rejected(registry, field, value):
    with pytest.raises(GuardrailViolation):
        registry.create(_exp(**{field: value}))


def test_unmarked_secondary_change_rejected(registry):
    with pytest.raises(GuardrailViolation):
        registry.create(_exp(secondary_changes=["also changed h1"]))


def test_inseparable_secondary_change_allowed(registry):
    registry.create(_exp(secondary_changes=["inseparable:h1 меняется тем же шаблоном"]))


def test_valid_experiment_is_created_and_started(registry):
    registry.create(_exp())
    started = registry.start("EXP-20260822-demo-fixture-001", today=date(2026, 8, 22))
    assert started.status == "running"
    assert started.ends_at == (date(2026, 8, 22) + timedelta(days=21)).isoformat()


# --- аллокация ----------------------------------------------------------------

def test_cohort_split_is_deterministic(isolated_state):
    urls = [f"/title/{i}" for i in range(500)]
    a, ha = split_cohort(urls, 0.08, "salt", 0.08)
    b, hb = split_cohort(urls, 0.08, "salt", 0.08)
    assert a == b and ha == hb
    assert not (set(a) & set(ha)), "Treatment и holdout не пересекаются"
    assert 0.05 <= len(a) / len(urls) <= 0.12


def test_allocator_respects_site_concurrency(registry):
    alloc = Allocator(registry)
    for i in range(3):
        registry.create(_exp(id=f"E{i}", page_type=f"t{i}"))
        registry.start(f"E{i}")
    assert alloc.can_start("demo-fixture", page_type="other").allowed is False


def test_allocator_respects_page_type_limit(registry):
    alloc = Allocator(registry)
    for i in range(2):
        registry.create(_exp(id=f"E{i}", page_type="title"))
        registry.start(f"E{i}")
    decision = alloc.can_start("demo-fixture", page_type="title")
    assert not decision.allowed and "тип страниц" in decision.reason


def test_allocator_blocks_when_incident_open(registry, store):
    store.open_incident("INC-1", "demo-fixture", "SC-01", "high", "падение")
    assert not Allocator(registry).can_start("demo-fixture", "title").allowed


def test_allocation_requires_holdout(registry):
    alloc = Allocator(registry)
    decision = alloc.allocate("demo-fixture", ["/only-one-page"], page_type="title")
    assert not decision.allowed


def test_allocation_produces_treatment_and_holdout(registry):
    alloc = Allocator(registry)
    urls = [f"/title/{i}" for i in range(400)]
    decision = alloc.allocate("demo-fixture", urls, page_type="title")
    assert decision.allowed and decision.cohort and decision.holdout


def test_rollout_steps_are_gradual(registry):
    alloc = Allocator(registry)
    assert alloc.rollout_step(0.08) == 0.25
    assert alloc.rollout_step(1.0) is None


# --- зрелость -----------------------------------------------------------------

def _rows(start: date, days: int, clicks=10, impressions=300):
    return [{"date": (start + timedelta(days=i)).isoformat(), "clicks": clicks,
             "impressions": impressions, "value": clicks, "completeness": 1.0}
            for i in range(days)]


def test_young_experiment_is_not_evaluated(isolated_state):
    exp = _exp(started_at="2026-08-20")
    m = check_maturity(exp, _rows(date(2026, 8, 20), 2), today=date(2026, 8, 22))
    assert not m.mature


def test_low_volume_experiment_is_not_mature(isolated_state):
    exp = _exp(started_at="2026-07-01")
    m = check_maturity(exp, _rows(date(2026, 7, 1), 40, clicks=0, impressions=1),
                       today=date(2026, 8, 22))
    assert not m.mature
    assert any("Показов" in r or "Кликов" in r for r in m.reasons)


def test_mature_experiment_passes(isolated_state):
    exp = _exp(started_at="2026-07-01")
    m = check_maturity(exp, _rows(date(2026, 7, 1), 50), today=date(2026, 8, 22))
    assert m.mature, m.reasons


def test_data_lag_is_subtracted_from_observation(isolated_state):
    exp = _exp(started_at="2026-08-01")
    m = check_maturity(exp, _rows(date(2026, 8, 1), 21), today=date(2026, 8, 22))
    assert m.observed_days == 18   # 21 календарный день минус 3 дня задержки GSC


# --- stop-loss и конфаундеры --------------------------------------------------

def test_stop_loss_triggers_on_deep_drop(isolated_state):
    triggered, breaches = check_stop_loss(_exp(), {"clicks": -35}, {})
    assert triggered and breaches


def test_stop_loss_ignores_small_move(isolated_state):
    triggered, _ = check_stop_loss(_exp(), {"clicks": -5}, {})
    assert not triggered


def test_guardrail_breach_triggers_stop(isolated_state):
    triggered, breaches = check_stop_loss(_exp(), {}, {"indexed_coverage_drop": True})
    assert triggered and "indexed_coverage_drop" in breaches[0]


@pytest.mark.parametrize("context,expected", [
    ({"algorithm_update_window": True}, "algorithm_update"),
    ({"incident_ids": ["INC-1"]}, "incident"),
    ({"seasonality_zscore": 3.1}, "seasonality"),
    ({"competitor_release_event": True}, "competitor_or_release_event"),
    ({"deploy_in_window": True}, "deploy"),
])
def test_confounders_are_detected(isolated_state, context, expected):
    found = detect_confounders(_exp(), context)
    assert any(expected in f for f in found)


# --- решения ------------------------------------------------------------------

def test_immature_experiment_is_inconclusive(isolated_state):
    exp = _exp(started_at="2026-08-20")
    ev = evaluate(exp, _rows(date(2026, 8, 20), 2), [], {}, {}, today=date(2026, 8, 22))
    assert ev.decision == "inconclusive" and "не созрели" in ev.explanation


def test_guardrail_breach_forces_rollback(isolated_state):
    exp = _exp(started_at="2026-07-01")
    ev = evaluate(exp, _rows(date(2026, 7, 1), 50), [], {"soft_404_rate": 12}, {},
                  today=date(2026, 8, 22))
    assert ev.decision == "rollback" and ev.stop_loss_triggered


def test_confounded_result_is_not_claimed_as_success(isolated_state):
    exp = _exp(started_at="2026-07-01")
    treatment = _rows(date(2026, 7, 1), 25, clicks=10) + _rows(date(2026, 7, 26), 25, clicks=30)
    ev = evaluate(exp, treatment, [], {},
                  {"algorithm_update_window": True, "incident_ids": ["INC-1"],
                   "seasonality_zscore": 3.5, "competitor_release_event": True},
                  today=date(2026, 8, 22))
    assert ev.decision == "inconclusive"
    assert ev.confounders


def test_flat_result_is_not_kept(isolated_state):
    exp = _exp(started_at="2026-07-01")
    ev = evaluate(exp, _rows(date(2026, 7, 1), 50, clicks=20), _rows(date(2026, 7, 1), 50, clicks=20),
                  {}, {}, today=date(2026, 8, 22))
    assert ev.decision == "inconclusive"


def test_control_absorbs_seasonality(isolated_state):
    """Рост и в treatment, и в control — это сезон, а не эффект эксперимента."""
    exp = _exp(started_at="2026-07-01")
    rise = _rows(date(2026, 6, 20), 30, clicks=10) + _rows(date(2026, 7, 20), 34, clicks=20)
    ev = evaluate(exp, rise, rise, {}, {}, today=date(2026, 8, 22))
    assert ev.lift_pct is not None and abs(ev.lift_pct) < 1
    assert ev.decision == "inconclusive"


def test_freeze_affects_only_target_site(registry, store):
    registry.create(_exp(id="E-A", site_id="demo-fixture"))
    registry.start("E-A")
    frozen = registry.freeze("demo-fixture", "SC-01")
    assert frozen == ["E-A"]
    assert registry.get("E-A").status == "frozen"
