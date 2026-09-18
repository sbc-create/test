"""Пустые полки главной не рисуются.

На пустом каталоге `latest_grid` обещал «Последние добавления» и врал
про «выбранные условия» (фильтров на главной нет), а `genre_chips` /
`year_grid` оставляли заголовок над пустым `<ul class="chips">`.

Тот же принцип уже действует для `collection_cards`, `fresh_episodes`,
`type_rows` и `top_rated`: нет содержимого — нет секции.
"""

from __future__ import annotations

import re

import pytest

from factory.lords import fixtures as fx
from factory.lords import preview as preview_mod
from factory.lords import render as render_mod

SITES = ("animedia-preview", "zona-cinema-preview", "lords-01")


@pytest.fixture(scope="module")
def empty_catalog():
    return fx.Catalog(titles=(), collections=())


@pytest.mark.parametrize("site_id", SITES)
def test_empty_catalog_home_has_no_empty_shelves(site_id, empty_catalog):
    package, _ = preview_mod._package(site_id)
    site = render_mod.render_site(package, catalog=empty_catalog, environ={})
    home = site.pages["/"].body
    assert 'data-block="latest_grid"' not in home
    assert "По выбранным условиям" not in home
    assert '<ul class="chips"></ul>' not in home
    assert 'data-block="genre_chips"' not in home
    assert 'data-block="year_grid"' not in home
    assert 'data-block="country_grid"' not in home


@pytest.mark.parametrize("site_id", SITES)
def test_populated_catalog_still_shows_latest_grid(site_id):
    package, _ = preview_mod._package(site_id)
    site = render_mod.render_site(package, catalog=fx.build_catalog(), environ={})
    home = site.pages["/"].body
    assert 'data-block="latest_grid"' in home
    assert re.search(r'class="card"', home)
