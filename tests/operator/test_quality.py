"""Data quality gate tests."""

from __future__ import annotations

import pytest

from seo_operator.datasources.base import Availability, SourceStatus
from seo_operator.quality import (
    GateResult,
    MetricRedactionError,
    evaluate,
    guard_metric,
    safe_metric,
)

OK = Availability(SourceStatus.AVAILABLE, "ok")
GONE = Availability(SourceStatus.MISSING_CREDENTIALS, "нет токена")


def test_no_sources_fails_closed():
    report = evaluate({"google_search_console": GONE, "yandex_webmaster": GONE})
    assert report.result is GateResult.FAIL
    assert not report.can_publish_metrics


def test_all_search_sources_missing_fails():
    report = evaluate({"google_search_console": GONE, "yandex_webmaster": GONE, "cms": OK})
    assert report.result is GateResult.FAIL


def test_one_search_source_present_is_degraded():
    report = evaluate({"google_search_console": OK, "yandex_webmaster": GONE})
    assert report.result is GateResult.DEGRADED
    assert report.can_publish_metrics


def test_everything_present_passes():
    report = evaluate({"google_search_console": OK, "yandex_webmaster": OK})
    assert report.result is GateResult.PASS


def test_metric_from_unavailable_source_raises():
    report = evaluate({"google_search_console": OK, "yandex_webmaster": GONE})
    with pytest.raises(MetricRedactionError):
        guard_metric("yandex_clicks", 0, report, "yandex_webmaster")


def test_metric_from_available_source_passes_through():
    report = evaluate({"google_search_console": OK, "yandex_webmaster": OK})
    assert guard_metric("clicks", 512, report, "google_search_console") == 512


def test_safe_metric_marks_unmeasured_rather_than_zero():
    """The regression this guards: absence rendering as 0."""
    report = evaluate({"google_search_console": OK, "yandex_webmaster": GONE})
    result = safe_metric("yandex_clicks", 0, report, "yandex_webmaster")
    assert result["measured"] is False
    assert result["value"] is None
    assert result["value"] != 0
