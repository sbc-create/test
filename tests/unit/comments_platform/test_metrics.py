"""Metrics: split by tenant, site and version; free of user content."""

from __future__ import annotations

import json

import pytest

from factory.comments_platform.metrics import (
    ALLOWED_LABELS,
    COUNTERS,
    Metrics,
    Timer,
    observability_contract,
)
from factory.comments_platform.tenancy import TenantScope

LORDS = TenantScope("lords", "lords-main")
ZONA = TenantScope("zona", "zona-main")


class TestLabelling:
    def test_every_series_carries_tenant_site_and_version(self):
        metrics = Metrics()
        metrics.increment("api_requests_total", LORDS, operation="create")
        for series in metrics.series():
            for label in ("tenant_id", "site_id", "version"):
                assert label in series["labels"], f"{series['metric']} lacks {label}"

    def test_two_sites_do_not_share_a_counter(self):
        metrics = Metrics()
        metrics.increment("api_requests_total", LORDS, operation="create")
        metrics.increment("api_requests_total", ZONA, operation="create")
        assert metrics.value("api_requests_total", LORDS, operation="create") == 1
        assert metrics.value("api_requests_total", ZONA, operation="create") == 1

    def test_operations_are_distinguishable(self):
        metrics = Metrics()
        metrics.increment("api_requests_total", LORDS, operation="create")
        metrics.increment("api_requests_total", LORDS, operation="read")
        assert metrics.value("api_requests_total", LORDS, operation="read") == 1

    def test_scope_totals_cover_one_site_only(self):
        metrics = Metrics()
        metrics.increment("write_success_total", LORDS)
        metrics.increment("write_success_total", ZONA, value=5)
        assert metrics.scope_totals(LORDS)["write_success_total"] == 1


class TestNoContentInLabels:
    @pytest.mark.parametrize(
        "label,value",
        [
            ("body", "the text somebody wrote"),
            ("text", "the text somebody wrote"),
            ("subject_id", "g_abc123"),
            ("network_hmac", "n_abc123"),
            ("token", "secret"),
            ("email", "a@b.test"),
        ],
    )
    def test_a_disallowed_label_is_dropped(self, label, value):
        metrics = Metrics()
        metrics.increment("api_requests_total", LORDS, **{label: value})
        flat = json.dumps(metrics.series())
        # Neither the label name nor its value survives, and the counter still
        # increments: dropping a label must not drop the measurement.
        assert label not in ALLOWED_LABELS, f"{label} should not be an allowed label"
        assert label not in flat
        assert value not in flat
        assert metrics.value("api_requests_total", LORDS) == 1

    def test_an_allowed_label_with_an_address_in_it_is_dropped(self):
        metrics = Metrics()
        metrics.increment("api_requests_total", LORDS, code="https://leak.test/path")
        assert "leak.test" not in json.dumps(metrics.series())

    def test_a_long_label_value_is_dropped(self):
        metrics = Metrics()
        metrics.increment("api_requests_total", LORDS, reason_class="x" * 200)
        assert "xxxx" not in json.dumps(metrics.series())

    def test_a_short_classification_is_kept(self):
        metrics = Metrics()
        metrics.increment("moderation_outcomes_total", LORDS, outcome="hidden")
        assert metrics.value("moderation_outcomes_total", LORDS, outcome="hidden") == 1


class TestUnknownSeriesAreRefused:
    def test_an_unknown_counter_raises(self):
        with pytest.raises(ValueError):
            Metrics().increment("comments_vibes_total", LORDS)

    def test_an_unknown_histogram_raises(self):
        with pytest.raises(ValueError):
            Metrics().observe("api_vibes_ms", LORDS, 1.0)


class TestHistograms:
    def test_percentiles_are_reported(self):
        metrics = Metrics()
        for value in range(1, 101):
            metrics.observe("api_latency_ms", LORDS, float(value), operation="read")
        series = [s for s in metrics.series() if s["metric"] == "api_latency_ms"][0]
        assert series["count"] == 100
        assert 45 <= series["p50"] <= 55
        assert 90 <= series["p95"] <= 100

    def test_timer_records_something(self):
        metrics = Metrics()
        with Timer(metrics, "api_latency_ms", LORDS, operation="create"):
            pass
        series = [s for s in metrics.series() if s["metric"] == "api_latency_ms"][0]
        assert series["count"] == 1


class TestRequiredCoverage:
    @pytest.mark.parametrize(
        "required",
        [
            "api_errors_total", "read_success_total", "write_success_total",
            "moderation_outcomes_total", "idempotency_conflicts_total",
            "rate_limited_total", "widget_load_total", "widget_ready_total",
            "widget_error_total", "hydration_mismatch_total", "ssr_render_total",
            "ssr_timeout_total", "ssr_cache_hit_total", "js_error_free_sessions_total",
            "queue_depth", "kill_switch_engaged", "cross_tenant_attempts_total",
        ],
    )
    def test_the_brief_s_metric_exists(self, required):
        assert required in COUNTERS


class TestCrossTenantCounter:
    def test_it_exists_and_is_documented_as_p0(self):
        contract = observability_contract()
        assert contract["p0_signal"]["metric"] == "cross_tenant_attempts_total"
        assert "blocks rollout" in contract["p0_signal"]["rule"]

    def test_a_refused_probe_is_counted_per_site(self):
        metrics = Metrics()
        metrics.increment("cross_tenant_attempts_total", LORDS, outcome="refused")
        assert metrics.value("cross_tenant_attempts_total", LORDS, outcome="refused") == 1
        assert metrics.value("cross_tenant_attempts_total", ZONA, outcome="refused") == 0


class TestContract:
    def test_it_names_what_never_appears(self):
        contract = observability_contract()
        never = " ".join(contract["never_in_metrics"]).lower()
        for item in ("comment text", "subject", "token", "email", "raw ip"):
            assert item in never

    def test_it_is_serialisable(self):
        assert json.loads(json.dumps(observability_contract()))
