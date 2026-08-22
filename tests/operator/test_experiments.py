"""Experiment lifecycle, canary scope and keep/rollback decision tests."""

from __future__ import annotations

import pytest

from seo_operator.audit import Change, ChangeKind
from seo_operator.experiments import (
    CanaryScopeError,
    Experiment,
    Observation,
    Verdict,
    decide,
)


def make_experiment(**kw):
    defaults = {
        "hypothesis": "Добавление сезона в title повысит CTR карточек сериалов",
        "site_id": "site-a",
        "primary_metric": "ctr",
        "scope_pages": 8,
        "site_total_pages": 100,
    }
    defaults.update(kw)
    return Experiment(**defaults)


def test_experiment_requires_hypothesis():
    with pytest.raises(ValueError, match="гипотезы"):
        make_experiment(hypothesis="")


def test_experiment_requires_primary_metric():
    with pytest.raises(ValueError, match="метрика"):
        make_experiment(primary_metric="")


class TestCanaryScope:
    def test_within_limits_ok(self):
        make_experiment(scope_pages=8, site_total_pages=100).validate_canary_scope()

    def test_page_share_over_10_percent_rejected(self):
        exp = make_experiment(scope_pages=11, site_total_pages=100)
        with pytest.raises(CanaryScopeError, match="страниц"):
            exp.validate_canary_scope()

    def test_multi_site_rollout_rejected(self):
        """The 'no mass change across all sites without canary' rule."""
        exp = make_experiment(scope_pages=5, site_total_pages=100)
        with pytest.raises(CanaryScopeError, match="сайтов"):
            exp.validate_canary_scope(sites_touched=15)

    def test_boundary_exactly_10_percent_allowed(self):
        make_experiment(scope_pages=10, site_total_pages=100).validate_canary_scope()


class TestDecision:
    def test_guardrail_breach_rolls_back_immediately(self):
        verdict, why = decide(
            Observation(
                days_elapsed=1, impressions=10, primary_metric_delta=0.5, guardrail_breached=True
            )
        )
        assert verdict is Verdict.ROLLBACK
        assert "guardrail" in why

    def test_regression_rolls_back_even_early(self):
        verdict, _ = decide(Observation(days_elapsed=2, impressions=50, primary_metric_delta=-0.09))
        assert verdict is Verdict.ROLLBACK

    def test_immature_data_continues(self):
        verdict, _ = decide(
            Observation(days_elapsed=3, impressions=5000, primary_metric_delta=0.20)
        )
        assert verdict is Verdict.CONTINUE

    def test_small_sample_is_insufficient_not_a_keep(self):
        verdict, _ = decide(
            Observation(days_elapsed=21, impressions=120, primary_metric_delta=0.40)
        )
        assert verdict is Verdict.INSUFFICIENT_DATA

    def test_clear_improvement_is_kept(self):
        verdict, _ = decide(
            Observation(days_elapsed=21, impressions=8000, primary_metric_delta=0.12)
        )
        assert verdict is Verdict.KEEP

    def test_flat_result_is_rolled_back_not_kept(self):
        """An unproven change does not get to stay."""
        verdict, why = decide(
            Observation(days_elapsed=21, impressions=8000, primary_metric_delta=0.01)
        )
        assert verdict is Verdict.ROLLBACK
        assert "не достиг порога" in why


def test_rollback_payloads_are_reverse_order():
    exp = make_experiment()
    exp.changes = [
        Change(
            site_id="site-a",
            entity_id="e1",
            kind=ChangeKind.TITLE,
            field_name="title",
            before="A",
            after="B",
            reason="r1",
        ),
        Change(
            site_id="site-a",
            entity_id="e2",
            kind=ChangeKind.H1,
            field_name="h1",
            before="C",
            after="D",
            reason="r2",
        ),
    ]
    payloads = exp.rollback_payloads()
    assert [p["entity_id"] for p in payloads] == ["e2", "e1"]
    assert payloads[0]["restore_value"] == "C"
