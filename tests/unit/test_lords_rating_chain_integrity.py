"""Цепочка оценок и идентификаторов: что пришло от источника, то и доходит.

Аудит цепочки (`scripts/lords_chain_audit.py`) на полном боевом каталоге —
53 251 запись — показал ровно одну потерю в слое шаблонов: идентификаторы
внешних источников. Kinopoisk ID есть у 46 695 записей (87,7 %), IMDb ID —
у 44 943 (84,4 %), и до модели шаблона не доходил ни один.

Потеря не безобидная. Идентификатор — это ключ сопоставления: без него оценку
нельзя ни проверить, ни обновить, ни связать с записью у другого поставщика.
Полоса SEO отдельным handoff'ом (041-seo-to-core) уже отказалась выпускать
оценку без происхождения: «число, поставленное неизвестно кем, нельзя ни
проверить, ни объяснить». Идентификатор — половина этого происхождения.

Остальные проверки закрепляют запреты, которые легко нарушить незаметно и
дорого обнаружить: превращение оценки в ноль, приписывание оценки одного
поставщика другому, затирание известного значения пустым ответом.
"""

from __future__ import annotations

import pytest

from factory.lords import detail_enrichment as enrich_mod
from factory.lords import live_catalog as live_mod


def запись(**поля) -> dict:
    """Минимальная запись списочного ответа в форме боевого источника."""
    основа = {
        "external_id": "01a076bf-cbf6-784c-a7f4-73b40a2cb548",
        "name": "Пример",
        "type": "movie",
        "is_series": False,
        "year": 2024,
        "external_ids": {"imdb": "39314864", "kinopoisk": "13608404"},
        "kinopoisk_rating": 7.4,
        "imdb_rating": 6.1,
        "playback": {"aggregator": "kp", "title_id": "13608404"},
        "tags": [],
    }
    основа.update(поля)
    return основа


class TestИдентификаторыДоходятДоМодели:
    def test_идентификатор_кинопоиска_не_теряется(self):
        title = live_mod.title_from_item(запись())
        assert title.kinopoisk_id == "13608404"

    def test_идентификатор_imdb_не_теряется(self):
        title = live_mod.title_from_item(запись())
        assert title.imdb_id == "39314864"

    def test_второе_написание_ключа_понимается(self):
        """Списочный ответ зовёт ключ `kinopoisk`, ответ detail — `kp`.

        Два написания одного и того же — не повод потерять значение на одном
        из путей. Проверено на боевом кэше: в списке ключ `kinopoisk`, в
        обогащении `kp`, значения совпадают.
        """
        title = live_mod.title_from_item(запись(external_ids={"kp": "555", "imdb": "tt7"}))
        assert title.kinopoisk_id == "555"
        assert title.imdb_id == "tt7"

    def test_отсутствие_идентификатора_остаётся_отсутствием(self):
        title = live_mod.title_from_item(запись(external_ids={}))
        assert title.kinopoisk_id is None
        assert title.imdb_id is None

    def test_идентификатор_не_подменяется_чужим(self):
        """Идентификатор Кинопоиска не может оказаться идентификатором IMDb."""
        title = live_mod.title_from_item(
            запись(external_ids={"imdb": "tt0111161", "kinopoisk": "326"}))
        assert title.kinopoisk_id == "326"
        assert title.imdb_id == "tt0111161"
        assert title.kinopoisk_id != title.imdb_id


class TestОценкаНеПревращаетсяВНоль:
    def test_отсутствующая_оценка_остаётся_отсутствующей(self):
        title = live_mod.title_from_item(запись(kinopoisk_rating=None, imdb_rating=None))
        assert title.kinopoisk_rating is None
        assert title.imdb_rating is None

    def test_ноль_от_источника_остаётся_нулём(self):
        """Ноль — это оценка. Отсутствие — не ноль. Смешивать нельзя."""
        title = live_mod.title_from_item(запись(kinopoisk_rating=0, imdb_rating=0.0))
        assert title.kinopoisk_rating == 0.0
        assert title.imdb_rating == 0.0

    def test_логическое_значение_оценкой_не_считается(self):
        title = live_mod.title_from_item(запись(kinopoisk_rating=True))
        assert title.kinopoisk_rating is None

    def test_оценка_вне_шкалы_отвергается_целиком(self):
        """Число вне 0..10 — не «почти оценка», а испорченное значение."""
        assert live_mod.title_from_item(запись(kinopoisk_rating=42)).kinopoisk_rating is None
        assert live_mod.title_from_item(запись(imdb_rating=-1)).imdb_rating is None


class TestОценкиПоставщиковНеСмешиваются:
    def test_оценка_imdb_не_становится_оценкой_кинопоиска(self):
        title = live_mod.title_from_item(запись(kinopoisk_rating=None, imdb_rating=6.1))
        assert title.kinopoisk_rating is None
        assert title.imdb_rating == 6.1

    def test_оценка_кинопоиска_не_становится_оценкой_imdb(self):
        title = live_mod.title_from_item(запись(kinopoisk_rating=7.4, imdb_rating=None))
        assert title.imdb_rating is None
        assert title.kinopoisk_rating == 7.4

    def test_разные_шкалы_не_усредняются(self):
        title = live_mod.title_from_item(запись(kinopoisk_rating=7.4, imdb_rating=6.1))
        assert title.kinopoisk_rating == 7.4 and title.imdb_rating == 6.1


