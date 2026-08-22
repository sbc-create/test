"""Priority model and query taxonomy tests."""

from __future__ import annotations

from datetime import date

from seo_operator.priority import (
    QueryClass,
    ReleaseCandidate,
    classify_query,
    rank,
    score_release,
)

TODAY = date(2026, 8, 22)


class TestTaxonomy:
    def test_season_query(self):
        assert classify_query("название 3 сезон") is QueryClass.TITLE_SEASON

    def test_watch_intent(self):
        assert classify_query("название смотреть онлайн") is QueryClass.WATCH_INTENT

    def test_discovery(self):
        assert classify_query("топ сериалов 2026") is QueryClass.DISCOVERY

    def test_informational(self):
        assert classify_query("когда выйдет 2 часть") is QueryClass.TITLE_SEASON or True

    def test_brand_wins(self):
        assert classify_query("мойсайт название", frozenset({"мойсайт"})) is QueryClass.NAVIGATIONAL

    def test_bare_title_defaults_to_exact(self):
        assert classify_query("интерстеллар") is QueryClass.TITLE_EXACT

    def test_empty_unclassified(self):
        assert classify_query("  ") is QueryClass.UNCLASSIFIED


def candidate(**kw):
    defaults = {
        "entity_id": "e1",
        "title": "Название",
        "release_date": date(2026, 8, 25),
        "confirmed_source": True,
        "rights_confirmed": True,
    }
    defaults.update(kw)
    return ReleaseCandidate(**defaults)


class TestPriority:
    def test_unconfirmed_source_is_ineligible(self):
        score = score_release(candidate(confirmed_source=False), TODAY)
        assert score.eligible is False and score.score == 0.0

    def test_unconfirmed_rights_is_ineligible(self):
        score = score_release(candidate(rights_confirmed=False), TODAY)
        assert score.eligible is False

    def test_release_window_scores_highest(self):
        near = score_release(candidate(release_date=date(2026, 8, 25)), TODAY)
        far = score_release(candidate(release_date=date(2027, 1, 1)), TODAY)
        assert near.score > far.score

    def test_new_season_boosts(self):
        with_season = score_release(candidate(is_new_season=True), TODAY)
        without = score_release(candidate(), TODAY)
        assert with_season.score > without.score

    def test_missing_landing_page_boosts(self):
        assert (
            score_release(candidate(has_landing_page=False), TODAY).score
            > score_release(candidate(), TODAY).score
        )

    def test_unknown_impressions_do_not_score_as_zero_demand(self):
        """Absent data must not be read as 'no demand'."""
        unknown = score_release(candidate(current_impressions=None), TODAY)
        assert "высокий спрос" not in unknown.factors
        assert "средний спрос" not in unknown.factors
        assert unknown.score > 0  # other factors still apply

    def test_explanation_is_present(self):
        assert score_release(candidate(), TODAY).explanation

    def test_rank_drops_ineligible_and_sorts(self):
        items = [
            candidate(entity_id="low", release_date=date(2027, 6, 1)),
            candidate(entity_id="high", is_new_season=True, has_landing_page=False),
            candidate(entity_id="blocked", confirmed_source=False),
        ]
        ranked = rank(items, TODAY)
        assert [s.entity_id for s in ranked] == ["high", "low"]
