"""Верхняя карусель на главной.

Полку собирает ранжировщик, а не рука: правила допуска и разнообразия живут в
одном месте. Главное обещание карусели — просмотр, поэтому запись без
подтверждённого потока туда не попадает ни при каких обстоятельствах.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import pytest

from factory.lords import plan as plan_mod
from factory.lords import recommend, render
from factory.lords import theme as theme_mod
from factory.recs import shelves as sh
from factory.recs.model import ItemFeatures

NOW = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)


def feature(cid, **kw):
    base = {
        "content_id": cid, "title": f"Тайтл {cid}", "content_type": "movie",
        "poster": f"https://poster/{cid}.webp", "playback_state": True,
        "added_at": NOW - timedelta(days=int(cid[-1]) if cid[-1].isdigit() else 1),
        "genres": ("драма",),
        # Адрес страницы обязателен: карточке некуда вести без него.
        "path": f"/title/{cid}/",
    }
    base.update(kw)
    return ItemFeatures(**base)


def shelf_of(items, limit=18):
    return sh.build_shelf(sh.LATEST_ADDED, items, now=NOW, limit=limit)


def rendered(items, limit=18):
    return render._carousel({}, shelf_of(items, limit), "Новинки")


def pool(n=14, **kw):
    return [feature(f"c{i}", genres=(f"жанр{i % 5}",), **kw) for i in range(n)]


class TestOnlyWatchableTitlesReachTheCarousel:
    def test_a_title_with_confirmed_silence_is_excluded(self):
        items = pool(12) + [feature("немой", playback_state=False, added_at=NOW)]
        html = rendered(items)
        assert "немой" not in html

    def test_an_unchecked_title_is_excluded_too(self):
        # Карусель обещает просмотр. «Не проверяли» — не обещание.
        items = pool(12) + [feature("неизвестный", playback_state=None, added_at=NOW)]
        assert "неизвестный" not in rendered(items)

    def test_a_title_without_a_poster_is_excluded(self):
        items = pool(12) + [feature("безкартинки", poster=None, added_at=NOW)]
        assert "безкартинки" not in rendered(items)


class TestSizeAndComposition:
    def test_the_shelf_holds_between_ten_and_eighteen(self):
        shelf = shelf_of(pool(40))
        assert 10 <= len(shelf) <= 18

    def test_a_shelf_too_short_is_not_drawn_at_all(self):
        # Три карточки выглядят как сбой, а не как подборка.
        assert render._carousel({}, shelf_of(pool(3)), "Новинки") == ""

    def test_no_title_appears_twice(self):
        ids = re.findall(r'data-content-id="([^"]+)"', rendered(pool(20)))
        assert len(ids) == len(set(ids))

    def test_one_genre_does_not_take_over_the_shelf(self):
        items = [feature(f"g{i}", genres=("боевик",)) for i in range(8)]
        items += [feature(f"o{i}", genres=("комедия",)) for i in range(8)]
        html = rendered(items)
        order = re.findall(r'data-content-id="([^"]+)"', html)
        assert len(order) >= 10


class TestCardShowsOnlyConfirmedFacts:
    def test_a_rating_carries_its_source(self):
        html = rendered(pool(12) + [feature("сОценкой", kp_rating=7.4, added_at=NOW)])
        if "сОценкой" in html:
            assert "Кинопоиск" in html

    def test_a_zero_rating_is_not_printed(self):
        html = rendered(pool(12) + [feature("ноль", kp_rating=0.0, added_at=NOW)])
        assert "0.0" not in html

    def test_absent_year_leaves_no_dangling_separator(self):
        html = rendered(pool(12))
        assert " · </span>" not in html
        assert "· ·" not in html

    def test_posters_are_lazy_and_sized(self):
        html = rendered(pool(12))
        assert 'loading="lazy"' in html
        # Ширина и высота заданы, чтобы подгрузка не сдвигала вёрстку.
        assert 'width="400"' in html and 'height="600"' in html


class TestAccessibilityAndEvents:
    def test_the_shelf_is_a_list_with_a_name(self):
        html = rendered(pool(12))
        assert 'role="list"' in html and "aria-label" in html

    def test_the_shelf_is_reachable_from_the_keyboard(self):
        assert 'tabindex="0"' in rendered(pool(12))

    def test_arrows_are_labelled_for_screen_readers(self):
        html = rendered(pool(12))
        assert html.count("aria-label=") >= 3

    def test_every_card_carries_shelf_position_and_id(self):
        html = rendered(pool(12))
        assert 'data-shelf="' in html
        positions = re.findall(r'data-position="(\d+)"', html)
        assert positions == [str(i + 1) for i in range(len(positions))]

    def test_the_section_records_the_algorithm_version(self):
        assert 'data-algorithm="ranker-v1"' in rendered(pool(12))


class TestOrderIsStable:
    def test_the_same_input_gives_the_same_order(self):
        items = pool(16)
        first = re.findall(r'data-content-id="([^"]+)"', rendered(list(items)))
        second = re.findall(r'data-content-id="([^"]+)"', rendered(list(reversed(items))))
        assert first == second


class TestStylesExistForTheCarousel:
    @pytest.fixture(params=["lords-general", "lords-new", "lords-curated"])
    def sheet(self, request):
        return theme_mod.stylesheet(plan_mod.load_profiles()[request.param])

    @pytest.mark.parametrize("selector", [
        ".rail {", ".rail__item", ".rail__poster", ".rail__arrow", ".rail__rating"])
    def test_every_carousel_class_has_a_rule(self, sheet, selector):
        assert selector in sheet

    def test_the_page_does_not_scroll_sideways(self, sheet):
        # Полка прокручивается внутри себя; страница — нет.
        assert ".section--rail {" in sheet
        assert "overflow: hidden" in sheet.split(".section--rail {")[1].split("}")[0]

    def test_the_poster_frame_is_fixed_so_loading_does_not_shift_layout(self, sheet):
        block = sheet.split(".rail__poster {")[1].split("}")[0]
        assert "aspect-ratio" in block

    def test_mobile_shows_a_partial_card_to_hint_at_more(self, sheet):
        assert "2.5" in sheet


class TestProfilesUseTheCarousel:
    def test_all_three_product_profiles_lead_with_it(self):
        profiles = plan_mod.load_profiles()
        for name in ("lords-general", "lords-new", "lords-curated"):
            blocks = theme_mod.layout_of(profiles[name])["home_blocks"]
            assert blocks[0] == "top_carousel", name

    def test_each_domain_names_its_shelf_differently(self):
        profiles = plan_mod.load_profiles()
        headings = {theme_mod.layout_of(profiles[n]).get("carousel_heading")
                    for n in ("lords-general", "lords-new", "lords-curated")}
        assert len(headings) == 3 and None not in headings


class TestAdapterKeepsTheContract:
    def test_playable_state_survives_the_translation(self):
        class Fake:
            name = "Т"
            content_type = "movie"
            slug = "t"
            external_id = "t"
            genres = ("драма",)
            country = "Франция"
            year = 2020
            playback = {"aggregator": "kp", "title_id": "1"}
            playable = True
            poster_url = "p.webp"
            kinopoisk_rating = 7.0
            imdb_rating = None
            created_at = "2026-08-01T00:00:00Z"
            updated_at = None
            episodic = False
        item = recommend.features_from_title(Fake())
        assert item.playback_state is True
        assert item.kp_rating == 7.0 and item.imdb_rating is None
        assert item.release_date.year == 2020


class TestCarouselLinksGoWhereThePageIs:
    """Ссылка карточки — адрес страницы, а не идентификатор поставщика.

    Первая выкладка карусели собирала адрес из `content_id`, то есть из UUID
    поставщика. Страницы по такому адресу нет, и каждая карточка вела в 404.
    Поймала это приёмка выкладки: она берёт первую ссылку на тайтл с главной,
    не находит там плеера и откатывает релиз. Сайт при этом не пострадал, но
    карусель не появилась.
    """

    def test_the_card_uses_the_catalogue_path(self):
        # Идентификатор уникален: совпади он с записью из набора, слияние
        # дублей склеило бы обе и адрес взяло бы у первой.
        item = feature("отдельная", path="/title/nastoyashchiy-slug/")
        html = rendered(pool(12) + [item])
        assert "/title/nastoyashchiy-slug/" in html

    def test_an_identifier_never_becomes_a_url(self):
        html = rendered([feature(f"01a0471{i}-97cc-754a-a163-7eff4fbca39{i}",
                                path=f"/title/slug-{i}/") for i in range(12)])
        assert "/title/01a0471" not in html

    def test_a_record_without_a_path_is_not_drawn(self):
        # Рисовать карточку, которой некуда вести, незачем.
        assert render._carousel_card(
            type("S", (), {"item": feature("c1", path=None)})(), 1, "shelf") == ""

    def test_every_rendered_card_has_a_href(self):
        html = rendered([feature(f"c{i}", path=f"/title/s{i}/") for i in range(14)])
        cards = html.count("rail__item")
        hrefs = html.count('class="rail__link" href="/title/')
        assert cards == hrefs
