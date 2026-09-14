"""Сквозные проверки происхождения данных карточки.

Главное утверждение всего набора одно: поле, пришедшее от поставщика, обязано
дойти до публичного контракта. Всё остальное — его частные случаи.

Проверки идут на настоящих записях живого снимка каталога, а не только на
придуманных. Придуманная запись доказывает, что код делает то, что задумано;
настоящая — что задумано было то, что нужно.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from factory.lords.canonical_projection import (
    ДОСТУПНО, ИЗ_КАТАЛОГА, ИЗ_ДЕТАЛИ, ОЖИДАЕТСЯ, SCHEMA_VERSION,
    Проекция, описание_годное, потери, спроецировать)

СНИМОК = Path("/srv/site-factory/repo/var/lords/lords/catalog-cache/lords-01.json")
ДЕТАЛИ = Path("/srv/site-factory/repo/var/lords/detail-cache")


@pytest.fixture(scope="module")
def каталог() -> list[dict]:
    if not СНИМОК.is_file():
        pytest.fail("снимок каталога недоступен: проверять нечего")
    return json.loads(СНИМОК.read_text(encoding="utf-8"))["items"]


@pytest.fixture(scope="module")
def выборка(каталог) -> list[dict]:
    # Фиксированное зерно: повтор даёт ту же выборку, иначе падение теста
    # невозможно воспроизвести.
    random.seed(20260914)
    return random.sample(каталог, min(2500, len(каталог)))


def деталь_для(ид: str) -> dict | None:
    п = ДЕТАЛИ / f"{ид}.json"
    if not п.is_file():
        return None
    try:
        return (json.loads(п.read_text(encoding="utf-8")).get("detail") or {})
    except (OSError, ValueError):
        return None


# --- главный инвариант -------------------------------------------------------

def test_ни_одно_поле_не_теряется_между_источником_и_контрактом(выборка):
    """Если значение пришло — оно обязано дойти. Это весь смысл задачи."""
    потеряно: dict[str, int] = {}
    for з in выборка:
        д = деталь_для(з["external_id"])
        п = спроецировать(з, д)
        for поле in потери(з, д, п):
            потеряно[поле] = потеряно.get(поле, 0) + 1
    assert not потеряно, f"поля потеряны по дороге: {потеряно}"


def test_канонический_идентификатор_у_всех(выборка):
    for з in выборка:
        п = спроецировать(з, деталь_для(з["external_id"]))
        assert п.id == з["external_id"]
        assert п.schema_version == SCHEMA_VERSION


# --- оценки ------------------------------------------------------------------

def test_оценка_из_каталога_доходит_когда_детали_нет():
    """Ровно тот случай, который терялся: деталь отсутствует, оценка есть."""
    з = {"external_id": "e1", "kinopoisk_rating": 7.4, "imdb_rating": 6.9}
    п = спроецировать(з, None)
    assert п.ratings == {"kinopoisk": 7.4, "imdb": 6.9}
    assert п.ratings_source == {"kinopoisk": ИЗ_КАТАЛОГА, "imdb": ИЗ_КАТАЛОГА}


def test_деталь_уточняет_оценку_но_не_отнимает():
    з = {"external_id": "e2", "kinopoisk_rating": 7.4, "imdb_rating": 6.9}
    п = спроецировать(з, {"kinopoisk_rating": 7.6, "imdb_rating": None})
    assert п.ratings["kinopoisk"] == 7.6
    assert п.ratings_source["kinopoisk"] == ИЗ_ДЕТАЛИ
    assert п.ratings["imdb"] == 6.9, "пустая деталь затёрла оценку каталога"
    assert п.ratings_source["imdb"] == ИЗ_КАТАЛОГА


def test_только_кп():
    п = спроецировать({"external_id": "e3", "kinopoisk_rating": 8.1}, None)
    assert п.ratings == {"kinopoisk": 8.1}
    assert "imdb" not in п.ratings, "отсутствие IMDb не должно ничего добавлять"


def test_только_imdb():
    п = спроецировать({"external_id": "e4", "imdb_rating": 5.5}, None)
    assert п.ratings == {"imdb": 5.5}
    assert "kinopoisk" not in п.ratings


def test_обе_оценки_независимы():
    п = спроецировать({"external_id": "e5", "kinopoisk_rating": 8.1,
                       "imdb_rating": 5.5}, None)
    assert len(п.ratings) == 2 and п.ratings["kinopoisk"] != п.ratings["imdb"]


def test_запись_без_оценок():
    п = спроецировать({"external_id": "e6"}, None)
    assert п.ratings == {} and п.ratings_source == {}


def test_ноль_это_оценка_а_не_её_отсутствие():
    п = спроецировать({"external_id": "e7", "imdb_rating": 0.0}, None)
    assert п.ratings["imdb"] == 0.0


def test_негодная_оценка_отбрасывается():
    for плохое in (-1, 11, "нет", True, [7]):
        п = спроецировать({"external_id": "e8", "imdb_rating": плохое}, None)
        assert "imdb" not in п.ratings, f"принято {плохое!r}"


def test_кп_и_imdb_не_путаются(выборка):
    """Оценка обязана остаться у своего агрегатора."""
    проверено = 0
    for з in выборка:
        д = деталь_для(з["external_id"])
        п = спроецировать(з, д)
        источник_кп = (д or {}).get("kinopoisk_rating")
        if источник_кп is None:
            источник_кп = з.get("kinopoisk_rating")
        if источник_кп is not None and "kinopoisk" in п.ratings:
            assert п.ratings["kinopoisk"] == float(источник_кп)
            проверено += 1
    assert проверено > 0, "не нашлось ни одной записи с КП — проверять нечего"


# --- привязка к источнику ----------------------------------------------------

def test_канонический_идентификатор_не_подставляется_как_источник():
    з = {"external_id": "ent-999", "playback": {"aggregator": "kp"}}
    п = спроецировать(з, None)
    assert п.sources[0].source_id == ""
    assert п.sources[0].availability_status == ОЖИДАЕТСЯ
    assert not п.playable


def test_воспроизводимость_требует_идентификатора_источника():
    з = {"external_id": "e9", "playback": {"aggregator": "mali",
                                           "title_id": "58057"}}
    п = спроецировать(з, None)
    assert п.playable and п.sources[0].source_id == "58057"
    assert п.sources[0].provider == "mali"
    assert п.sources[0].availability_status == ДОСТУПНО


def test_запись_без_playback_не_воспроизводима():
    п = спроецировать({"external_id": "e10"}, None)
    assert п.sources == [] and not п.playable


def test_недоступный_источник_помечен_явно():
    з = {"external_id": "e11", "playback": {"aggregator": "kp",
                                            "title_id": "1", "available": False}}
    п = спроецировать(з, None)
    assert п.sources[0].availability_status == "unavailable"
    assert not п.playable


def test_ни_одна_настоящая_запись_не_получает_чужую_привязку(выборка):
    неверных = 0
    for з in выборка:
        п = спроецировать(з, деталь_для(з["external_id"]))
        for и in п.sources:
            if и.source_id and и.source_id == з["external_id"]:
                неверных += 1
    assert неверных == 0, f"канонический id подставлен как источник: {неверных}"


# --- описание ----------------------------------------------------------------

@pytest.mark.parametrize("заглушка", ["—", "-", "нет описания", "Описание отсутствует",
                                      "N/A", "...", "   ", ""])
def test_заглушка_описанием_не_считается(заглушка):
    assert not описание_годное(заглушка)
    п = спроецировать({"external_id": "e12"}, {"description": заглушка})
    assert п.description is None and п.description_source is None


def test_настоящее_описание_сохраняется_с_источником():
    текст = "Полнометражная история о том, как герой возвращается домой " \
            "после долгого отсутствия и заново узнаёт свою семью."
    п = спроецировать({"external_id": "e13"}, {"description": текст})
    assert п.description == текст
    assert п.description_source == ИЗ_ДЕТАЛИ
    assert п.description_language == "ru"


# --- постер ------------------------------------------------------------------

def test_постер_из_каталога_доходит_когда_детали_нет():
    п = спроецировать({"external_id": "e14",
                       "poster_url": "https://poster/x.webp"}, None)
    assert п.poster == "https://poster/x.webp"
    assert п.poster_source == ИЗ_КАТАЛОГА


# --- внешние идентификаторы --------------------------------------------------

def test_внешние_идентификаторы_объединяются_без_потерь():
    з = {"external_id": "e15", "external_ids": {"kinopoisk": "123"}}
    д = {"external_ids": {"imdb": "tt7", "kinopoisk": "999"}}
    п = спроецировать(з, д)
    # Каталог назван первым намеренно: он и есть основание сопоставления.
    assert п.external_ids["kinopoisk"] == "123"
    assert п.external_ids["imdb"] == "tt7"


def test_пустые_внешние_идентификаторы_не_попадают():
    п = спроецировать({"external_id": "e16",
                       "external_ids": {"imdb": "", "kinopoisk": None}}, None)
    assert п.external_ids == {}


# --- типы контента -----------------------------------------------------------

def test_фильм():
    п = спроецировать({"external_id": "f1", "type": "movie", "year": 2024}, None)
    assert п.type == "movie" and п.seasons == []


def test_сериал_один_сезон():
    д = {"seasons": [{"n": 1, "eps": 12}], "seasons_count": 1}
    п = спроецировать({"external_id": "s1", "type": "tv"}, д)
    assert п.type == "tv" and len(п.seasons) == 1


def test_многосезонный_сериал():
    д = {"seasons": [{"n": 1, "eps": 12}, {"n": 2, "eps": 10},
                     {"n": 3, "eps": 8}], "seasons_count": 3}
    п = спроецировать({"external_id": "s2", "type": "tv"}, д)
    assert len(п.seasons) == 3
    assert [с["n"] for с in п.seasons] == [1, 2, 3]


# --- устойчивость к повтору --------------------------------------------------

def test_проекция_детерминирована(выборка):
    """Повторный вызов даёт тот же результат: иначе сравнивать нечего."""
    for з in выборка[:200]:
        д = деталь_для(з["external_id"])
        a = спроецировать(з, д).as_dict()
        b = спроецировать(з, д).as_dict()
        assert a == b


def test_запись_без_идентификатора_отвергается():
    with pytest.raises(ValueError):
        спроецировать({"name": "без идентификатора"}, None)


# --- защита от подмены сущности ---------------------------------------------

def test_дубли_названий_остаются_разными_записями(каталог):
    """Одинаковое название не делает записи одной сущностью."""
    по_имени: dict[str, set] = {}
    for з in каталог[:8000]:
        по_имени.setdefault(з.get("name", ""), set()).add(з["external_id"])
    дубли = {k: v for k, v in по_имени.items() if len(v) > 1}
    assert дубли, "в выборке нет одноимённых записей — проверять нечего"
    # Проекция обязана сохранить их различными.
    имя, иды = next(iter(дубли.items()))
    записи = [з for з in каталог[:8000] if з["external_id"] in иды]
    проекции = [спроецировать(з, деталь_для(з["external_id"])) for з in записи]
    assert len({п.id for п in проекции}) == len(записи), \
        f"одноимённые записи слились: {имя}"
