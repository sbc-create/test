"""Реестр источников рейтингов."""

from __future__ import annotations

from factory.ratings import (
    ADAPTER_VERSION_AMD_ONLINE,
    ADAPTER_VERSION_ANIMEMEDIA,
    ADAPTER_VERSION_SHIKIMORI,
)
from factory.ratings.models import HealthState, SourceRecord, SourceState
from factory.ratings.store import RatingsStore


def default_sources() -> list[SourceRecord]:
    return [
        SourceRecord(
            source_key="shikimori",
            display_name="Shikimori",
            canonical_origin="https://shikimori.io",
            adapter_version=ADAPTER_VERSION_SHIKIMORI,
            state=SourceState.READY,
            enabled=True,
            score_scale=10.0,
            supports_vote_count=True,
            supports_distribution=True,
            max_rps=2.0,
            max_requests_per_minute=60,
            freshness_policy={
                "ongoing_hours": 24,
                "recently_finished_days": 7,
                "popular_days": 14,
                "archive_days": [30, 90],
                "not_found_days": [14, 30],
            },
            legal_access_evidence="docs/rights/shikimori-ratings.md",
            attribution_gate=(
                "CONTRACT_GATE: long-term storage/attribution rules not fully "
                "documented by upstream; preserve provenance URL + adapter version"
            ),
            health_state=HealthState.UNKNOWN,
        ),
        SourceRecord(
            source_key="amd_online",
            display_name="AMD.online",
            canonical_origin="https://amd.online",
            adapter_version=ADAPTER_VERSION_AMD_ONLINE,
            state=SourceState.BLOCKED,
            enabled=False,
            score_scale=10.0,
            supports_vote_count=True,
            supports_distribution=False,
            max_rps=0.1,
            max_requests_per_minute=6,
            freshness_policy={"detail_pages_only": True, "min_interval_sec": 10},
            legal_access_evidence=(
                "artifacts/evidence/ratings-ingestion-02/AMD_PERMISSION_STATUS.md"
            ),
            attribution_gate="BLOCKED_PENDING_WRITTEN_PERMISSION",
            health_state=HealthState.UNKNOWN,
        ),
        SourceRecord(
            source_key="animemedia",
            display_name="AnimeMedia (unverified — not our sites)",
            canonical_origin="",
            adapter_version=ADAPTER_VERSION_ANIMEMEDIA,
            state=SourceState.UNVERIFIED_DISABLED,
            enabled=False,
            score_scale=10.0,
            supports_vote_count=False,
            supports_distribution=False,
            legal_access_evidence=(
                "UNVERIFIED: animedia.icu/space are our sites, not external sources. "
                "Use amd_online for AMD.online baseline."
            ),
            attribution_gate="CONTRACT_GATE: source unverified",
            health_state=HealthState.UNKNOWN,
        ),
        SourceRecord(
            source_key="provider_feed_kinopoisk",
            display_name="Кинопоиск (provider feed)",
            canonical_origin="provider-feed",
            adapter_version="provider-feed/1.0.0",
            state=SourceState.READY,
            enabled=True,
            score_scale=10.0,
            supports_vote_count=False,
            legal_access_evidence="docs/rights/provider-feed-ratings.md",
            health_state=HealthState.HEALTHY,
        ),
        SourceRecord(
            source_key="provider_feed_imdb",
            display_name="IMDb (provider feed)",
            canonical_origin="provider-feed",
            adapter_version="provider-feed/1.0.0",
            state=SourceState.READY,
            enabled=True,
            score_scale=10.0,
            supports_vote_count=False,
            legal_access_evidence="docs/rights/provider-feed-ratings.md",
            health_state=HealthState.HEALTHY,
        ),
    ]


def seed_registry(store: RatingsStore) -> list[dict]:
    for source in default_sources():
        store.upsert_source(source)
    return store.list_sources()
