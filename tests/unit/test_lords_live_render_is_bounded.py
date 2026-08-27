"""REQ-LORDS-BOUNDED-PAGE: ни одна страница не несёт весь каталог.

История. На трёх публичных доменах Lords стояла одна страница со всем каталогом:
4316 карточек, 988 КБ на запрос, 425 738 px прокрутки на десктопе и 2 746 542 px
на телефоне. Референсы на тех же ширинах укладываются в 1 972 px и 4 555 px.

Штатный рендерер пагинацию умеет — по 24 карточки на страницу. Но рядом с ними
он встраивал `#listing-data`: полный JSON всего каталога для фильтрации на
клиенте. На стенде в 62 тайтла это стоило килобайты, на живом каталоге в 4800 —
полтора мегабайта на каждой странице списка. Карточек на странице по-прежнему
24, а весит она как весь каталог, и первым это замечает посетитель с телефона.

Поэтому проверяется не «есть ли пагинация», а размер того, что уходит наружу.
"""

from __future__ import annotations

import yaml

from factory.lords import live_catalog, render as render_mod
from factory.paths import PATHS

CARD_MARK = "<article class=" + chr(34) + "card"


def live_items(count: int) -> list[dict]:
    """Записи в формате `content_live.normalize_title`."""
    return [
        {
            "external_id": f"01a0-{index:06d}",
            "name": f"Тайтл номер {index}",
            "type": "movie" if index % 2 else "tv",
            "is_series": bool(index % 2 == 0),
            "year": 2000 + (index % 27),
            "poster_url": f"https://poster.cdnvideohub.com/p/{index}.jpg",
            "licensed": True,
            "tags": ["Драма", "Триллер"],
            "kinopoisk_rating": 7.0,
            "imdb_rating": 6.5,
            "external_ids": {},
            "playback": None,
            "created_at": "2026-08-20T10:00:00Z",
            "updated_at": "2026-08-21T10:00:00Z",
        }
        for index in range(count)
    ]


def render(count: int):
    catalog = live_catalog.catalog_from_live(live_items(count))
    package = yaml.safe_load(PATHS.site_package("lords-01").read_text(encoding="utf-8"))
    site = render_mod.render_site(package, catalog=catalog, environ={})
    pages = site.pages
    return dict(pages) if isinstance(pages, dict) else {p.path: p for p in pages}


def body(page) -> str:
    return page.body if hasattr(page, "body") else str(page)


class TestLargeCatalogStaysBounded:
    def test_no_listing_page_carries_the_whole_catalog(self):
        pages = render(300)
        listings = {p: body(page) for p, page in pages.items()
                    if p in ("/", "/catalog/", "/movies/", "/series/")}
        assert listings, "разделов списка не нашлось — тест ничего не стережёт"
        for path, html in listings.items():
            assert len(html) < 200_000, (
                f"{path} весит {len(html)} байт: страница списка снова несёт весь каталог"
            )

    def test_a_listing_page_shows_one_page_of_cards(self):
        pages = render(300)
        html = body(pages["/catalog/"])
        cards = html.count(CARD_MARK)
        assert 0 < cards <= 48, f"на странице {cards} карточек вместо одной страницы выдачи"

    def test_client_dataset_is_dropped_when_the_catalog_is_large(self):
        """Полный JSON каталога на каждой странице — та же выдача, вид сбоку."""
        html = body(render(300)["/catalog/"])
        assert "listing-data" not in html, (
            "встроен полный набор каталога: фильтрация на клиенте не стоит "
            "полутора мегабайт на каждой странице"
        )

    def test_small_catalog_keeps_client_filtering(self):
        """На маленьком каталоге фильтрация дешёвая и остаётся на месте."""
        html = body(render(30)["/catalog/"])
        assert "listing-data" in html

    def test_second_page_shows_different_titles(self):
        pages = render(300)
        first = body(pages["/catalog/"])
        second_path = next(p for p in pages if p.startswith("/catalog/page/2"))
        second = body(pages[second_path])
        assert first != second, "вторая страница повторяет первую"


class TestLivePostersDoNotBecomePages:
    def test_remote_posters_never_turn_into_local_pages(self):
        """Постер источника — это адрес картинки, а не маршрут нашего сайта."""
        pages = render(30)
        bogus = [p for p in pages if p.startswith("http")]
        assert not bogus, f"внешние адреса стали страницами: {bogus[:3]}"

    def test_card_points_at_the_real_poster(self):
        html = body(render(30)["/catalog/"])
        assert "poster.cdnvideohub.com" in html, "живой постер не попал в карточку"


class TestCardTellsTheTruth:
    def test_no_fixture_badge_on_live_cards(self):
        html = body(render(30)["/catalog/"])
        assert ">fixture<" not in html, (
            "живая карточка помечена как фикстура — подпись противоречит содержимому"
        )

    def test_meta_has_no_dangling_separators(self):
        """Списочный ответ не даёт страну: «Фильм · 2003 · » — это брак вёрстки."""
        html = body(render(30)["/catalog/"])
        assert "· </span>" not in html and "·  ·" not in html, "в мета-строке повис разделитель"
