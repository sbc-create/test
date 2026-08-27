"""REQ-LORDS-LIVE-CATALOG: живой каталог рендерится тем же рендерером, что и стенд.

История, ради которой этот модуль существует. У направления Lords есть полный
рендерер: главная с секциями, каталог с пагинацией, жанры, годы, страны,
подборки, расписание, поиск и страницы тайтлов — 152 документа. Он умеет
работать с любым `Catalog`, но `Catalog` собирался только из фикстур.

Живые данные тем временем шли мимо него: отдельный черновой сборщик выкладывал
одну страницу со всем каталогом сразу — 4316 карточек, 988 КБ на запрос, ни
пагинации, ни навигации, ни локализованных типов. Именно это и стояло на трёх
публичных доменах.

Здесь проверяется мост между ними: записи источника превращаются в тот самый
`Catalog`, и ничего не выдумывается по дороге. Поля, которых источник не даёт,
остаются пустыми — и обязаны быть скрыты в разметке, а не показаны как «·  ·».
"""

from __future__ import annotations

import pytest

from factory.lords import fixtures as fx
from factory.lords import live_catalog


def item(**over) -> dict:
    """Запись в том виде, в каком её отдаёт `content_live.normalize_title`."""
    base = {
        "external_id": "01a03cb6-aefe-744b-a824-96cd08fe601b",
        "name": "Бункер",
        "type": "movie",
        "is_series": False,
        "year": 2023,
        "poster_url": "https://poster.cdnvideohub.com/x/bunker.jpg",
        "licensed": True,
        "tags": ["Триллер", "Драма"],
        "kinopoisk_rating": 7.8,
        "imdb_rating": 6.9,
        "external_ids": {"kinopoisk": "1234"},
        "playback": {"aggregator": "kp", "title_id": "1234"},
        "created_at": "2026-08-20T10:00:00Z",
        "updated_at": "2026-08-21T10:00:00Z",
    }
    base.update(over)
    return base


class TestTypeMapping:
    """Тип показывается по-русски или не показывается вовсе."""

    @pytest.mark.parametrize("raw,is_series,expected", [
        ("movie", False, fx.MOVIES),
        ("film", False, fx.MOVIES),
        ("tv", True, fx.SERIES),
        ("series", True, fx.SERIES),
        ("show", True, fx.SERIES),
        ("cartoon", False, fx.ANIMATION),
        ("animated_series", True, fx.ANIMATION),
        ("anime", True, fx.ANIME),
        ("dorama", True, fx.DORAMA),
    ])
    def test_known_types_map_to_the_renderers_vocabulary(self, raw, is_series, expected):
        title = live_catalog.title_from_item(item(type=raw, is_series=is_series))
        assert title is not None
        assert title.content_type == expected

    def test_unknown_type_falls_back_to_the_series_flag(self):
        """`is_series` — подтверждённый факт источника, в отличие от строки типа."""
        assert live_catalog.title_from_item(
            item(type="unheard-of", is_series=True)).content_type == fx.SERIES
        assert live_catalog.title_from_item(
            item(type="unheard-of", is_series=False)).content_type == fx.MOVIES

    def test_raw_provider_value_never_reaches_the_title(self):
        """`cartoon` в карточке — это утечка сырого enum наружу."""
        title = live_catalog.title_from_item(item(type="cartoon", is_series=False))
        assert title.content_type in fx.CONTENT_TYPES if hasattr(fx, "CONTENT_TYPES") else True
        assert title.content_type != "cartoon"


class TestNothingIsInvented:
    def test_absent_fields_stay_empty(self):
        """Источник списка не отдаёт страну, студию, хронометраж и описание."""
        title = live_catalog.title_from_item(item())
        assert title.country == ""
        assert title.studio == ""
        assert title.summary == ""
        assert title.runtime_min == 0
        assert title.age_rating == ""
        assert title.original_name == ""

    def test_tags_become_genres_unchanged(self):
        title = live_catalog.title_from_item(item(tags=["Триллер", "Драма"]))
        assert list(title.genres) == ["Триллер", "Драма"]
        assert all(slug and slug == slug.lower() for slug in title.genre_slugs)

    def test_record_without_a_stable_id_or_name_is_dropped(self):
        assert live_catalog.title_from_item(item(external_id="")) is None
        assert live_catalog.title_from_item(item(name="")) is None

    def test_title_is_not_a_fixture(self):
        """Живая запись обязана честно отличаться от синтетической."""
        title = live_catalog.title_from_item(item())
        assert title.fixture is False
        assert title.source != fx.SOURCE


class TestRatingsKeepTheirSource:
    def test_kinopoisk_and_imdb_are_not_mixed_up(self):
        title = live_catalog.title_from_item(item(kinopoisk_rating=7.8, imdb_rating=6.9))
        assert title.kinopoisk_rating == 7.8
        assert title.imdb_rating == 6.9

    def test_missing_rating_is_none_not_zero(self):
        """Ноль — это оценка. Отсутствие оценки — не ноль."""
        title = live_catalog.title_from_item(item(kinopoisk_rating=None, imdb_rating=None))
        assert title.kinopoisk_rating is None
        assert title.imdb_rating is None


class TestCatalogAssembly:
    def test_slugs_are_unique_and_addressable(self):
        items = [item(external_id=f"id-{i}", name="Бункер") for i in range(3)]
        catalog = live_catalog.catalog_from_live(items)
        slugs = [t.slug for t in catalog.titles]
        assert len(set(slugs)) == len(slugs), f"слаги повторяются: {slugs}"
        for slug in slugs:
            assert catalog.by_slug(slug) is not None

    def test_catalog_is_a_real_catalog_the_renderer_accepts(self):
        catalog = live_catalog.catalog_from_live([item()])
        assert isinstance(catalog, fx.Catalog)
        assert catalog.of_type(fx.MOVIES)

    def test_unusable_records_do_not_abort_the_whole_catalog(self):
        catalog = live_catalog.catalog_from_live([item(), item(name=""), item(external_id="id-2")])
        assert len(catalog.titles) == 2
