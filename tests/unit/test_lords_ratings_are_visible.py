"""Оценки видно, и видно, чьи они.

Разметка оценок выводилась давно, но в таблице стилей слово «rating» не
встречалось ни разу: подпись и число шли подряд без промежутка и терялись среди
прочего текста. Владелец сообщил, что Кинопоиска и IMDb на страницах нет, — и
был прав по сути, хотя элементы в HTML присутствовали.
"""
from __future__ import annotations

import dataclasses

import pytest

from factory.lords import live_catalog as lc
from factory.lords import plan as plan_mod
from factory.lords import render
from factory.lords import theme as theme_mod

BASE = lc.title_from_item({
    "external_id": "x", "name": "Пример", "type": "movie", "is_series": False,
    "year": 2020, "tags": [], "external_ids": {}, "playback": None,
    "created_at": None, "updated_at": None,
})


def rated(kinopoisk=None, imdb=None):
    return dataclasses.replace(BASE, kinopoisk_rating=kinopoisk, imdb_rating=imdb)


class TestEveryRatingCarriesItsSource:
    def test_both_ratings_are_named(self):
        html = render._ratings_block(rated(7.28, 6.1))
        assert "Кинопоиск" in html and "IMDb" in html
        assert "7,3" in html and "6,1" in html

    def test_the_source_is_never_dropped(self):
        # Число без подписи ничего не утверждает: 7.8 у Кинопоиска и 7.8 у
        # IMDb — разные суждения разных источников.
        for html in (render._ratings_block(rated(7.0, None)),
                     render._ratings_block(rated(None, 7.0)),
                     render._card_rating(rated(7.0, None)),
                     render._card_rating(rated(None, 7.0))):
            assert "Кинопоиск" in html or "IMDb" in html

    def test_ratings_are_not_swapped(self):
        html = render._ratings_block(rated(9.9, 1.1))
        assert html.index("Кинопоиск") < html.index("9,9") < html.index("IMDb")

    def test_one_source_present_does_not_invent_the_other(self):
        html = render._ratings_block(rated(None, 6.1))
        assert "IMDb" in html and "Кинопоиск" not in html


class TestNothingIsInvented:
    def test_a_missing_rating_is_hidden_not_zeroed(self):
        assert render._ratings_block(rated(None, None)) == ""
        assert render._card_rating(rated(None, None)) == ""

    @pytest.mark.parametrize("zero", [0, 0.0])
    def test_a_zero_is_not_presented_as_an_opinion(self, zero):
        # Ноль в шкале «от одного до десяти» почти всегда означает «оценки
        # нет». Подписать его именем источника — приписать ему суждение.
        assert render._ratings_block(rated(zero, None)) == ""
        assert render._card_rating(rated(zero, None)) == ""

    def test_a_zero_does_not_hide_the_other_source(self):
        html = render._card_rating(rated(0.0, 8.0))
        assert "IMDb" in html and "8,0" in html

    @pytest.mark.parametrize("junk", [True, False, "7.5", None, [], {}])
    def test_non_numbers_are_refused(self, junk):
        assert render._shown_rating(junk) is None


class TestTheCardShowsOneRating:
    def test_kinopoisk_wins_when_both_exist(self):
        html = render._card_rating(rated(7.0, 9.0))
        assert "Кинопоиск" in html and "IMDb" not in html

    def test_imdb_is_used_when_kinopoisk_is_absent(self):
        assert "IMDb" in render._card_rating(rated(None, 9.0))

    def test_the_card_rating_reaches_the_grid(self):
        html = render._grid([rated(7.28, None)])
        assert "card__rating" in html and "7,3" in html


class TestRatingsAreActuallyStyled:
    """Без правил оформления разметка есть, а оценок на экране нет."""

    @pytest.fixture(params=["lords-general", "lords-new", "lords-curated"])
    def sheet(self, request):
        return theme_mod.stylesheet(plan_mod.load_profiles()[request.param])

    @pytest.mark.parametrize("selector", [
        ".ratings", ".rating__source", ".rating__value",
        ".card__rating", ".card__rating-value",
    ])
    def test_every_rating_class_has_a_rule(self, sheet, selector):
        assert selector in sheet, f"нет правила для {selector}"

    def test_the_source_and_the_number_are_separated(self, sheet):
        # Слипшееся «IMDb6.1» — ровно то, что читалось как отсутствие оценки.
        assert "gap:" in sheet.split(".rating {")[1].split("}")[0]

    def test_the_card_rating_is_readable_over_any_poster(self, sheet):
        block = sheet.split(".card__rating {")[1].split("}")[0]
        assert "background" in block
