"""Главная как витрина, а не как одна лента.

Владелец смотрит на главную и видит либо магазин, либо служебную выгрузку.
Разница между ними — не в количестве записей, а в том, разложены ли они по
полкам. Сериальный домен показывал ровно один заголовок «Последние
добавления», потому что полки про сезоны молча схлопывались: у живых записей
не было ни одного сезона, и `episodic` всегда был ложью.
"""
from __future__ import annotations

import pytest

from factory.lords import fixtures as fx
from factory.lords import live_catalog as lc
from factory.lords import render


def _item(external_id: str, name: str, **over) -> dict:
    item = {
        "external_id": external_id,
        "name": name,
        "type": "movie",
        "is_series": False,
        "year": 2019,
        "tags": [],
        "external_ids": {},
        "playback": None,
        "created_at": None,
        "updated_at": None,
    }
    item.update(over)
    return item


class TestSeasonsReachTheCatalogue:
    def test_a_series_with_detail_seasons_counts_as_episodic(self):
        title = lc.title_from_item(_item(
            "s1", "Сериал", type="tv", is_series=True,
            seasons=[{"number": "1", "episodes_count": 6},
                     {"number": "2", "episodes_count": 10}],
        ))
        assert title.episodic is True
        assert [s.number for s in title.seasons] == [1, 2]
        assert title.episode_count == 16

    def test_a_season_without_episodes_is_not_invented(self):
        # Сезон, про который источник не сказал числа серий, — это не сезон из
        # нуля серий, а отсутствие данных. Показывать пустую вкладку хуже, чем
        # не показывать вкладку.
        title = lc.title_from_item(_item(
            "s2", "Сериал", type="tv", is_series=True,
            seasons=[{"number": "1"}],
        ))
        assert title.seasons == ()
        assert title.episodic is False

    def test_a_film_stays_non_episodic(self):
        assert lc.title_from_item(_item("m1", "Фильм")).episodic is False

    @pytest.mark.parametrize("broken", [None, [], ["сезон"], [{"number": "нет"}]])
    def test_broken_season_payloads_do_not_raise(self, broken):
        assert lc.title_from_item(_item("m2", "Фильм", seasons=broken)).seasons == ()


class TestShelfHeadings:
    def test_declinable_types_get_a_plural_heading(self):
        # «Фильм» над рядом из двенадцати фильмов — это подпись типа, а не
        # название полки. У «аниме» и «дорам» множественное число совпадает с
        # единственным или образуется само собой, поэтому проверяются те типы,
        # где разница вообще существует.
        for kind in (fx.MOVIES, fx.SERIES, fx.ANIMATION):
            assert render.TYPE_SECTION_LABELS[kind] != render.TYPE_LABELS[kind]

    def test_no_heading_is_left_empty(self):
        assert all(label.strip() for label in render.TYPE_SECTION_LABELS.values())

    def test_every_shown_type_has_a_plural_heading(self):
        assert set(render.TYPE_SECTION_LABELS) == set(render.TYPE_LABELS)


class TestTopRatedShelf:
    def _rated(self, values):
        titles = []
        for i, value in enumerate(values):
            t = lc.title_from_item(_item(f"r{i}", f"Запись {i}"))
            titles.append(t.__class__(**{**t.__dict__, "kinopoisk_rating": value}))
        return titles

    def test_records_without_a_rating_stay_out_of_the_shelf(self):
        ctx = {"row_items": 12}
        html = render._top_rated(ctx, self._rated([8.1, 7.4, None, 6.9, 9.0]))
        assert "Запись 2" not in html

    def test_the_shelf_is_ordered_by_the_confirmed_rating(self):
        html = render._top_rated({"row_items": 12}, self._rated([7.0, 9.0, 8.0, 6.0]))
        assert html.index("Запись 1") < html.index("Запись 2") < html.index("Запись 0")

    def test_too_few_rated_records_render_no_shelf_at_all(self):
        # Полка из двух записей выглядит как ошибка вёрстки, а не как подборка.
        assert render._top_rated({"row_items": 12}, self._rated([8.0, 7.0])) == ""

    def test_a_zero_rating_is_not_treated_as_missing(self):
        assert render._best_rating(self._rated([0.0])[0]) == 0.0
