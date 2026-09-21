"""Сопоставление тайтлов: точный ID, карантин, отсутствие автопривязки."""

from __future__ import annotations

import pytest

from factory.unified_ratings.matching import (
    MatchMethod,
    MatchStatus,
    QuarantineReason,
    TitleFacts,
    disagreements,
    effective_kind_class,
    match,
)


def ours(**kwargs) -> TitleFacts:
    base = {
        "title_id": "nova:t-001",
        "title_ru": "Ковбой Бибоп",
        "title_original": "Cowboy Bebop",
        "year": 1998,
        "kind": "tv",
        "episode_count": 26,
        "external_ids": {"myanimelist": "1"},
    }
    base.update(kwargs)
    return TitleFacts(**base)


def theirs(**kwargs) -> TitleFacts:
    base = {
        "title_id": "1",
        "title_original": "Cowboy Bebop",
        "year": 1998,
        "kind": "TV",
        "episode_count": 26,
        "external_ids": {"myanimelist": "1"},
    }
    base.update(kwargs)
    return TitleFacts(**base)


# ---------------------------------------------------------------------------
# точный внешний ID
# ---------------------------------------------------------------------------


def test_exact_external_id_is_accepted_when_facts_agree():
    decision = match(ours(), [theirs()], id_space="myanimelist")
    assert decision.status is MatchStatus.EXACT
    assert decision.method is MatchMethod.EXACT_EXTERNAL_ID
    assert decision.confidence == 1.0
    assert decision.auto_acceptable


def test_confirmed_mapping_wins_over_recomputation():
    decision = match(
        ours(), [theirs(title_id="777")], id_space="myanimelist", confirmed_external_id="777"
    )
    assert decision.status is MatchStatus.REVIEWED
    assert decision.method is MatchMethod.CONFIRMED_MAPPING


def test_one_external_id_pointing_at_two_records_is_a_conflict():
    decision = match(
        ours(), [theirs(title_id="1"), theirs(title_id="2")], id_space="myanimelist"
    )
    assert decision.status is MatchStatus.CONFLICT
    assert QuarantineReason.EXTERNAL_ID_CONFLICT in decision.reasons
    assert not decision.auto_acceptable


# ---------------------------------------------------------------------------
# обязательные причины карантина
# ---------------------------------------------------------------------------


def test_year_mismatch_quarantines_even_with_matching_id():
    decision = match(ours(), [theirs(year=2009)], id_space="myanimelist")
    assert decision.status is MatchStatus.CONFLICT
    assert QuarantineReason.YEAR_MISMATCH in decision.reasons


def test_one_year_difference_is_tolerated():
    """Зимний сезон отнесён каталогами к соседним годам — это не расхождение."""
    decision = match(ours(), [theirs(year=1999)], id_space="myanimelist")
    assert decision.status is MatchStatus.EXACT


def test_movie_versus_series_quarantines():
    decision = match(ours(kind="tv"), [theirs(kind="MOVIE")], id_space="myanimelist")
    assert decision.status is MatchStatus.CONFLICT
    assert QuarantineReason.MOVIE_VS_SERIES in decision.reasons


def test_special_or_ova_against_main_season_quarantines():
    decision = match(ours(kind="tv"), [theirs(kind="OVA")], id_space="myanimelist")
    assert decision.status is MatchStatus.CONFLICT
    assert QuarantineReason.SPECIAL_OVA_VS_MAIN in decision.reasons


def test_our_ova_matches_their_ova_despite_coarse_catalog_kind():
    """Каталог знает только tv/movie; пометка в названии тоже заявляет тип."""
    decision = match(
        ours(title_ru="Ковбой Бибоп OVA", kind="movie"),
        [theirs(kind="OVA")],
        id_space="myanimelist",
    )
    assert decision.status is MatchStatus.EXACT


def test_season_mismatch_quarantines():
    decision = match(
        ours(title_ru="Атака титанов 2", season_number=2),
        [theirs(title_original="Attack on Titan Season 3", season_number=3)],
        id_space="myanimelist",
    )
    assert decision.status is MatchStatus.CONFLICT
    assert QuarantineReason.SEASON_MISMATCH in decision.reasons


