"""Tests for versioned topical-relevance decisions."""
from __future__ import annotations

from datetime import datetime, timezone

from seo_operator.priority import QueryClass
from seo_operator.relevance import (
    OwnershipIndex,
    RelevanceInput,
    RelevanceVerdict,
    decide_relevance,
)

NOW = datetime(2026, 9, 17, tzinfo=timezone.utc)


def _input(**overrides) -> RelevanceInput:
    base = {
        "site_id": "lords-01",
        "query": "Интерстеллар",
        "normalized_query": "интерстеллар",
        "entity_id": "movie-interstellar-2014",
        "taxonomy_id": "title.interstellar-2014",
        "intent": QueryClass.TITLE_EXACT,
        "target_url": "https://lordfilm47.space/title/interstellar-2014",
        "landing_page_taxonomy_id": "title.interstellar-2014",
        "rendered_evidence_confirmed": True,
        "homonym_entity_ids": (),
    }
    base.update(overrides)
    return RelevanceInput(**base)


class TestApprovedRelevant:
    def test_matching_everything_is_approved(self):
        decision = decide_relevance(_input(), ownership=OwnershipIndex(), now=NOW)
        assert decision.verdict is RelevanceVerdict.APPROVED_RELEVANT
        assert decision.sync_eligible is True
        assert decision.policy_revision >= 1
        assert decision.decided_at


class TestOffTopic:
    def test_wrong_landing_page_is_off_topic(self):
        decision = decide_relevance(
            _input(landing_page_taxonomy_id="genre.action"),
            ownership=OwnershipIndex(), now=NOW,
        )
        assert decision.verdict is RelevanceVerdict.OFF_TOPIC
        assert "wrong landing page" in decision.reason

    def test_rendered_evidence_contradicts_query_is_off_topic(self):
        decision = decide_relevance(
            _input(rendered_evidence_confirmed=False),
            ownership=OwnershipIndex(), now=NOW,
        )
        assert decision.verdict is RelevanceVerdict.OFF_TOPIC


class TestAmbiguousHomonym:
    def test_title_homonym_is_ambiguous(self):
        """"Интерстеллар" could be the 2014 film or an unrelated cover band EP."""
        decision = decide_relevance(
            _input(homonym_entity_ids=("movie-interstellar-2014", "ep-interstellar-cover-band")),
            ownership=OwnershipIndex(), now=NOW,
        )
        assert decision.verdict is RelevanceVerdict.AMBIGUOUS
        assert "2 distinct entities" in decision.reason

    def test_single_candidate_is_not_treated_as_homonymy(self):
        decision = decide_relevance(
            _input(homonym_entity_ids=("movie-interstellar-2014",)),
            ownership=OwnershipIndex(), now=NOW,
        )
        assert decision.verdict is RelevanceVerdict.APPROVED_RELEVANT


class TestSuspiciousRequiresReview:
    def test_missing_rendered_evidence_is_suspicious_not_approved(self):
        decision = decide_relevance(
            _input(rendered_evidence_confirmed=None),
            ownership=OwnershipIndex(), now=NOW,
        )
        assert decision.verdict is RelevanceVerdict.SUSPICIOUS_REQUIRES_REVIEW
        assert decision.sync_eligible is False

    def test_ownership_conflict_between_two_sites_is_suspicious(self):
        ownership = OwnershipIndex()
        first = decide_relevance(_input(site_id="lords-01"), ownership=ownership, now=NOW)
        assert first.verdict is RelevanceVerdict.APPROVED_RELEVANT

        second = decide_relevance(_input(site_id="lords-02"), ownership=ownership, now=NOW)
        assert second.verdict is RelevanceVerdict.SUSPICIOUS_REQUIRES_REVIEW
        assert "non-compete" in second.reason or "ownership" in second.reason

    def test_same_site_reclaiming_its_own_query_is_not_a_conflict(self):
        ownership = OwnershipIndex()
        first = decide_relevance(_input(site_id="lords-01"), ownership=ownership, now=NOW)
        second = decide_relevance(_input(site_id="lords-01"), ownership=ownership, now=NOW)
        assert first.verdict is RelevanceVerdict.APPROVED_RELEVANT
        assert second.verdict is RelevanceVerdict.APPROVED_RELEVANT


class TestKeywordOverlapAloneIsNotEnough:
    def test_word_match_without_rendered_evidence_does_not_approve(self):
        """Sharing words with the query is not itself a basis for approval."""
        decision = decide_relevance(
            _input(query="боевики онлайн", normalized_query="боевики онлайн",
                   rendered_evidence_confirmed=None),
            ownership=OwnershipIndex(), now=NOW,
        )
        assert decision.verdict is not RelevanceVerdict.APPROVED_RELEVANT
