"""REQ-LORDS-FACTS: карточка говорит только то, что подтвердил источник.

Список фактов страницы тайтла писался под синтетический стенд и на живом
каталоге начал врать сразу в нескольких местах:

  * строка «Происхождение данных» сообщала «синтетическая запись стенда» —
    под настоящей записью CDNVideoHub;
  * поля, которых списочный ответ не даёт, всё равно печатались пустыми:
    «Страна», «Студия», «Оригинальное название» — заголовок есть, значения нет;
  * «Длительность» показывала «0 мин», хотя ноль здесь означает «не сказано»;
  * оценки Кинопоиска и IMDb источник отдаёт, но страница о них молчала.

Проверяется поведение на живой записи, а не на фикстуре.
"""

from __future__ import annotations

import yaml

from factory.lords import live_catalog
from factory.lords import render as render_mod
from factory.paths import PATHS


def item(**over) -> dict:
    base = {
        "external_id": "01a0-00001",
        "name": "Бункер",
        "type": "movie",
        "is_series": False,
        "year": 2023,
        "poster_url": "https://poster.cdnvideohub.com/p/1.jpg",
        "tags": ["Триллер"],
        "kinopoisk_rating": 7.8,
        "imdb_rating": 6.9,
        "external_ids": {},
        "playback": {"aggregator": "kp", "title_id": "1"},
        "created_at": "2026-08-20T10:00:00Z",
        "updated_at": "2026-08-21T10:00:00Z",
    }
    base.update(over)
    return base


def title_html(items) -> str:
    catalog = live_catalog.catalog_from_live(items)
    package = yaml.safe_load(PATHS.site_package("lords-01").read_text(encoding="utf-8"))
    site = render_mod.render_site(package, catalog=catalog, environ={}, publisher_id="10238")
    pages = site.pages if isinstance(site.pages, dict) else {p.path: p for p in site.pages}
    for path, page in pages.items():
        if path.startswith("/title/"):
            return page.body if hasattr(page, "body") else str(page)
    raise AssertionError("страницы тайтла нет")


class TestNoEmptyFactRows:
    def test_absent_fields_do_not_produce_empty_rows(self):
        html = title_html([item()])
        for label in ("Страна", "Студия", "Оригинальное название", "Возрастная отметка"):
            assert f"<dt>{label}</dt>" not in html, (
                f"строка «{label}» напечатана, хотя источник значения не дал"
            )

    def test_unknown_runtime_is_not_zero_minutes(self):
        html = title_html([item()])
        assert "0 мин" not in html, "ноль минут — это не длительность, а её отсутствие"

    def test_known_fields_are_still_shown(self):
        html = title_html([item()])
        assert "<dt>Тип</dt>" in html and "Фильм" in html
        assert "<dt>Год</dt>" in html and "2023" in html
        # У живого каталога строка называется «Теги»: то, что источник кладёт в
        # `tags`, жанрами не является — там же лежат возрастные отметки.
        assert "<dt>Теги</dt>" in html and "Триллер" in html
        assert "<dt>Жанры</dt>" not in html


class TestProvenanceTellsTheTruth:
    def test_live_record_is_not_called_a_fixture(self):
        html = title_html([item()])
        assert "синтетическая" not in html, "живая запись подписана как синтетическая"
        assert "стенда" not in html


class TestRatingsAreLabelledAndNotMixedUp:
    def test_both_ratings_are_shown_with_their_source(self):
        html = title_html([item(kinopoisk_rating=7.8, imdb_rating=6.9)])
        assert "Кинопоиск" in html and "7,8" in html
        assert "IMDb" in html and "6,9" in html

    def test_ratings_are_not_swapped(self):
        html = title_html([item(kinopoisk_rating=1.1, imdb_rating=9.9)])
        kp = html.index("Кинопоиск")
        # Значение своего источника обязано стоять рядом со своей подписью.
        assert "1,1" in html[kp:kp + 60], "рядом с Кинопоиском стоит не его оценка"
        imdb = html.index("IMDb")
        assert "9,9" in html[imdb:imdb + 60], "рядом с IMDb стоит не его оценка"

    def test_missing_rating_is_hidden_not_zero(self):
        html = title_html([item(kinopoisk_rating=None, imdb_rating=None)])
        assert "Кинопоиск" not in html, "подпись Кинопоиска стоит без оценки"
        assert "IMDb" not in html, "подпись IMDb стоит без оценки"

    def test_one_rating_present_does_not_invent_the_other(self):
        html = title_html([item(kinopoisk_rating=7.8, imdb_rating=None)])
        assert "Кинопоиск" in html
        assert "IMDb" not in html
