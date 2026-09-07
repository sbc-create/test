"""REQ-NAV-CONTRACT: объявленная навигация обслуживается витриной.

Найдено браузерной приёмкой: раздел `/collections/`, объявленный в
`navigation.primary` пакета, отдаёт 404 на всех трёх боевых доменах — хотя
пакет объявляет `collections: True`, blueprint объявляет маршрут, а рендерер
раздел строит.

Первую проверку я написал на фикстурном каталоге, и она прошла: у фикстур
подборки есть. Это и была ловушка — фикстуры отвечают на вопрос «умеет ли
рендерер», а спрашивать надо «доезжает ли раздел до витрины».

Корень: `live_catalog.catalog_from_live(items, collections=())` — оба живых
вызова, в `live_site` и в `fast_path`, подборок не передают никогда. Поэтому
`capabilities()` их не содержит, состояние типа становится `disabled_by_api`, а
причина гласит «источник данных его не подтверждает». Источник об этом не
спрашивали: в договоре CDNVideoHub раздела подборок нет вовсе — есть titles,
seasons, episodes, genres, countries.

Здесь закреплены два обещания. Первое: живой каталог не притворяется, что
подборки у него отсутствуют по вине источника. Второе: пакет не объявляет
пунктом меню то, чего витрина в живом режиме не строит.
"""

from __future__ import annotations

import pytest
import yaml

from factory.lords import content_types as ct
from factory.lords import live_catalog
from factory.paths import PATHS

LORDS_BLUEPRINT = "lords"


def пакеты_lords() -> list[tuple[str, dict]]:
    итог = []
    for путь in sorted((PATHS.root / "sites").glob("*/package.yaml")):
        данные = yaml.safe_load(путь.read_text(encoding="utf-8"))
        if (данные or {}).get("blueprint") == LORDS_BLUEPRINT:
            итог.append((путь.parent.name, данные))
    return итог


def записи_всех_типов() -> list[dict]:
    """Каталог, в котором есть запись каждого типа, доступного из titles.

    Иначе проверка ловила бы не дефект, а бедность своих данных: каталог из
    одного фильма делает «непостроенными» и сериалы, и мультфильмы. Предмет
    проверки — тип, у которого нет канала поставки вовсе, а не тип, которого
    случайно нет в выборке.
    """
    итог = []
    for н, (тип, сериал) in enumerate((("movie", False), ("series", True),
                                       ("cartoon", False), ("anime", False),
                                       ("dorama", False)), start=1):
        итог.append({
            "external_id": f"e-{н}", "name": f"Название {н}", "type": тип,
            "is_series": сериал, "year": 2024,
            "playback": {"aggregator": "kp", "title_id": str(н)},
            "external_ids": {"kinopoisk": str(н)},
            "tags": [тип],
        })
    return итог


class TestЖивойКаталогНеПритворяется:
    def test_живой_каталог_собирается_без_подборок(self):
        каталог = live_catalog.catalog_from_live(записи_всех_типов())
        assert caталог_подборки(каталог) == (), (
            "у живого каталога появились подборки — проверка устарела")

    def test_подборки_не_объявляются_отсутствующими_по_вине_источника(self):
        """Причина обязана отличать «не отдаёт» от «не спрашивали»."""
        каталог = live_catalog.catalog_from_live(записи_всех_типов())
        assert "collections" not in каталог.capabilities(), (
            "проверка бессмысленна: подборки в возможностях уже есть")

        пакет = {"content_types": {"collections": True, "movies": True,
                                   "series": True, "animation": False,
                                   "anime": False, "dorama": False}}
        состояния = ct.resolve(пакет, credentials_available=True,
                               api_capabilities=каталог.capabilities(),
                               source_supports=каталог.supported())
        подборки = состояния["collections"]
        assert подборки.state == ct.UNSUPPORTED_BY_SOURCE, (
            f"состояние подборок — {подборки.state!r} с причиной "
            f"{подборки.reason!r}. Источник об этом не спрашивали: в договоре "
            f"поставщика раздела подборок нет, и валить на него нельзя")


class TestНавигацияНеВрёт:
    @pytest.mark.parametrize("site_id,пакет", пакеты_lords(),
                             ids=[с for с, _ in пакеты_lords()])
    def test_меню_не_обещает_выключенного_типа(self, site_id, пакет):
        каталог = live_catalog.catalog_from_live(записи_всех_типов())
        состояния = ct.resolve(пакет, credentials_available=True,
                               api_capabilities=каталог.capabilities(),
                               source_supports=каталог.supported())
        объявлено = [п["url"] for п
                     in ((пакет.get("navigation") or {}).get("primary") or [])]
        # Предмет — не «типа сейчас нет в выборке», а «типу неоткуда взяться».
        врут = [а for а in объявлено
                if (тип := ТИП_ПО_АДРЕСУ.get(а))
                and состояния[тип].state == ct.UNSUPPORTED_BY_SOURCE]
        assert not врут, (
            f"{site_id}: меню обещает разделы, которым неоткуда взяться: "
            f"{врут}. Либо тип получает канал поставки, либо объявление "
            f"убирается — но обещание, которого никто не обслуживает, "
            f"утверждает неправду о собственном сайте")


#: Пункт меню → тип контента, которым он живёт.
ТИП_ПО_АДРЕСУ = {
    "/movies/": "movies",
    "/series/": "series",
    "/animation/": "animation",
    "/anime/": "anime",
    "/dorama/": "dorama",
    "/collections/": "collections",
}


def caталог_подборки(каталог):
    return tuple(каталог.collections)
