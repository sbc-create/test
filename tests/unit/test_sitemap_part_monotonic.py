"""Монотонность части карты: что считается потерей и как считаются работы.

Повод записан в самом инструменте: у `yummyani.site` между двумя чтениями из
части ушла работа `detektiv-konan` целиком — 1 217 адресов, — а число работ
осталось 36. Поэтому потери считаются по МНОЖЕСТВУ адресов, а работы
печатаются отдельно: одна ушедшая работа весит тысячу адресов.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ПУТЬ = КОРЕНЬ / "automation" / "local" / "sitemap-part-monotonic.py"

спец = importlib.util.spec_from_file_location("sitemap_part_monotonic", ПУТЬ)
модуль = importlib.util.module_from_spec(спец)
assert спец.loader is not None
спец.loader.exec_module(модуль)

А = "https://yummyani.site/anime/detektiv-konan/season/1/episode/"
Б = "https://yummyani.site/anime/tristiya/season/1/episode/"


def test_рост_без_потерь_это_надмножество():
    итог = модуль.сравнить({f"{А}1", f"{А}2"}, {f"{А}1", f"{А}2", f"{Б}1"})
    assert итог["исход"] == модуль.НАДМНОЖЕСТВО
    assert итог["добавилось"] == 1
    assert итог["исчезло"] == 0


def test_исчезновение_адреса_это_потеря():
    итог = модуль.сравнить({f"{А}1", f"{А}2"}, {f"{А}1"})
    assert итог["исход"] == модуль.ПОТЕРИ
    assert итог["исчезло"] == 1
    assert итог["примеры_исчезших"] == [f"{А}2"]


def test_обмен_работами_виден_как_потеря_несмотря_на_число_работ():
    # Ровно случай .site: ушла одна работа (много адресов), пришла другая
    # (мало), число работ не изменилось.
    прежние = {f"{А}{i}" for i in range(1, 6)}
    текущие = {f"{Б}1", f"{Б}2"}
    итог = модуль.сравнить(прежние, текущие)
    assert итог["исход"] == модуль.ПОТЕРИ
    assert итог["исчезло"] == 5
    assert итог["добавилось"] == 2
    assert итог["исчезли_работы"] == ["detektiv-konan"]
    assert итог["добавились_работы"] == ["tristiya"]


def test_полное_совпадение_не_потеря():
    итог = модуль.сравнить({f"{А}1"}, {f"{А}1"})
    assert итог["исход"] == модуль.НАДМНОЖЕСТВО
    assert итог["добавилось"] == 0


def test_пустое_прежнее_множество():
    итог = модуль.сравнить(set(), {f"{А}1"})
    assert итог["исход"] == модуль.НАДМНОЖЕСТВО
    assert итог["было"] == 0


def test_опустевшая_часть_это_потеря():
    итог = модуль.сравнить({f"{А}1"}, set())
    assert итог["исход"] == модуль.ПОТЕРИ
    assert итог["стало"] == 0


@pytest.mark.parametrize("адрес,ожидание", [
    ("https://d/anime/akvarion/season/2/episode/3", "akvarion"),
    ("https://d/title/beybleyd/season-4/episode-2/", "beybleyd"),
    ("https://d/catalog/?genre=komediya", ""),
    ("https://d/", ""),
])
def test_слаг_работы_из_адреса(адрес, ожидание):
    assert модуль.работа(адрес) == ожидание


def test_перечни_работ_ограничены_и_отсортированы():
    прежние = {f"https://d/anime/w{i}/season/1/episode/1" for i in range(20)}
    итог = модуль.сравнить(прежние, set())
    assert len(итог["исчезли_работы"]) == 12
    assert итог["исчезли_работы"] == sorted(итог["исчезли_работы"])


def test_путь_снимка_зависит_от_адреса():
    а = модуль.путь_снимка("https://x/sitemap/episodes.xml")
    б = модуль.путь_снимка("https://x/sitemap/episodes-2.xml")
    assert а != б
    assert а.suffix == ".json"


def test_исходы_различимы():
    assert len({модуль.ПЕРВЫЙ, модуль.НАДМНОЖЕСТВО, модуль.ПОТЕРИ,
                модуль.НЕ_ИЗМЕРЕНО}) == 4
