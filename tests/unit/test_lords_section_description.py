"""Meta description раздела не должна быть тавтологией шаблона.

Профиль описывает только те разделы, которыми владеет (и home/search).
Остальные страницы — noindex-навигация: им нельзя придумывать описание
(`test_lords_page_quality.TestDescriptionIsNeverEmpty.test_owned_sections_describe_themselves`).

Прежний fallback `f"{title} каталога."` нарушал это правило и давал бессмыслицу:
«Каталог каталога.», «Новое каталога.», «Жанры каталога.» — на Animedia/Zona,
у которых в профиле нет текстов для catalog/movies/…. Пустой description хуже
отсутствующего; отсутствующий meta-тег — честный исход, уже поддержанный `_page()`.
"""

from __future__ import annotations

import re

import pytest

from factory.lords import fixtures as fx
from factory.lords import preview as preview_mod
from factory.lords import render as render_mod

SITES = ("animedia-preview", "zona-cinema-preview", "lords-01", "lords-04")

#: Шаблоны, которые раньше рождал fallback `"{title} каталога."`.
TAUTOLOGY = re.compile(
    r'name="description" content="(?:Каталог|Новое|Жанры|Годы|Годы выпуска|Страны) каталога\.'
)


@pytest.fixture(scope="module")
def catalog():
    return fx.build_catalog()


@pytest.mark.parametrize("site_id", SITES)
def test_no_tautological_section_description(site_id, catalog):
    package, _ = preview_mod._package(site_id)
    site = render_mod.render_site(package, catalog=catalog, environ={})
    hits = []
    for path, page in site.pages.items():
        if not page.content_type.startswith("text/html"):
            continue
        if TAUTOLOGY.search(page.body):
            hits.append(path)
    assert hits == [], f"{site_id}: тавтологический description на {hits}"


@pytest.mark.parametrize("site_id", ("animedia-preview", "zona-cinema-preview"))
def test_unowned_listing_omits_description_meta(site_id, catalog):
    """У Animedia/Zona нет section-текстов для catalog — meta description нет."""
    package, _ = preview_mod._package(site_id)
    site = render_mod.render_site(package, catalog=catalog, environ={})
    html = site.pages["/catalog/"].body
    assert 'name="description"' not in html, (
        f"{site_id} /catalog/: description выдуман без текста профиля"
    )
    assert 'name="description" content=""' not in html