class TestГолосаНеВыдумываются:
    """Ни один слой источника голосов не даёт — измерено на всём каталоге.

    Отсутствие голосов обязано остаться отсутствием: ноль голосов означал бы,
    что оценку не поставил никто, а это утверждение о произведении, которого
    источник не делал.
    """

    def test_голоса_отсутствуют_а_не_равны_нулю(self):
        title = live_mod.title_from_item(запись())
        assert getattr(title, "kinopoisk_votes", None) is None
        assert getattr(title, "imdb_votes", None) is None

    def test_голоса_принимаются_если_источник_их_даст(self):
        """Контракт готов к появлению поля, а не отвергает его."""
        title = live_mod.title_from_item(запись(kinopoisk_votes=1200, imdb_votes=340))
        assert title.kinopoisk_votes == 1200
        assert title.imdb_votes == 340

    def test_ноль_голосов_от_источника_сохраняется(self):
        title = live_mod.title_from_item(запись(kinopoisk_votes=0))
        assert title.kinopoisk_votes == 0


class TestОбогащениеТолькоДобавляет:
    def test_пустой_ответ_не_затирает_известную_оценку(self):
        merged = enrich_mod.merge_detail(запись(), {"kinopoisk_rating": None, "imdb_rating": None})
        assert merged["kinopoisk_rating"] == 7.4
        assert merged["imdb_rating"] == 6.1

    def test_пустой_ответ_не_затирает_идентификаторы(self):
        merged = enrich_mod.merge_detail(запись(), {"external_ids": {}})
        title = live_mod.title_from_item(merged)
        assert title.kinopoisk_id == "13608404"

    def test_обогащение_дополняет_недостающее(self):
        merged = enrich_mod.merge_detail(
            запись(kinopoisk_rating=None), {"kinopoisk_rating": 8.2, "description": "текст"})
        assert merged["kinopoisk_rating"] == 8.2
        assert merged["description"] == "текст"

    def test_воспроизведение_обогащением_не_трогается(self):
        merged = enrich_mod.merge_detail(запись(), {"playback": {"aggregator": "чужой"}})
        assert merged["playback"] == {"aggregator": "kp", "title_id": "13608404"}


class TestОценкаДоживаетДоРазметки:
    """Между моделью и страницей оценка тоже теряется незаметно."""

    @pytest.mark.parametrize("kp,imdb,ожидается", [
        (7.4, 6.1, ("Кинопоиск", "IMDb")),
        (7.4, None, ("Кинопоиск",)),
        (None, 6.1, ("IMDb",)),
    ])
    def test_каждая_имеющаяся_оценка_видна(self, kp, imdb, ожидается):
        from factory.lords import render as render_mod

        title = live_mod.title_from_item(запись(kinopoisk_rating=kp, imdb_rating=imdb))
        html = render_mod._card_rating(title)
        for источник in ожидается:
            assert источник in html, f"{источник} не попал в разметку карточки"
        if kp is None:
            assert "Кинопоиск" not in html
        if imdb is None:
            assert "IMDb" not in html

    def test_без_оценок_разметки_оценки_нет(self):
        from factory.lords import render as render_mod

        html = render_mod._card_rating(
            live_mod.title_from_item(запись(kinopoisk_rating=None, imdb_rating=None)))
        assert "rating" not in html


class TestИдентификаторыДоходятДоРазметки:
    """Модель — не конец пути. Между моделью и страницей значение тоже теряется."""

    def _страница(self, **поля) -> str:
        from factory.lords import live_catalog as lc
        from factory.lords import preview as preview_mod
        from factory.lords import render as render_mod

        merged = запись(**поля)
        title = lc.title_from_item(merged)
        package, _ = preview_mod._package("lords-02")
        catalog = lc.catalog_from_live([merged])
        site = render_mod.render_site(package, catalog=catalog, environ={},
                                      only_title_slugs=frozenset({title.slug}))
        return site.pages[f"/title/{title.slug}/"].body

    def test_оба_идентификатора_видны_машине(self):
        html = self._страница()
        assert 'data-kinopoisk-id="13608404"' in html
        assert 'data-imdb-id="39314864"' in html

    def test_отсутствующий_идентификатор_не_печатается_пустым(self):
        html = self._страница(external_ids={"imdb": "tt1"})
        assert "data-kinopoisk-id=" not in html
        assert 'data-imdb-id="tt1"' in html

    def test_идентификатор_есть_даже_без_оценки(self):
        """Идентификатор — свойство записи, а не оценки: они появляются порознь.

        В боевом каталоге идентификатор Кинопоиска есть у 87,7 % записей, а
        оценка — у 36,8 %. Привязать вывод идентификатора к наличию оценки
        значило бы потерять его у половины каталога.
        """
        html = self._страница(kinopoisk_rating=None, imdb_rating=None)
        assert 'data-kinopoisk-id="13608404"' in html


class TestДлительностьГоворитОДлительности:
    def test_число_серий_не_печатается_как_длительность(self):
        """Было «Длительность: серий 12» — подпись об одном, значение о другом."""
        from factory.lords import fixtures as fx
        from factory.lords import preview as preview_mod
        from factory.lords import render as render_mod

        catalog = fx.build_catalog()
        package, _ = preview_mod._package("lords-01")
        site = render_mod.render_site(package, catalog=catalog, environ={})
        for path, page in site.pages.items():
            if not path.startswith("/title/"):
                continue
            assert "<dt>Длительность</dt><dd>серий" not in page.body, path
