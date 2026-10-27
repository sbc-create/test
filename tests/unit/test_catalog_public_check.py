"""Проверка каталога отвечает на вопрос, а не на код ответа.

`/catalog/` отдаёт 200 и без единой ссылки на подборки — так и было до 27.10.
Поэтому разбор проверяется отдельно от сети: страница с кодом 200, но без
полосы, обязана считаться бедой, а полоса раздела — не выдаваться за полосу
каталога.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ПУТЬ = КОРЕНЬ / "automation" / "local" / "catalog-collections-public-check.py"


@pytest.fixture(scope="module")
def модуль():
    спец = importlib.util.spec_from_file_location("catalog_public_check", ПУТЬ)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


def test_полоса_каталога_опознаётся(модуль):
    тело = ('<section class="zsec" data-collections="catalog">'
            '<h2>Редакционные подборки</h2>'
            '<a href="/collections/">Все подборки</a>'
            '<a href="/collection/trillery-na-vecher-2026/">Триллеры</a>'
            '<a href="/collection/fantastika-2026/">Фантастика</a></section>')
    р = модуль.разобрать_каталог(тело)
    assert р["метка полосы"] == "catalog"
    assert р["ссылок на подборки"] == 2
    assert р["адреса"] == ["/collection/fantastika-2026/",
                           "/collection/trillery-na-vecher-2026/"]
    assert р["ссылка на хаб"] is True


def test_полоса_раздела_не_выдаётся_за_каталог(модуль):
    тело = ('<section data-collections="section"><h2>Подборки этого раздела</h2>'
            '<a href="/collection/fantastika-2026/">Ф</a></section>')
    assert модуль.разобрать_каталог(тело)["метка полосы"] == "section"


def test_страница_без_полосы_это_пробел(модуль):
    тело = '<div class="zwrap"><a href="/collections/">Подборки</a></div>'
    р = модуль.разобрать_каталог(тело)
    assert р["метка полосы"] is None
    assert р["ссылок на подборки"] == 0
    # Ссылка на хаб есть — и именно так выглядело состояние до правки.
    assert р["ссылка на хаб"] is True


def test_дубли_адресов_не_раздувают_счёт(модуль):
    тело = ('data-collections="catalog"'
            '<a href="/collection/a-b/">1</a><a href="/collection/a-b/">2</a>')
    assert модуль.разобрать_каталог(тело)["ссылок на подборки"] == 1


def test_цели_разбираются_и_третий_аргумент_виден(модуль):
    добро = ("<script>var C=112582938,L=[\"title_view\"];"
             "window.__sfGoal=g;window.__sfGoalOnce('title_view');</script>")
    р = модуль.разобрать_цели(добро)
    assert р["точка отправки"] and р["цель title_view"]
    assert р["счётчик"] == "112582938"
    assert р["третий аргумент у отправки"] is False
    # Вызов «с данными» — то, чего быть не должно: поисковая фраза ушла бы в отчёт.
    худо = "window.ym(C,'reachGoal',n,{q:phrase});window.__sfGoal=g;"
    assert модуль.разобрать_цели(худо)["третий аргумент у отправки"] is True
