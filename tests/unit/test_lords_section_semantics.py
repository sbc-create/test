"""REQ-LORDS-RECENTLY-ADDED: «Последние добавления» показывают добавленное последним.

Обновление каталога заработало: провайдер добавил «Призраки» в 14:28, таймер
принёс запись, и у неё появилась своя страница. На главной её при этом не было.

Причина в сортировке. Блок «Последние добавления» использовал общий порядок
каталога — по году выпуска, затем по названию. Для витрины это разумный порядок,
но к слову «последние» он отношения не имеет: фильм 2026 года, добавленный
полгода назад, всегда обгонит вчерашнее поступление 2019 года.

Проверяется именно порядок по времени появления записи у источника.
"""

from __future__ import annotations

import re

import yaml

from factory.lords import live_catalog
from factory.lords import render as render_mod
from factory.paths import PATHS


def item(index: int, *, created: str, year: int, name: str) -> dict:
    return {
        "external_id": f"01a0-{index:05d}",
        "name": name,
        "type": "movie",
        "is_series": False,
        "year": year,
        "poster_url": f"https://poster.cdnvideohub.com/p/{index}.jpg",
        "tags": ["Драма"],
        "kinopoisk_rating": None,
        "imdb_rating": None,
        "external_ids": {},
        "playback": None,
        "created_at": created,
        "updated_at": created,
    }


def home_html(items) -> str:
    catalog = live_catalog.catalog_from_live(items)
    package = yaml.safe_load(PATHS.site_package("lords-01").read_text(encoding="utf-8"))
    site = render_mod.render_site(package, catalog=catalog, environ={}, publisher_id="10238")
    pages = site.pages if isinstance(site.pages, dict) else {p.path: p for p in site.pages}
    page = pages["/"]
    return page.body if hasattr(page, "body") else str(page)


def latest_block(html: str) -> str:
    """Разметка блока «Последние добавления» и ничего больше."""
    start = html.index("Последние добавления")
    end = html.find("</section>", start)
    return html[start:end]


class TestRecentlyAddedIsOrderedByArrival:
    def test_the_newest_arrival_comes_first_even_with_an_older_year(self):
        items = [
            item(1, created="2026-01-01T00:00:00Z", year=2026, name="Старое поступление"),
            item(2, created="2026-08-27T14:28:29Z", year=2019, name="Свежее поступление"),
        ]
        block = latest_block(home_html(items))
        assert "Свежее поступление" in block, "вчерашнее поступление не попало в блок"
        assert block.index("Свежее поступление") < block.index("Старое поступление"), (
            "порядок задан годом выпуска, а не временем появления записи"
        )

    def test_a_title_added_today_appears_on_the_home_page(self):
        """То, ради чего работает таймер: новое поступление видно сразу."""
        items = [
            item(i, created=f"2026-0{1 + i % 8}-01T00:00:00Z", year=2020 + i % 6,
                 name=f"Каталожный тайтл {i}")
            for i in range(1, 30)
        ]
        items.append(item(99, created="2026-08-27T14:28:29Z", year=2011, name="Призрачный гость"))
        assert "Призрачный гость" in latest_block(home_html(items))

    def test_records_without_a_timestamp_do_not_jump_to_the_front(self):
        """Отсутствие даты — не повод считать запись самой свежей."""
        items = [
            item(1, created="2026-08-27T14:28:29Z", year=2019, name="С датой"),
            item(2, created="", year=2026, name="Без даты"),
        ]
        block = latest_block(home_html(items))
        assert block.index("С датой") < block.index("Без даты"), (
            "запись без времени появления обогнала запись с ним"
        )


class TestTheRestOfTheCatalogueKeepsItsOrder:
    def test_catalogue_listing_is_still_ordered_by_year(self):
        """Каталог — витрина, а не лента поступлений: порядок там другой."""
        items = [
            item(1, created="2026-08-27T14:28:29Z", year=2011, name="Свежая запись старого года"),
            item(2, created="2026-01-01T00:00:00Z", year=2026, name="Давняя запись нового года"),
        ]
        catalog = live_catalog.catalog_from_live(items)
        package = yaml.safe_load(PATHS.site_package("lords-01").read_text(encoding="utf-8"))
        site = render_mod.render_site(package, catalog=catalog, environ={}, publisher_id="1")
        pages = site.pages if isinstance(site.pages, dict) else {p.path: p for p in site.pages}
        html = pages["/catalog/"].body
        cards = re.findall(r'class="card__title"[^>]*>([^<]+)<', html)
        assert cards[0] == "Давняя запись нового года", (
            f"порядок каталога изменился: {cards}"
        )
