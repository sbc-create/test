"""Tests for the versioned HF/MF/LF frequency-band policy."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from seo_operator.frequency_policy import (
    BandBoundary,
    FrequencyBand,
    FrequencyPolicy,
    Freshness,
    PolicyError,
    VolumeMeasurement,
    check_bands_are_contiguous,
    classify_frequency,
    compute_digest,
    load_policy,
    measurement_to_dict,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_POLICY_PATH = REPO_ROOT / "config" / "frequency-band-policy.json"
NOW = datetime(2026, 9, 17, tzinfo=timezone.utc)


def _policy(freshness_days: int = 90) -> FrequencyPolicy:
    bands = (
        BandBoundary(FrequencyBand.LF, 0, 1000),
        BandBoundary(FrequencyBand.MF, 1000, 10000),
        BandBoundary(FrequencyBand.HF, 10000, None),
    )
    return FrequencyPolicy(
        policy_id="test-policy",
        revision=1,
        supersedes_revision=None,
        digest="0" * 64,
        effective_from="2026-01-01T00:00:00Z",
        region="213",
        searchers=("yandex", "google"),
        freshness_max_age_days=freshness_days,
        bands=bands,
    )


def _measurement(value, *, days_old=0, source="yandex_webmaster", region="213", searcher="yandex"):
    measured_at = None
    if value is not None:
        measured_at = (NOW - timedelta(days=days_old)).isoformat()
    return VolumeMeasurement(value=value, source=source, measured_at=measured_at, region=region, searcher=searcher)


class TestBandBoundaries:
    def test_low_frequency(self):
        band, freshness, _ = classify_frequency(_measurement(500), _policy(), now=NOW)
        assert band is FrequencyBand.LF
        assert freshness is Freshness.FRESH

    def test_mid_frequency(self):
        band, _, _ = classify_frequency(_measurement(5000), _policy(), now=NOW)
        assert band is FrequencyBand.MF

    def test_high_frequency_open_ended(self):
        band, _, _ = classify_frequency(_measurement(1_000_000), _policy(), now=NOW)
        assert band is FrequencyBand.HF

    def test_boundary_is_exclusive_upper_inclusive_lower(self):
        # exactly 1000 belongs to MF, not LF: LF's upper bound is exclusive.
        band, _, _ = classify_frequency(_measurement(1000), _policy(), now=NOW)
        assert band is FrequencyBand.MF


class TestUnknownOnMissingOrStale:
    def test_missing_volume_is_unknown_not_zero(self):
        band, freshness, reason = classify_frequency(
            _measurement(None), _policy(), now=NOW
        )
        assert band is FrequencyBand.UNKNOWN
        assert freshness is Freshness.MISSING
        assert "0" not in reason.split()  # never phrased as a zero

    def test_stale_volume_is_unknown_not_its_last_band(self):
        # A high-volume reading from 200 days ago, with a 90-day freshness window.
        band, freshness, reason = classify_frequency(
            _measurement(1_000_000, days_old=200), _policy(freshness_days=90), now=NOW
        )
        assert band is FrequencyBand.UNKNOWN
        assert freshness is Freshness.STALE
        assert "200" in reason

    def test_fresh_boundary_is_inclusive(self):
        band, freshness, _ = classify_frequency(
            _measurement(500, days_old=90), _policy(freshness_days=90), now=NOW
        )
        assert freshness is Freshness.FRESH
        assert band is FrequencyBand.LF

    def test_measurement_to_dict_never_substitutes_zero(self):
        d = measurement_to_dict(_measurement(None), Freshness.MISSING)
        assert d["value"] is None
        assert d["measured_at"] is None
        assert d["freshness"] == "MISSING"


class TestPolicyIsVersionedNotHardcoded:
    def test_default_policy_loads_and_validates(self):
        policy = load_policy(DEFAULT_POLICY_PATH)
        assert policy.revision == 1
        assert policy.policy_id
        assert len(policy.bands) == 3

    def test_tampered_policy_file_is_rejected_by_digest(self, tmp_path):
        import json

        data = json.loads(DEFAULT_POLICY_PATH.read_text(encoding="utf-8"))
        data["freshness_max_age_days"] = 999  # edited without recomputing digest
        tampered = tmp_path / "tampered.json"
        tampered.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(PolicyError, match="digest"):
            load_policy(tampered)

    def test_a_new_revision_produces_a_reproducible_diff(self):
        import json

        data = json.loads(DEFAULT_POLICY_PATH.read_text(encoding="utf-8"))
        revision_2 = dict(data)
        revision_2["revision"] = 2
        revision_2["supersedes_revision"] = data["revision"]
        revision_2["bands"] = [
            {"name": "LF", "min_monthly_volume": 0, "max_monthly_volume": 2000},
            {"name": "MF", "min_monthly_volume": 2000, "max_monthly_volume": 20000},
            {"name": "HF", "min_monthly_volume": 20000, "max_monthly_volume": None},
        ]
        revision_2.pop("digest", None)
        digest_2 = compute_digest(revision_2)
        assert digest_2 != data["digest"], "a boundary change must change the digest"

    def test_gap_between_bands_is_rejected(self):
        bands = (
            BandBoundary(FrequencyBand.LF, 0, 900),
            BandBoundary(FrequencyBand.MF, 1000, 10000),  # gap: 900..1000 uncovered
            BandBoundary(FrequencyBand.HF, 10000, None),
        )
        with pytest.raises(PolicyError, match="gap or overlap"):
            check_bands_are_contiguous(bands)

    def test_overlap_between_bands_is_rejected(self):
        bands = (
            BandBoundary(FrequencyBand.LF, 0, 1100),
            BandBoundary(FrequencyBand.MF, 1000, 10000),  # overlap: 1000..1100
            BandBoundary(FrequencyBand.HF, 10000, None),
        )
        with pytest.raises(PolicyError, match="gap or overlap"):
            check_bands_are_contiguous(bands)

    def test_missing_band_is_rejected(self):
        bands = (
            BandBoundary(FrequencyBand.LF, 0, 10000),
            BandBoundary(FrequencyBand.HF, 10000, None),
        )
        with pytest.raises(PolicyError, match="exactly LF, MF and HF"):
            check_bands_are_contiguous(bands)


class TestFreshnessSourcedFields:
    def test_measurement_always_carries_source_region_searcher(self):
        m = _measurement(None, source="google_search_console", region="213", searcher="google")
        assert m.source == "google_search_console"
        assert m.region == "213"
        assert m.searcher == "google"
