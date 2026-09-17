"""Tests for the five-entity observation model and its forbidden inferences."""
from __future__ import annotations

import pytest

from seo_operator.query_observations import (
    IndexabilityObservation,
    ObservationError,
    QueryObservation,
    RankObservation,
    SearchIndexObservation,
    noindex_directive,
)


class TestQueryObservation:
    def test_absence_is_none_not_zero(self):
        obs = QueryObservation(
            site_id="lords-01", domain="lordfilm47.space", query="фильмы",
            source="yandex_webmaster", period_start="2026-08-01", period_end="2026-08-31",
        )
        assert obs.impressions is None
        assert obs.clicks is None
        assert obs.average_position is None

    def test_unknown_source_is_rejected(self):
        with pytest.raises(ObservationError):
            QueryObservation(
                site_id="lords-01", domain="lordfilm47.space", query="фильмы",
                source="made_up_source", period_start="2026-08-01", period_end="2026-08-31",
            )


class TestRankObservationDoesNotProveIndexation:
    def test_rank_observation_has_no_index_field(self):
        rank = RankObservation(
            site_id="lords-01", domain="lordfilm47.space", query="фильмы",
            source="topvisor", position=3, checked_at="2026-09-17T00:00:00Z",
            searcher="yandex", region="213",
        )
        assert not hasattr(rank, "indexed")
        assert not hasattr(rank, "is_indexed")
        assert not hasattr(rank, "in_index")

    def test_unknown_source_is_rejected(self):
        with pytest.raises(ObservationError):
            RankObservation(
                site_id="lords-01", domain="lordfilm47.space", query="фильмы",
                source="scraped_serp", position=3, checked_at="2026-09-17T00:00:00Z",
                searcher="yandex", region="213",
            )

    def test_missing_position_is_none_not_zero(self):
        rank = RankObservation(
            site_id="lords-01", domain="lordfilm47.space", query="фильмы",
            source="topvisor", position=None, checked_at="2026-09-17T00:00:00Z",
            searcher="yandex", region="213",
        )
        assert rank.position is None


class TestIndexabilityDoesNotProveIndexed:
    def test_fully_confirmed_indexable_still_does_not_prove_indexed(self):
        obs = IndexabilityObservation(
            site_id="lords-01", url="https://lordfilm47.space/genre/action",
            status_code=200, robots_allowed=True, canonical_matches_self=True,
            in_sitemap=True, rendered_ok=True, checked_at="2026-09-17T00:00:00Z",
        )
        assert obs.fully_confirmed_indexable is True
        assert obs.proves_indexed is False

    def test_unknown_flag_is_not_treated_as_confirmed(self):
        obs = IndexabilityObservation(
            site_id="lords-01", url="https://lordfilm47.space/genre/action",
            status_code=200, robots_allowed=True, canonical_matches_self=None,
            in_sitemap=True, rendered_ok=True,
        )
        assert obs.fully_confirmed_indexable is False

    def test_no_evidence_at_all_is_not_confirmed(self):
        obs = IndexabilityObservation(site_id="lords-01", url="https://lordfilm47.space/x")
        assert obs.fully_confirmed_indexable is False
        assert obs.proves_indexed is False


class TestSearchIndexObservationIsTheOnlyIndexClaim:
    def test_can_assert_indexed(self):
        obs = SearchIndexObservation(
            site_id="lords-01", url="https://lordfilm47.space/genre/action",
            provider="yandex_webmaster_indexing", indexed=True,
            checked_at="2026-09-17T00:00:00Z", evidence_ref="wm-idx-001",
        )
        assert obs.indexed is True

    def test_can_assert_not_indexed(self):
        obs = SearchIndexObservation(
            site_id="lords-01", url="https://lordfilm47.space/genre/action",
            provider="yandex_webmaster_indexing", indexed=False,
            checked_at="2026-09-17T00:00:00Z", evidence_ref="wm-idx-002",
        )
        assert obs.indexed is False


class TestQueryLevelNoindexIsRejected:
    def test_url_subject_is_accepted(self):
        assert noindex_directive("https://lordfilm47.space/x", subject_kind="url") == (
            "https://lordfilm47.space/x"
        )

    def test_query_subject_is_rejected(self):
        with pytest.raises(ObservationError, match="URL-level directive only"):
            noindex_directive("смотреть боевики онлайн", subject_kind="query")

    def test_other_subject_kinds_are_also_rejected(self):
        with pytest.raises(ObservationError):
            noindex_directive("entity-42", subject_kind="entity")
