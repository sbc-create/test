"""Фасеты строятся по данным, а не по зашитому словарю.

Дефект наблюдался на боевой витрине lordserial33.biz: страница `/countries/`
отвечала 200 и честно сообщала «Значений с непустым списком: 0», а `/genres/`
показывала три жанра на каталог из 53 тысяч записей.

Причина не в фильтрации — она исправна. `Catalog.countries()` и
`Catalog.genres()` пересекали посчитанное с константами `COUNTRIES` и
`GENRES`, а те содержат фикстурный словарь на английских слагах:
`russia`, `france`, `japan`, `canada` — шесть стран и десять жанров.

Живой источник отдаёт русские названия, и `slugify` даёт транслитерацию:
`ssha`, `velikobritaniya`, `yaponiya`, `franciya`, `kanada`. Замер по
полутора тысячам обогащённых записей: встречено 66 стран, из них в словаре
**ноль**; 64 жанра, из них в словаре **один**.

`canada` и `kanada` — одна страна, и совпасть они не могут никогда.

Значение, которого нет в константе, исчезало молча: ни ошибки, ни записи в
журнале. Страница выглядела исправной и была пустой.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from factory.lords import fixtures as fx  # noqa: E402


def _title(slug: str, *, country_slug: str, country: str,
           genre_slugs: tuple[str, ...], genres: tuple[str, ...]) -> fx.Title:
    return fx.Title(
        slug=slug, name=f"Запись {slug}", original_name="", content_type="movies",
        year=2024, country_slug=country_slug, country=country,
        genre_slugs=genre_slugs, genres=genres, studio="", runtime_min=None,
        age_rating="", summary="", seasons=(),
    )


class TestФасетыОтражаютДанные:
    def _каталог(self) -> fx.Catalog:
        return fx.Catalog(titles=(
            _title("a", country_slug="ssha", country="США",
                   genre_slugs=("komediya",), genres=("комедия",)),
            _title("b", country_slug="ssha", country="США",
                   genre_slugs=("triller",), genres=("триллер",)),
            _title("c", country_slug="kanada", country="Канада",
                   genre_slugs=("komediya", "drama"), genres=("комедия", "драма")),
        ), collections=())

    def test_страны_из_данных_попадают_в_фасет(self):
        countries = {slug: label for slug, label, _ in self._каталог().countries()}
        assert "ssha" in countries, (
            "страна, отсутствующая в зашитом словаре, исчезла из фасета — "
            "именно так /countries/ и оказалась пустой на боевой витрине")
        assert "kanada" in countries

    def test_подпись_страны_берётся_из_данных(self):
        countries = {slug: label for slug, label, _ in self._каталог().countries()}
        assert countries.get("ssha") == "США", (
            f"подпись не из данных: {countries.get('ssha')!r}")

    def test_счёт_по_странам_верен(self):
        counts = {slug: n for slug, _, n in self._каталог().countries()}
        assert counts.get("ssha") == 2
        assert counts.get("kanada") == 1

    def test_жанры_из_данных_попадают_в_фасет(self):
        genres = {slug: label for slug, label, _ in self._каталог().genres()}
        assert "komediya" in genres and "triller" in genres, (
            "жанр вне зашитого словаря исчез из фасета")
        assert genres.get("komediya") == "комедия"

    def test_счёт_по_жанрам_верен(self):
        counts = {slug: n for slug, _, n in self._каталог().genres()}
        assert counts.get("komediya") == 2
        assert counts.get("drama") == 1

    def test_пустой_слаг_в_фасет_не_попадает(self):
        """Запись без страны не создаёт раздел «без страны».

        Пустое значение — отсутствие данных, а не категория: посадочная
        страница под него вела бы в никуда.
        """
        catalog = fx.Catalog(titles=(
            _title("x", country_slug="", country="", genre_slugs=(), genres=()),
        ), collections=())
        assert catalog.countries() == ()
        assert catalog.genres() == ()
