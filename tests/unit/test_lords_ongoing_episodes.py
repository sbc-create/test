"""Витрина не обещает серий, которых нет.

Источник отдаёт по сезону два числа: сколько серий заявлено и сколько
действительно доступно. Адаптер читал только первое, и витрина показывала
«серий 24» там, где посмотреть можно семь.

Это не мелочь и не округление. Зритель выбирает сериал по числу серий, открывает
и находит семь: обещание было ложным, и ложным именно со стороны витрины —
источник сказал правду, её потеряли по дороге.

Масштаб измерен на боевом кэше: из 3 919 записей с сезонами у 272 доступно
меньше заявленного. Это и есть продолжающиеся истории — то самое различие
«выходит» и «завершено», ради которого аниме-портал и заведён.

Правило: показывается доступное, заявленное называется рядом и только когда
отличается. «Серий 7 из 24» — утверждение, которое можно проверить; «серий 24»
на семи доступных — нельзя.
"""

from __future__ import annotations

from factory.lords import live_catalog as live


def сезон(number=1, declared=12, available=None) -> dict:
    entry = {"number": str(number), "episodes_count": declared}
    if available is not None:
        entry["available_episodes_count"] = available
    return entry


class TestДоступноеИЗаявленное:
    def test_показывается_доступное(self):
        seasons = live.seasons_from_detail([сезон(declared=24, available=7)])
        assert len(seasons[0].episodes) == 7, "витрина рисует серии, которых нет"

    def test_заявленное_не_теряется(self):
        seasons = live.seasons_from_detail([сезон(declared=24, available=7)])
        assert seasons[0].declared_episodes == 24

    def test_завершённый_сезон_не_помечается_продолжающимся(self):
        seasons = live.seasons_from_detail([сезон(declared=12, available=12)])
        assert seasons[0].ongoing is False
        assert len(seasons[0].episodes) == 12

    def test_продолжающийся_сезон_помечен(self):
        seasons = live.seasons_from_detail([сезон(declared=24, available=7)])
        assert seasons[0].ongoing is True

    def test_без_сведений_о_доступности_берётся_заявленное(self):
        """Источник промолчал — это не повод объявить сезон неполным."""
        seasons = live.seasons_from_detail([сезон(declared=12, available=None)])
        assert len(seasons[0].episodes) == 12
        assert seasons[0].ongoing is False
        assert seasons[0].declared_episodes == 12

    def test_доступное_больше_заявленного_не_ломает_запись(self):
        """Расхождение в другую сторону бывает: показывается то, что есть."""
        seasons = live.seasons_from_detail([сезон(declared=5, available=8)])
        assert len(seasons[0].episodes) == 8
        assert seasons[0].ongoing is False

    def test_сезон_без_единой_доступной_серии_не_рисуется(self):
        """Пустой сезон — это обещание пустоты, а не сезон."""
        assert live.seasons_from_detail([сезон(declared=12, available=0)]) == ()


class TestРазметкаНазываетСостояние:
    def _страница(self, declared: int, available: int) -> str:
        from factory.lords import preview as preview_mod
        from factory.lords import render as render_mod

        merged = {
            "external_id": "01a07703-338c-7afa-8c09-719efabb29da",
            "name": "Продолжающаяся история",
            "type": "tv", "is_series": True, "year": 2026,
            "external_ids": {"kinopoisk": "1", "imdb": "tt1"},
            "kinopoisk_rating": None, "imdb_rating": None,
            "playback": {"aggregator": "kp", "title_id": "1"},
            "tags": [], "poster_url": "https://poster.invalid/x.webp",
            "seasons": [сезон(declared=declared, available=available)],
        }
        title = live.title_from_item(merged)
        package, _ = preview_mod._package("animedia-preview")
        catalog = live.catalog_from_live([merged])
        site = render_mod.render_site(package, catalog=catalog, environ={},
                                      publisher_id="1",
                                      only_title_slugs=frozenset({title.slug}))
        return site.pages[f"/title/{title.slug}/"].body

    def test_продолжающаяся_история_названа_словами(self):
        html = self._страница(declared=24, available=7)
        # Проверяется формулировка, а не наличие цифр где-нибудь на странице:
        # первая редакция проверки искала «7» и «24» по всему документу и
        # проходила, пока страница ничего об этом не говорила.
        assert "<dt>Серий</dt><dd>7 из 24</dd>" in html, "факт не называет обе величины"
        assert "Сезон 1 · 7 из 24 серий" in html, "заголовок сезона молчит о продолжении"

    def test_завершённая_история_не_обвешана_лишним(self):
        html = self._страница(declared=12, available=12)
        # Ничего лишнего: у завершённого сериала «12 из 12» — шум, а не сведение.
        assert "из 12" not in html
