"""`catalog=None` не подставляет фикстуру вместо отсутствующего источника.

Docstring `render_site` обещает: при `catalog=None` все типы находятся в
состоянии `blocked_credentials`, разделов не возникает, и рендерер «честно
отдаёт сайт без каталога вместо витрины с выдуманным содержимым».

Код делал обратное: следующей же строкой подставлял `fx.build_catalog()` —
то есть возвращал ровно витрину с выдуманным содержимым, 90 страниц
синтетических произведений. Обещание безопасности существовало только в
тексте.

Ни один вызов в `factory/`, `tools/` и `tests/` на эту подстановку не
опирается: все передают каталог явно. Поэтому поведение приводится к
объявленному, а не наоборот.
"""

from __future__ import annotations

import yaml

from factory.lords import render
from factory.paths import PATHS

SITES = ("lords-01", "lords-02", "lords-03")


def package(site_id: str) -> dict:
    return yaml.safe_load(PATHS.site_package(site_id).read_text(encoding="utf-8"))


def test_no_catalog_means_no_invented_titles():
    for site_id in SITES:
        site = render.render_site(package(site_id), catalog=None)
        title_pages = [p for p in site.pages if p.startswith("/title/")]
        assert not title_pages, (
            f"{site_id}: без источника данных создано {len(title_pages)} страниц "
            f"произведений, например {title_pages[:3]}"
        )


def test_no_catalog_means_every_type_is_blocked():
    site = render.render_site(package("lords-03"), catalog=None)
    states = site.plan.type_states
    active = [name for name, state in states.items() if state.active]
    assert not active, f"без источника данных активны типы: {active}"


def test_no_catalog_still_produces_a_site_rather_than_failing():
    """Отсутствие источника — не авария: служебные страницы остаются."""
    site = render.render_site(package("lords-03"), catalog=None)
    assert "/" in site.pages
    assert "/robots.txt" in site.pages
