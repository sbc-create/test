"""Пустой элемент не выводится вовсе.

Пустое поле — не повод выводить пустой тег. `<p class="lede"></p>` невидим, но
не бесплатен: высота у него нулевая, а нижний отступ — четырнадцать пикселей,
и они складываются в мёртвое место между заголовком и содержимым. На четырёх
витринах таких абзацев набиралось сто сорок шесть.

Заодно закрепляется общее правило: элементов с текстовой ролью и без текста на
странице быть не должно.
"""

from __future__ import annotations

import re

import pytest

from factory.lords import fixtures as fx, preview as preview_mod
from factory.lords import render as render_mod

SITES = ("lords-01", "lords-02", "lords-03", "lords-04")

#: Теги, пустота которых означает ошибку сборки, а не оформление. `span` и
#: `div` сюда не входят намеренно: у них бывает чисто раскладочная роль.
ТЕКСТОВЫЕ = ("p", "h1", "h2", "h3", "li", "dd", "dt", "figcaption")


@pytest.fixture(scope="module")
def catalog():
    return fx.build_catalog()


@pytest.mark.parametrize("site_id", SITES)
def test_пустых_абзацев_подзаголовка_нет(site_id, catalog):
    package, _ = preview_mod._package(site_id)
    site = render_mod.render_site(package, catalog=catalog, environ={})
    сколько = sum(page.body.count('<p class="lede"></p>') for page in site.pages.values())
    assert сколько == 0, f"{site_id}: пустых абзацев подзаголовка {сколько}"


@pytest.mark.parametrize("site_id", SITES)
def test_текстовых_элементов_без_текста_нет(site_id, catalog):
    package, _ = preview_mod._package(site_id)
    site = render_mod.render_site(package, catalog=catalog, environ={})
    образец = re.compile(r"<(" + "|".join(ТЕКСТОВЫЕ) + r")\b[^>]*>\s*</\1>")
    находки = []
    for path, page in site.pages.items():
        for m in образец.finditer(page.body):
            находки.append(f"{path}: {m.group(0)}")
    assert находки == [], f"{site_id}: пустые элементы — {находки[:5]}"
