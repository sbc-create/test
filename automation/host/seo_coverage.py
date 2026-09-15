"""Матрица фактического покрытия: домен × сегмент × поле.

Считается раздельно и намеренно. Один общий процент по портфелю скрывает
провалившийся сегмент за благополучными соседями: если у аниме нет описаний,
а у фильмов есть, среднее покажет «неплохо», и никто не узнает, что половина
каталога пуста.

Два знаменателя, и разница между ними — половина смысла отчёта.

`RAW_COVERAGE` считается от всех записей: столько на самом деле есть.
`ELIGIBLE_COVERAGE` — от записей, у которых поле в принципе может быть
заполнено. Рейтинга нет у произведения, которого нет в источнике, и это
`MISSING_SOURCE`, а не ноль по нашей вине. Сопоставить запись с источником не
удалось — `UNMATCHED_IDENTITY`, и это уже наша вина.

Знаменатель фиксируется снимком. Улучшать процент выбрасыванием трудных
записей запрещено, и проверяется это сравнением снимков, а не обещанием.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
from typing import Any

#: Сегменты. Аниме отделено от фильмов и сериалов не по жанру, а по семейству
#: витрины: витрина аниме отвечает на другой запрос, и мерить её вместе с
#: киносайтом значит не мерить ни то, ни другое.
СЕГМЕНТЫ = ("FILMS", "SERIES", "ANIME")

ВИД_В_СЕГМЕНТ = {"Фильм": "FILMS", "Сериал": "SERIES", "Мультфильм": "FILMS"}

#: Поля каталога и подробностей, покрытие которых измеряется.
ПОЛЯ_КАТАЛОГА = ("slug", "title", "year", "kind", "poster", "url")
ПОЛЯ_ПОДРОБНОСТЕЙ = ("name", "original_name", "description", "genres",
                     "poster_url", "year", "type", "external_ids")

#: Источники рейтингов. Считаются раздельно: записать оценку IMDb в поле
#: Кинопоиска — это не «приблизительно то же самое», а подлог.
ИСТОЧНИКИ_РЕЙТИНГА = ("kinopoisk", "imdb", "shikimori", "myanimelist", "amd")


def сегмент(вид: str, семейство: str) -> str:
    if семейство in ("yummy", "animedia"):
        return "ANIME"
    return ВИД_В_СЕГМЕНТ.get(вид or "", "FILMS")


def _пусто(з: Any) -> bool:
    if з is None:
        return True
    if isinstance(з, str):
        return not з.strip()
    if isinstance(з, (list, dict, tuple)):
        return len(з) == 0
    return False


def покрытие_поля(записи: list[dict], поле: str, *,
                  eligible: list[dict] | None = None) -> dict[str, Any]:
    всего = len(записи)
    покрыто = sum(1 for з in записи if not _пусто(з.get(поле)))
    годных = len(eligible) if eligible is not None else всего
    покрыто_годных = (sum(1 for з in eligible if not _пусто(з.get(поле)))
                      if eligible is not None else покрыто)
    return {
        "TOTAL": всего, "COVERED": покрыто,
        "RAW_COVERAGE": round(покрыто / всего, 4) if всего else None,
        "ELIGIBLE": годных, "ELIGIBLE_COVERED": покрыто_годных,
        "ELIGIBLE_COVERAGE": round(покрыто_годных / годных, 4) if годных else None,
    }


def рейтинги(детали: dict[str, dict]) -> dict[str, Any]:
    """Покрытие по каждому источнику раздельно, с разделением причин пропуска.

    `MISSING_SOURCE` — у записи нет идентификатора источника: источник её не
    знает, и требовать оценку не с кого. `UNMATCHED_IDENTITY` — идентификатор
    есть, а оценки нет: сопоставление состоялось, данные не пришли. Это разные
    задачи, и складывать их в один «непокрытый остаток» значит не понимать,
    что чинить.
    """
    из: dict[str, Any] = {}
    всего = len(детали)
    #: Ключи внешних идентификаторов, под которыми источник встречается в
    #: данных. У Кинопоиска их два — исторический `kp` и полный `kinopoisk`.
    АЛИАСЫ = {"kinopoisk": ("kinopoisk", "kp"), "imdb": ("imdb",),
              "shikimori": ("shikimori",), "myanimelist": ("myanimelist", "mal"),
              "amd": ("amd",)}
    for источник in ИСТОЧНИКИ_РЕЙТИНГА:
        имеет_ид = имеет_оценку = 0
        for д in детали.values():
            внешние = д.get("external_ids") or {}
            оценки = д.get("ratings_by_source") or {}
            запись = оценки.get(источник)
            # Оценка засчитывается только при числовом значении. Объект
            # сопоставления без `value` — это доказательство того, что запись
            # нашли, а не того, что её оценили; считать его покрытием значит
            # выдавать найденное за измеренное.
            есть_оценка = isinstance(запись, dict) and isinstance(
                запись.get("value"), (int, float))
            есть_ид = any(внешние.get(а) for а in АЛИАСЫ[источник]) or есть_оценка
            имеет_ид += int(есть_ид)
            имеет_оценку += int(есть_оценка)
        подключён = имеет_оценку > 0
        из[источник] = {
            "TOTAL": всего, "ELIGIBLE": имеет_ид, "COVERED": имеет_оценку,
            "RAW_COVERAGE": round(имеет_оценку / всего, 4) if всего else None,
            "ELIGIBLE_COVERAGE": (round(имеет_оценку / имеет_ид, 4)
                                  if имеет_ид else None),
            "MISSING_SOURCE": всего - имеет_ид,
            # Пока источник не подключён вовсе, непокрытый остаток нельзя
            # называть несопоставленными записями: сопоставлять было не с чем.
            "UNMATCHED_IDENTITY": (имеет_ид - имеет_оценку) if подключён else 0,
            "SOURCE_NOT_INTEGRATED": (имеет_ид if not подключён and имеет_ид
                                      else 0),
        }
    return из


def по_витрине(site_id: str, домен: str, семейство: str,
               каталог: dict, детали: dict[str, dict]) -> dict[str, Any]:
    записи = каталог.get("items", [])
    по_сегментам: dict[str, list[dict]] = {с: [] for с in СЕГМЕНТЫ}
    for з in записи:
        по_сегментам[сегмент(з.get("kind", ""), семейство)].append(з)

    итог: dict[str, Any] = {"site_id": site_id, "domain": домен,
                            "family": семейство,
                            "catalog_revision": каталог.get("revision"),
                            "catalog_total": len(записи),
                            "details_total": len(детали),
                            "segments": {}}
    for с, часть in по_сегментам.items():
        if not часть:
            continue
        слаги = {з.get("slug") for з in часть}
        детали_сегмента = {k: v for k, v in детали.items() if k in слаги}
        поля = {п: покрытие_поля(часть, п) for п in ПОЛЯ_КАТАЛОГА}
        if детали:
            подр = list(детали_сегмента.values())
            for п in ПОЛЯ_ПОДРОБНОСТЕЙ:
                поля[f"details.{п}"] = покрытие_поля(подр, п)
        else:
            # Подробностей нет вовсе — это не нулевое покрытие полей, а
            # отсутствующий источник: измерять нечего, и говорить «0 %»
            # значило бы обвинить витрину в том, чего ей не давали.
            for п in ПОЛЯ_ПОДРОБНОСТЕЙ:
                поля[f"details.{п}"] = {"TOTAL": len(часть), "COVERED": 0,
                                        "RAW_COVERAGE": None,
                                        "ELIGIBLE": 0, "ELIGIBLE_COVERED": 0,
                                        "ELIGIBLE_COVERAGE": None,
                                        "BLOCKED": "подробности каталога не собраны"}
        итог["segments"][с] = {
            "entries": len(часть),
            "details_available": len(детали_сегмента),
            "fields": поля,
            "ratings": рейтинги(детали_сегмента) if детали_сегмента else {
                и: {"TOTAL": len(часть), "ELIGIBLE": 0, "COVERED": 0,
                    "RAW_COVERAGE": None, "ELIGIBLE_COVERAGE": None,
                    "MISSING_SOURCE": len(часть), "UNMATCHED_IDENTITY": 0,
                    "BLOCKED": "подробности каталога не собраны"}
                for и in ИСТОЧНИКИ_РЕЙТИНГА},
        }
    return итог


def отпечаток(матрица: dict) -> str:
    """Подпись снимка: знаменатель нельзя переписать задним числом."""
    основа = {д: {с: v["entries"] for с, v in з["segments"].items()}
              for д, з in матрица.items()}
    return hashlib.sha256(json.dumps(основа, sort_keys=True).encode()).hexdigest()
