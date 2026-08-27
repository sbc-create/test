"""REQ-LORDS-WATCHABLE-LEAD: главная ведёт туда, где есть что смотреть.

Заказчик открыл сайты и не увидел плеера ни на одном из проверенных тайтлов.
Плеер при этом работал: на странице установившегося тайтла он показывает кадр,
кнопку Play и переключатели сезона, эпизода и озвучки.

Расхождение объяснилось составом главной. Блок «Последние добавления» после
перехода на сортировку по времени поступления стал показывать самые свежие
записи — а у свежих записей контракт воспроизведения чаще всего ещё не заведён:
из двенадцати последних поступлений его имели четыре. Посетитель кликал первые
карточки и в двух случаях из трёх попадал на страницу без видео.

Покрытие каталога при этом оставалось прежним — около 86%. Средняя цифра
скрывала то, что видел человек: витрина вела именно туда, где смотреть нечего.

Проверяется состав ленты, а не общее покрытие.
"""

from __future__ import annotations

import yaml

from factory.lords import live_catalog
from factory.lords import render as render_mod
from factory.paths import PATHS


def item(index: int, *, created: str, playable: bool, name: str) -> dict:
    return {
        "external_id": f"01a0-{index:05d}",
        "name": name,
        "type": "movie",
        "is_series": False,
        "year": 2024,
        "poster_url": f"https://poster.cdnvideohub.com/p/{index}.jpg",
        "tags": ["Драма"],
        "kinopoisk_rating": None,
        "imdb_rating": None,
        "external_ids": {},
        "playback": {"aggregator": "kp", "title_id": str(index)} if playable else None,
        "created_at": created,
        "updated_at": created,
    }


def home_and_catalog(items):
    catalog = live_catalog.catalog_from_live(items)
    package = yaml.safe_load(PATHS.site_package("lords-01").read_text(encoding="utf-8"))
    site = render_mod.render_site(package, catalog=catalog, environ={}, publisher_id="10238")
    pages = site.pages if isinstance(site.pages, dict) else {p.path: p for p in site.pages}
    return pages


def lead_titles(html: str) -> list[str]:
    import re
    start = html.index("Последние добавления")
    end = html.find("</section>", start)
    return re.findall(r'class="card__title"[^>]*>([^<]+)<', html[start:end])


class TestTheLeadBlockOffersSomethingToWatch:
    def test_fresh_but_unplayable_titles_do_not_fill_the_lead(self):
        """Свежесть без видео — не то, ради чего посетитель открыл витрину."""
        items = [
            item(i, created=f"2026-08-27T1{i}:00:00Z", playable=False, name=f"Без видео {i}")
            for i in range(1, 9)
        ] + [
            item(20 + i, created=f"2026-08-2{i}T10:00:00Z", playable=True, name=f"С видео {i}")
            for i in range(1, 9)
        ]
        lead = lead_titles(home_and_catalog(items)["/"].body)
        assert lead, "лента пуста"
        # Инвариант точнее доли: смотрибельные идут первыми, и запись без видео
        # попадает в ленту только когда смотрибельные закончились. Доля зависит
        # от размера блока и от того, сколько записей с видео вообще есть.
        kinds = [name.startswith("С видео") for name in lead]
        first_unplayable = kinds.index(False) if False in kinds else len(kinds)
        assert all(kinds[:first_unplayable]), "порядок нарушен"
        assert not any(kinds[first_unplayable:]), (
            f"запись без видео стоит впереди записи с видео: {lead}"
        )
        assert first_unplayable == 8, (
            f"в ленту попало {first_unplayable} смотрибельных записей из восьми доступных"
        )

    def test_the_lead_is_still_ordered_by_arrival(self):
        """Отбор по смотрибельности не отменяет смысла «последние»."""
        items = [
            item(1, created="2026-01-01T00:00:00Z", playable=True, name="Раннее поступление"),
            item(2, created="2026-08-27T14:00:00Z", playable=True, name="Позднее поступление"),
        ]
        lead = lead_titles(home_and_catalog(items)["/"].body)
        assert lead.index("Позднее поступление") < lead.index("Раннее поступление")

    def test_unplayable_titles_remain_reachable_in_the_catalogue(self):
        """Скрывать записи целиком нельзя: у них есть описание и страница."""
        items = [
            item(1, created="2026-08-27T14:00:00Z", playable=False, name="Свежий без видео"),
            item(2, created="2026-08-01T10:00:00Z", playable=True, name="С видео"),
        ]
        pages = home_and_catalog(items)
        assert "Свежий без видео" in pages["/catalog/"].body, (
            "запись без видео пропала из каталога — она всё ещё часть каталога"
        )

    def test_a_catalogue_without_any_playback_still_shows_a_lead(self):
        """Если смотреть нечего нигде, лента не должна опустеть."""
        items = [
            item(i, created=f"2026-08-2{i}T10:00:00Z", playable=False, name=f"Тайтл {i}")
            for i in range(1, 9)
        ]
        assert lead_titles(home_and_catalog(items)["/"].body), (
            "лента опустела: отбор не должен превращаться в пустой блок"
        )
