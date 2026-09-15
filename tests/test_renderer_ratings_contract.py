"""Исполняемая проверка контракта показа оценок, переданного чату «Шаблоны».

Контракт передаётся не на словах: реализация из handoff-документа лежит здесь
целиком и проверяется теми же тестами, которые получит чат «Шаблоны». Так
принимающая сторона видит не предложение, а работающий код с доказательством.

Живой рендерер этим файлом не затрагивается: функция воспроизведена локально.
"""
from __future__ import annotations

import pytest

# --- реализация из docs/handoff/RENDERER_RATINGS_HANDOFF.md ----------------

ПОДПИСИ = (
    ("kinopoisk",   "kp",         "Кинопоиск"),
    ("imdb",        "imdb",       "IMDb"),
    ("shikimori",   "shikimori",  "Shikimori"),
    ("myanimelist", "mal",        "MyAnimeList"),
    ("amd",         "amd",        "AMD"),
)


def _число(значение):
    """Повторяет поведение рендерера: ноль и нечисловое — не оценка."""
    try:
        ч = float(значение)
    except (TypeError, ValueError):
        return None
    return ч if 0.0 < ч <= 10.0 else None


def оценки(деталь: dict) -> list:
    массив = деталь.get("ratings_by_source") or {}
    собрано = []
    for источник, код, метка in ПОДПИСИ:
        значение = None
        if источник == "kinopoisk":
            значение = _число(деталь.get("kinopoisk_rating"))
        elif источник == "imdb":
            значение = _число(деталь.get("imdb_rating"))
        if значение is None:
            запись = массив.get(источник)
            if isinstance(запись, dict):
                значение = _число(запись.get("value_on_ten", запись.get("value")))
        if значение:
            собрано.append((код, метка, значение))
    return собрано


# --- тестовый контракт ----------------------------------------------------

def test_плоское_поле_первично():
    """Значение из массива не подменяет Кинопоиск и IMDb.

    Плоские поля заполняют только эти два источника. Позволить массиву их
    перебивать значило бы показывать то одно число, то другое в зависимости
    от того, какой прогон добора был последним.
    """
    д = {"kinopoisk_rating": 7.1, "imdb_rating": 6.4,
         "ratings_by_source": {"kinopoisk": {"value_on_ten": 3.0},
                               "imdb": {"value_on_ten": 2.0}}}
    assert оценки(д) == [("kp", "Кинопоиск", 7.1), ("imdb", "IMDb", 6.4)]


def test_shikimori_добавляется_своей_подписью():
    д = {"ratings_by_source": {"shikimori": {"value_on_ten": 6.04}}}
    assert оценки(д) == [("shikimori", "Shikimori", 6.04)]


def test_shikimori_не_подменяет_imdb():
    """Оценка Shikimori не может оказаться подписанной как IMDb.

    Это главный запрет контракта: подпись под числом обязана быть правдой.
    """
    д = {"ratings_by_source": {"shikimori": {"value_on_ten": 8.8}}}
    assert all(код != "imdb" for код, _, _ in оценки(д))
    assert all(код != "kp" for код, _, _ in оценки(д))


def test_amd_и_mal_подписываются_отдельно():
    д = {"ratings_by_source": {"amd": {"value_on_ten": 7.0},
                               "myanimelist": {"value_on_ten": 8.0}}}
    assert оценки(д) == [("mal", "MyAnimeList", 8.0), ("amd", "AMD", 7.0)]


def test_показывается_только_существующее():
    assert оценки({}) == []
    assert оценки({"ratings_by_source": {}}) == []
    assert оценки({"kinopoisk_rating": None, "imdb_rating": ""}) == []


@pytest.mark.parametrize("плохое", [0, 0.0, -1, 10.5, "нет", None])
def test_ноль_и_мусор_не_оценка(плохое):
    assert оценки({"ratings_by_source": {"shikimori": {"value_on_ten": плохое}}}) == []


def test_порядок_устойчив():
    """Порядок задан контрактом, а не порядком ключей в данных."""
    д = {"imdb_rating": 6.0,
         "ratings_by_source": {"shikimori": {"value_on_ten": 7.0},
                               "kinopoisk": {"value_on_ten": 5.0}}}
    assert [к for к, _, _ in оценки(д)] == ["kp", "imdb", "shikimori"]


def test_массив_дополняет_пустое_плоское():
    """Если Кинопоиск придёт только массивом, он встанет в своё поле."""
    д = {"imdb_rating": 6.0,
         "ratings_by_source": {"kinopoisk": {"value_on_ten": 7.7}}}
    assert оценки(д) == [("kp", "Кинопоиск", 7.7), ("imdb", "IMDb", 6.0)]


def test_value_используется_если_нет_приведённого():
    д = {"ratings_by_source": {"shikimori": {"value": 6.5}}}
    assert оценки(д) == [("shikimori", "Shikimori", 6.5)]


def test_совместимость_с_текущим_поведением():
    """На записях без массива результат совпадает с нынешним рендерером."""
    for д in ({"kinopoisk_rating": 7.042, "imdb_rating": 6.3},
              {"kinopoisk_rating": 8.12},
              {"imdb_rating": 5.5},
              {}):
        текущее = []
        кп = _число(д.get("kinopoisk_rating"))
        им = _число(д.get("imdb_rating"))
        if кп: текущее.append(("kp", "Кинопоиск", кп))
        if им: текущее.append(("imdb", "IMDb", им))
        assert оценки(д) == текущее


def test_неизвестный_источник_не_показывается():
    """Источник без объявленной подписи на витрину не попадает."""
    д = {"ratings_by_source": {"нечто": {"value_on_ten": 9.9}}}
    assert оценки(д) == []
