"""Подборки на главной не ссылаются на несуществующие страницы.

Профиль `zona-cinema` включает `collection_cards`, но пакет
`zona-cinema-preview` выключает `content_types.collections`. Рендерер
рисовал полку со ссылками на `/collections/` и карточки подборок, а
страниц в плане сайта не было — битые внутренние ссылки на главной Zona.
"""

from __future__ import annotations

import copy
import re

from factory.lords import fixtures as fx
from factory.lords import preview as preview_mod
from factory.lords import render as render_mod


def _internal_hrefs(html: str) -> list[str]:
    return re.findall(r'href="(/[^"#?]*)"', html)


def test_zona_home_does_not_link_to_disabled_collections():
    package, _ = preview_mod._package("zona-cinema-preview")
    assert package["content_types"]["collections"] is False
    site = render_mod.render_site(package, catalog=fx.build_catalog(), environ={})
    home = site.pages["/"].body
    assert 'data-block="collection_cards"' not in home
    broken = [
        href for href in _internal_hrefs(home)
        if href.startswith("/collections") and href not in site.pages
    ]
    assert broken == [], f"битые ссылки на подборки: {broken}"


def test_collection_cards_render_when_package_enables_collections():
    """Тот же профиль Zona, но с collections: true — полка и страницы есть."""
    package, _ = preview_mod._package("zona-cinema-preview")
    package = copy.deepcopy(package)
    package["content_types"]["collections"] = True
    catalog = fx.build_catalog()
    site = render_mod.render_site(package, catalog=catalog, environ={})
    assert "/collections/" in site.pages
    home = site.pages["/"].body
    assert 'data-block="collection_cards"' in home
    assert "/collections/" in home
    for href in _internal_hrefs(home):
        if href.startswith("/collections"):
            assert href in site.pages, href