def test_remake_against_original_quarantines():
    decision = match(
        ours(title_ru="Хеллсинг"),
        [theirs(title_original="Hellsing remake")],
        id_space="myanimelist",
    )
    assert decision.status is MatchStatus.CONFLICT
    assert QuarantineReason.REMAKE in decision.reasons


def test_external_id_conflict_in_another_space_quarantines():
    decision = match(
        ours(external_ids={"myanimelist": "1", "imdb": "0213338"}),
        [theirs(external_ids={"myanimelist": "1", "imdb": "9999999"})],
        id_space="myanimelist",
    )
    assert decision.status is MatchStatus.CONFLICT
    assert QuarantineReason.EXTERNAL_ID_CONFLICT in decision.reasons


# ---------------------------------------------------------------------------
# без точного ID: только очередь проверки
# ---------------------------------------------------------------------------


def test_similar_title_alone_never_auto_links():
    decision = match(
        ours(external_ids={}),
        [theirs(external_ids={}, title_original="Cowboy Bebop")],
        id_space="myanimelist",
    )
    assert decision.status is MatchStatus.PENDING
    assert not decision.auto_acceptable


def test_franchise_neighbours_are_not_linked_by_name():
    decision = match(
        TitleFacts(
            title_id="nova:fma",
            title_ru="Стальной алхимик",
            title_original="Fullmetal Alchemist",
            year=2003,
            kind="tv",
        ),
        [
            TitleFacts(
                title_id="5114",
                title_original="Fullmetal Alchemist: Brotherhood",
                year=2009,
                kind="TV",
            )
        ],
    )
    assert decision.status is MatchStatus.PENDING
    assert QuarantineReason.YEAR_MISMATCH in decision.reasons


def test_multiple_equal_candidates_go_to_review():
    decision = match(
        ours(external_ids={}),
        [
            theirs(title_id="a", external_ids={}),
            theirs(title_id="b", external_ids={}),
        ],
    )
    assert decision.status is MatchStatus.PENDING
    assert QuarantineReason.MULTIPLE_EQUAL_CANDIDATES in decision.reasons


def test_low_confidence_goes_to_review():
    decision = match(
        ours(external_ids={}),
        [theirs(external_ids={}, title_original="Cowboy Bebop: Knockin on Heavens Door")],
    )
    assert decision.status is MatchStatus.PENDING
    assert decision.reasons  # причина названа


def test_no_candidates_is_rejected_not_guessed():
    decision = match(ours(), [], id_space="myanimelist")
    assert decision.status is MatchStatus.REJECTED
    assert decision.method is MatchMethod.NONE


def test_missing_year_blocks_title_based_matching():
    decision = match(
        ours(external_ids={}, year=None),
        [theirs(external_ids={}, year=None)],
    )
    assert decision.status is MatchStatus.PENDING


# ---------------------------------------------------------------------------
# вспомогательное
# ---------------------------------------------------------------------------


def test_effective_kind_reads_markers_in_the_title():
    assert effective_kind_class(ours(title_ru="Наруто OVA", kind="tv")) == "side"
    assert effective_kind_class(ours(title_ru="Наруто", kind="tv")) == "series"


def test_agreeing_facts_produce_no_reasons():
    assert disagreements(ours(), theirs()) == []


@pytest.mark.parametrize(
    "reason",
    [
        QuarantineReason.YEAR_MISMATCH,
        QuarantineReason.MOVIE_VS_SERIES,
        QuarantineReason.SEASON_MISMATCH,
        QuarantineReason.REMAKE,
        QuarantineReason.SPECIAL_OVA_VS_MAIN,
        QuarantineReason.EXTERNAL_ID_CONFLICT,
        QuarantineReason.INSUFFICIENT_CONFIDENCE,
        QuarantineReason.MULTIPLE_EQUAL_CANDIDATES,
        QuarantineReason.FRANCHISE_MISMATCH,
    ],
)
def test_every_required_quarantine_reason_exists(reason):
    assert reason.value
