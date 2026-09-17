"""Базовое покрытие `sites/animedia-preview` — до этой правки его не было вовсе.

Animedia не резолвится к боевому домену (`animedia.icu`/`animedia.space`
заблокированы внешне — DECISIONS.md D136 — и не имеют пакета в этом
репозитории). Единственный пакет Animedia под управлением фабрики —
`sites/animedia-preview` (blueprint `lords`, профиль `animedia-portal`),
собираемый локальным стендом (`factory.lords.preview`) на синтетическом
каталоге, — так же, как остальные пакеты без переданного источника.

Тест проверяет то, что раньше проверялось только для семейства Lords: что
пять поверхностей строятся, что заявленные типы контента действительно не
пусты, что карточки несут изображение (см. test_lords_grid_poster_fallback.py
про сам механизм) и что порядок типов на главной отражает собственное
назначение витрины, а не общий порядок Lords.
"""
from __future__ import annotations

import re

from factory.lords import preview as preview_mod

SITE_ID = "animedia-preview"


def _build():
    return preview_mod.build_preview(SITE_ID)


class TestПятьПоверхностей:
    def test_главная_строится(self):
        result = _build()
        assert "/" in result.site.pages
        assert result.site.pages["/"].body

    def test_каталог_строится(self):
        result = _build()
        assert "/catalog/" in result.site.pages

    def test_подборки_строятся_подборки_включены_в_manifest(self):
        result = _build()
        assert "/collections/" in result.site.pages
        assert result.site.pages["/collections/"].body

    def test_страница_произведения_строится(self):
        result = _build()
        title_pages = [p for p in result.site.pages if p.startswith("/title/")]
        assert title_pages, "ни одной страницы произведения не собралось"

    def test_404_строится(self):
        result = _build()
        assert result.site.not_found is not None
        assert result.site.not_found.body


class TestЗаявленныеТипыНеПусты:
    def test_активные_типы_совпадают_с_manifest(self):
        result = _build()
        # movies/series/animation/anime: true, dorama: false в package.yaml.
        assert set(result.report["active_types"]) >= {
            "movies", "series", "animation", "anime", "collections",
        }
        assert "dorama" not in result.report["active_types"]

    def test_включённый_тип_не_остаётся_без_страниц(self):
        result = _build()
        for kind, path in (("movies", "/movies/"), ("series", "/series/"),
                           ("animation", "/animation/"), ("anime", "/anime/")):
            assert path in result.site.pages, f"тип {kind} включён, но {path} не построен"
            body = result.site.pages[path].body
            assert 'class="card' in body, f"раздел {path} построен пустым"


class TestПостерыНаГлавной:
    def test_карточки_главной_несут_изображение(self):
        result = _build()
        home = result.site.pages["/"].body
        cards = re.findall(r'<article class="card"[^>]*>.*?</article>', home, re.S)
        assert cards, "на главной нет ни одной карточки — нечего проверять"
        without_image = [c for c in cards if "<img" not in c]
        assert not without_image, (
            f"{len(without_image)} из {len(cards)} карточек на главной без изображения"
        )


class TestГлавнаяВедётСвоимНазначением:
    def test_аниме_первым_типом_на_главной(self):
        # purpose профиля animedia-portal и navigation.primary пакета
        # называют аниме первым разделом — это должно быть видно и в
        # порядке активных типов главной, а не только в пункте меню.
        result = _build()
        assert result.report["active_types"][0] == "anime"

    def test_блоки_главной_из_профиля_присутствуют(self):
        result = _build()
        home = result.site.pages["/"].body
        for block in ("hero_search", "fresh_episodes", "calendar", "latest_grid", "genre_chips"):
            assert f'data-block="{block}"' in home, f"блок {block} из профиля не отрисован"


class TestИзоляцияОтДругихПрофилей:
    def test_каталог_помечен_как_синтетический_а_не_боевой(self):
        result = _build()
        assert result.report["catalog"]["source"] == "fixture/test"
        assert "fixture" in result.report["data_source"]

    def test_отчёт_называет_допущенные_блокеры_а_не_молчит_о_них(self):
        result = _build()
        fields = {b["field"] for b in result.report["tolerated_blockers"]}
        assert "content_source.rights_confirmed" in fields, (
            "стенд обязан явно называть, что права на контент не подтверждены"
        )
