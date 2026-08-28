"""REQ-LORDS-TAGS: то, что источник зовёт тегами, не выдаётся за жанры.

Поле `tags` списочного ответа CDNVideoHub оказалось не списком жанров. На живом
каталоге в нём лежат вперемешку:

  * возрастные отметки — `13+` (225 записей), `18+` (77), `NR` (28), `U/A 16+`,
    `MA 15+`, `12A`, `Not Yet Rated`;
  * пометки формы — `cartoon` (85), `anime` (71), `ona` (79), `ova`, `special`;
  * пользовательские дескрипторы MDL — `Suspense (Vote tags)`,
    `Friendship (Vote tags)`, `Adapted From A Novel (Vote tags)`.

Отдавать это как «Жанры» значит писать на странице фильма «Жанры: NR». Поэтому
теги разбираются: возраст уходит в свою строку, пометки формы уточняют тип, а
остальное показывается тегами и называется тегами.
"""

from __future__ import annotations

import pytest

from factory.lords import fixtures as fx
from factory.lords import live_catalog


def item(tags, **over) -> dict:
    base = {
        "external_id": "01a0-1", "name": "Тайтл", "type": "movie", "is_series": False,
        "year": 2023, "poster_url": None, "tags": tags,
        "kinopoisk_rating": None, "imdb_rating": None, "external_ids": {},
        "playback": None, "created_at": None, "updated_at": None,
    }
    base.update(over)
    return base


class TestAgeRatingsLeaveTheTagList:
    @pytest.mark.parametrize("tag", ["13+", "18+", "0+", "U/A 16+", "MA 15+",
                                     "12A", "R", "16"])
    def test_age_marks_become_the_age_field(self, tag):
        title = live_catalog.title_from_item(item([tag, "Детектив"]))
        assert title.age_rating == tag, f"{tag} не распознан как возрастная отметка"
        assert tag not in title.genres, f"{tag} остался в списке тегов"

    @pytest.mark.parametrize("tag", ["NR", "Not Yet Rated", "Not Rated", "Unrated"])
    def test_a_code_meaning_no_rating_is_not_shown_as_a_rating(self, tag):
        """«Отметки нет» — это отсутствие значения, а не значение.

        Код NR попадал в поле возрастной отметки и печатался на странице как
        «Возрастная отметка: NR» — на 31 странице каталога. Посетителю такой
        код ничего не сообщает; жанром он тоже не является, поэтому в теги
        не уходит.
        """
        title = live_catalog.title_from_item(item([tag, "Детектив"]))
        assert title.age_rating == ""
        assert tag not in title.genres
        assert list(title.genres) == ["Детектив"]

    def test_first_age_mark_wins_and_the_rest_do_not_pollute_tags(self):
        title = live_catalog.title_from_item(item(["13+", "16+", "Детектив"]))
        assert title.age_rating in ("13+", "16+")
        assert list(title.genres) == ["Детектив"]


class TestFormatMarksRefineTheType:
    @pytest.mark.parametrize("tag,expected", [
        ("cartoon", fx.ANIMATION),
        ("anime", fx.ANIME),
        ("ona", fx.ANIME),
        ("ova", fx.ANIME),
    ])
    def test_format_marks_change_the_content_type(self, tag, expected):
        title = live_catalog.title_from_item(item([tag], type="tv", is_series=True))
        assert title.content_type == expected, (
            f"пометка {tag} не уточнила тип: источник знает больше, чем поле type"
        )

    def test_format_marks_do_not_stay_in_the_tag_list(self):
        title = live_catalog.title_from_item(item(["cartoon", "Комедия"]))
        assert "cartoon" not in title.genres, "сырая пометка формы показана как тег"
        assert list(title.genres) == ["Комедия"]


class TestVoteTagsAreCleanedUp:
    def test_mdl_suffix_is_stripped(self):
        title = live_catalog.title_from_item(item(["Suspense (Vote tags)"]))
        assert list(title.genres) == ["Suspense"], "служебный суффикс источника показан посетителю"

    def test_ordinary_tags_pass_through(self):
        title = live_catalog.title_from_item(item(["Детектив", "Драма"]))
        assert list(title.genres) == ["Детектив", "Драма"]

    def test_a_title_with_only_service_tags_has_no_tags_at_all(self):
        """Пустой список честнее, чем строка «Жанры: NR»."""
        title = live_catalog.title_from_item(item(["13+", "cartoon"]))
        assert list(title.genres) == []


class TestNoStandWordingOnALiveCatalogue:
    """REQ-LORDS-NO-STAND-COPY: тексты про тестовый стенд принадлежат стенду.

    Витрина выглядела незаконченной не из-за вёрстки. На живом каталоге она
    сама сообщала посетителю, что каталог синтетический, названия и постеры
    выдуманы, а за записями не стоят реальные произведения. Проверяется весь
    отданный сайт целиком, а не отдельная строка: такие тексты жили в баннере,
    в подвале, в блоке комментариев и в описании подборок.
    """

    def test_no_page_tells_the_visitor_it_is_a_test_stand(self):
        import yaml

        from factory.lords import render as render_mod
        from factory.paths import PATHS

        items = [item(["Детектив"], external_id=f"id-{i}", name=f"Тайтл {i}") for i in range(20)]
        catalog = live_catalog.catalog_from_live(items)
        package = yaml.safe_load(PATHS.site_package("lords-03").read_text(encoding="utf-8"))
        site = render_mod.render_site(package, catalog=catalog, environ={}, publisher_id="10238")
        pages = site.pages if isinstance(site.pages, dict) else {p.path: p for p in site.pages}
        for path, page in pages.items():
            html = page.body if hasattr(page, "body") else str(page)
            if not html.lstrip().startswith("<!doctype"):
                continue
            for needle in ("синтетическ", "выдуманы", "тестового каталога",
                           "не стоят реальные произведения"):
                assert needle not in html, f"{path}: «{needle}» под живым каталогом"
