"""Tests for the approved_relevant_manifest contract: building, digesting,
determinism, and the fail-closed rules around it."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from seo_operator.approved_relevant_manifest import (
    EvidenceRef,
    ManifestError,
    build_entry,
    build_manifest,
    compute_digest,
    normalize_query,
    sync_eligible_entries,
    validate_manifest,
)
from seo_operator.frequency_policy import (
    FrequencyBand,
    Freshness,
    VolumeMeasurement,
    measurement_to_dict,
)
from seo_operator.priority import QueryClass
from seo_operator.relevance import OwnershipIndex, RelevanceInput, decide_relevance
from seo_operator.site_authority import KnownSite, SiteAuthority

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures"
NOW = datetime(2026, 9, 17, tzinfo=timezone.utc)


def _authority(ready: bool = True) -> SiteAuthority:
    return SiteAuthority(
        (
            KnownSite(site_id="lords-01", domain="lordfilm47.space", ready=ready),
            KnownSite(site_id="lords-02", domain="lordserial33.biz", ready=ready),
        )
    )


def _approved_entry(*, site_id="lords-01", domain="lordfilm47.space", query="боевики онлайн",
                     target_url="https://lordfilm47.space/genre/action", authority=None,
                     ownership=None):
    authority = authority or _authority()
    ownership = ownership if ownership is not None else OwnershipIndex()
    decision = decide_relevance(
        RelevanceInput(
            site_id=site_id, query=query, normalized_query=normalize_query(query),
            entity_id="genre-action", taxonomy_id="genre.action", intent=QueryClass.WATCH_INTENT,
            target_url=target_url, landing_page_taxonomy_id="genre.action",
            rendered_evidence_confirmed=True,
        ),
        ownership=ownership, now=NOW,
    )
    measurement = VolumeMeasurement(
        value=4400, source="yandex_webmaster", measured_at=NOW.isoformat(), region="213", searcher="yandex",
    )
    return build_entry(
        site_id=site_id, domain=domain, query=query, taxonomy_id="genre.action",
        intent=QueryClass.WATCH_INTENT, cluster="genre-action", frequency_band=FrequencyBand.MF,
        frequency_measurement=measurement_to_dict(measurement, Freshness.FRESH),
        target_url=target_url, relevance_decision=decision,
        evidence=(EvidenceRef("indexability_observation", "idx-001", "200, allowed, in sitemap",
                               NOW.isoformat()),),
        approved_by="seo-operator-dry-run", approved_at=NOW.isoformat(), created_at=NOW.isoformat(),
        site_authority=authority,
    )


class TestFailsClosedOnUnknownSiteOrDomain:
    def test_unknown_site_id_is_blocked(self):
        with pytest.raises(ManifestError, match="BLOCKED_INPUT"):
            _approved_entry(site_id="not-a-real-site")

    def test_known_site_wrong_domain_is_blocked(self):
        with pytest.raises(ManifestError, match="BLOCKED_INPUT"):
            _approved_entry(domain="example.com")

    def test_relevance_decision_must_be_a_real_decision_object(self):
        authority = _authority()
        measurement = VolumeMeasurement(
            value=100, source="yandex_webmaster", measured_at=NOW.isoformat(), region="213", searcher="yandex",
        )
        with pytest.raises(ManifestError, match="decide_relevance"):
            build_entry(
                site_id="lords-01", domain="lordfilm47.space", query="x", taxonomy_id="genre.action",
                intent=QueryClass.WATCH_INTENT, cluster="genre-action", frequency_band=FrequencyBand.LF,
                frequency_measurement=measurement_to_dict(measurement, Freshness.FRESH),
                target_url="https://lordfilm47.space/x",
                relevance_decision="APPROVED_RELEVANT",  # a bare string, not a RelevanceDecision
                evidence=(), approved_by="x", approved_at=NOW.isoformat(), created_at=NOW.isoformat(),
                site_authority=authority,
            )


class TestOnlyApprovedRelevantIsSyncEligible:
    def test_approved_with_evidence_and_ready_site_is_eligible(self):
        entry = _approved_entry(authority=_authority(ready=True))
        assert entry.sync_eligible is True

    def test_approved_but_site_not_ready_is_not_eligible(self):
        entry = _approved_entry(authority=_authority(ready=False))
        assert entry.sync_eligible is False

    def test_ambiguous_decision_is_never_sync_eligible(self):
        ownership = OwnershipIndex()
        # First claim it from a different site so the second is a conflict -> SUSPICIOUS.
        decide_relevance(
            RelevanceInput(
                site_id="lords-02", query="боевики онлайн", normalized_query="боевики онлайн",
                entity_id="genre-action", taxonomy_id="genre.action", intent=QueryClass.WATCH_INTENT,
                target_url="https://lordserial33.biz/genre/action", landing_page_taxonomy_id="genre.action",
                rendered_evidence_confirmed=True,
            ),
            ownership=ownership, now=NOW,
        )
        conflicted_decision = decide_relevance(
            RelevanceInput(
                site_id="lords-01", query="боевики онлайн", normalized_query="боевики онлайн",
                entity_id="genre-action", taxonomy_id="genre.action", intent=QueryClass.WATCH_INTENT,
                target_url="https://lordfilm47.space/genre/action", landing_page_taxonomy_id="genre.action",
                rendered_evidence_confirmed=True,
            ),
            ownership=ownership, now=NOW,
        )
        measurement = VolumeMeasurement(
            value=100, source="yandex_webmaster", measured_at=NOW.isoformat(), region="213", searcher="yandex",
        )
        entry = build_entry(
            site_id="lords-01", domain="lordfilm47.space", query="боевики онлайн",
            taxonomy_id="genre.action", intent=QueryClass.WATCH_INTENT, cluster="genre-action",
            frequency_band=FrequencyBand.LF, frequency_measurement=measurement_to_dict(measurement, Freshness.FRESH),
            target_url="https://lordfilm47.space/genre/action", relevance_decision=conflicted_decision,
            evidence=(EvidenceRef("manual_review", "mr-1", "reviewed", NOW.isoformat()),),
            approved_by="x", approved_at=NOW.isoformat(), created_at=NOW.isoformat(),
            site_authority=_authority(ready=True),
        )
        assert entry.sync_eligible is False


class TestDeterministicDigest:
    def test_same_entries_different_build_order_same_digest(self):
        e1 = _approved_entry(query="боевики онлайн", target_url="https://lordfilm47.space/genre/action")
        e2 = _approved_entry(
            site_id="lords-02", domain="lordserial33.biz", query="сериалы онлайн",
            target_url="https://lordserial33.biz/genre/series",
        )
        m1 = build_manifest(
            [e1, e2], manifest_id="m", version=1, revision=1, generated_at=NOW.isoformat(),
            site_authority=_authority(), band_policy_revision=1,
        )
        m2 = build_manifest(
            [e2, e1], manifest_id="m", version=1, revision=1, generated_at=NOW.isoformat(),
            site_authority=_authority(), band_policy_revision=1,
        )
        assert m1["digest"] == m2["digest"]
        assert m1["entries"] == m2["entries"]  # order is normalized, not just the hash

    def test_digest_changes_when_content_changes(self):
        e1 = _approved_entry()
        m1 = build_manifest(
            [e1], manifest_id="m", version=1, revision=1, generated_at=NOW.isoformat(),
            site_authority=_authority(), band_policy_revision=1,
        )
        e2 = _approved_entry(query="другой запрос")
        m2 = build_manifest(
            [e2], manifest_id="m", version=1, revision=1, generated_at=NOW.isoformat(),
            site_authority=_authority(), band_policy_revision=1,
        )
        assert m1["digest"] != m2["digest"]

    def test_compute_digest_ignores_the_digest_field_itself(self):
        doc = {"a": 1, "digest": "irrelevant"}
        doc_no_digest = {"a": 1}
        assert compute_digest(doc) == compute_digest(doc_no_digest)


class TestSchemaValidation:
    def test_valid_fixture_has_no_problems(self):
        data = json.loads((FIXTURE_DIR / "approved-relevant-manifest.valid.json").read_text())
        assert validate_manifest(data) == []

    def test_invalid_fixture_is_rejected(self):
        data = json.loads((FIXTURE_DIR / "approved-relevant-manifest.invalid.json").read_text())
        problems = validate_manifest(data)
        assert problems

    def test_built_manifest_validates_cleanly(self):
        e1 = _approved_entry()
        manifest = build_manifest(
            [e1], manifest_id="live-check", version=1, revision=1, generated_at=NOW.isoformat(),
            site_authority=_authority(), band_policy_revision=1,
        )
        assert validate_manifest(manifest) == []

    def test_tampered_digest_is_caught(self):
        e1 = _approved_entry()
        manifest = build_manifest(
            [e1], manifest_id="live-check", version=1, revision=1, generated_at=NOW.isoformat(),
            site_authority=_authority(), band_policy_revision=1,
        )
        manifest["digest"] = "0" * 64
        problems = validate_manifest(manifest)
        assert any("digest mismatch" in p for p in problems)


class TestSyncEligibleEntriesFilter:
    def test_only_approved_evidenced_ready_entries_pass(self):
        data = json.loads((FIXTURE_DIR / "approved-relevant-manifest.valid.json").read_text())
        eligible = sync_eligible_entries(data)
        # The fixture's AMBIGUOUS entry must never appear; its APPROVED_RELEVANT
        # entry has site_ready=false in the fixture and so is also excluded.
        assert all(e["relevance_decision"]["verdict"] == "APPROVED_RELEVANT" for e in eligible)
        assert all(e["site_ready"] is True for e in eligible)
        assert eligible == []

    def test_ready_approved_entry_is_eligible(self):
        e1 = _approved_entry(authority=_authority(ready=True))
        manifest = build_manifest(
            [e1], manifest_id="m", version=1, revision=1, generated_at=NOW.isoformat(),
            site_authority=_authority(ready=True), band_policy_revision=1,
        )
        eligible = sync_eligible_entries(manifest)
        assert len(eligible) == 1
        assert eligible[0]["site_id"] == "lords-01"


class TestNoDataDoesNotBecomeZero:
    def test_unknown_band_entry_still_validates_and_is_never_sync_eligible(self):
        ownership = OwnershipIndex()
        decision = decide_relevance(
            RelevanceInput(
                site_id="lords-01", query="интерстеллар", normalized_query="интерстеллар",
                entity_id="movie-interstellar-2014", taxonomy_id="title.unresolved",
                intent=QueryClass.TITLE_EXACT, target_url="https://lordfilm47.space/title/interstellar-2014",
                landing_page_taxonomy_id="title.interstellar-2014",  # mismatched on purpose
                rendered_evidence_confirmed=True,
            ),
            ownership=ownership, now=NOW,
        )
        assert decision.verdict.value == "OFF_TOPIC"
        missing = VolumeMeasurement(value=None, source="yandex_webmaster", measured_at=None, region="213", searcher="yandex")
        entry = build_entry(
            site_id="lords-01", domain="lordfilm47.space", query="интерстеллар",
            taxonomy_id="title.unresolved", intent=QueryClass.TITLE_EXACT, cluster="title-homonym",
            frequency_band=FrequencyBand.UNKNOWN,
            frequency_measurement=measurement_to_dict(missing, Freshness.MISSING),
            target_url="https://lordfilm47.space/title/interstellar-2014", relevance_decision=decision,
            evidence=(), approved_by="x", approved_at=NOW.isoformat(), created_at=NOW.isoformat(),
            site_authority=_authority(ready=True),
        )
        assert entry.frequency_measurement["value"] is None
        assert entry.sync_eligible is False
