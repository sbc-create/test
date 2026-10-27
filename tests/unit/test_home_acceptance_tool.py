"""Приёмка главной меряет то, что обещает, и не ходит в сеть сама по себе.

Инструмент решает, что считать бедой, и эта логика должна быть проверяема без
браузера: иначе «0 бед» ничего не значит. Здесь проверяется разбор адреса
(стенд по http, витрина по https) и сам счёт бед.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ПУТЬ = КОРЕНЬ / "automation" / "local" / "home-acceptance.py"


@pytest.fixture(scope="module")
def м():
    спец = importlib.util.spec_from_file_location("home_acceptance", ПУТЬ)
    модуль = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(модуль)
    return модуль


def test_схема_адреса_по_месту(м):
    """Стенд отвечает по http, витрина — по https. Прибить https нельзя:
    тогда приёмку не прогнать ДО выпуска."""
    assert м._адрес("127.0.0.1:8731") == "http://127.0.0.1:8731"
    assert м._адрес("localhost:9000") == "http://localhost:9000"
    assert м._адрес("zonafilm.space") == "https://zonafilm.space"
    assert м._адрес("https://animedia.icu/") == "https://animedia.icu"


def test_порог_роста_позиции_назван(м):
    """«Позиция больше нуля» просмотром не является: поставщик отдаёт 0.09 и
    держит её. Признак — рост."""
    assert м.РОСТ_С >= 0.5
    assert м.НАЖАТИЙ >= 2 and м.ОЖИДАНИЕ_С >= 10


def test_осмотр_считает_ссылки_на_просмотр_в_анонсах(м):
    """Главное свойство блока анонсов: в нём не бывает ссылки на /title/."""
    assert "ссылок на просмотр в анонсах" in м.ОСМОТР
    assert "includes('/title/')" in м.ОСМОТР


def test_осмотр_различает_видимые_и_ленивые_обложки(м):
    assert "'обложек без файла'" in м.ОСМОТР
    assert "'обложек ждут прокрутки'" in м.ОСМОТР
    assert "видна(i)" in м.ОСМОТР


def test_технический_прогон_глушит_метрику(м):
    """Иначе приёмка попадает в статистику людей и раздувает показы блоков."""
    текст = ПУТЬ.read_text(encoding="utf-8")
    assert текст.count('route("**mc.yandex.*/**"') >= 3, текст.count('route(')
