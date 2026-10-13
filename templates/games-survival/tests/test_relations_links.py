"""Связи «из чего → во что» на страницах C (рекомендация владельцу: в приёмке C отдельно не проверялись)."""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from craft.plan import recipe_inputs, uses  # noqa: E402
from craft.server import App  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return App()


def page_links(app, e):
    st, html, _ = app.route(e.url, {})
    assert st == 200
    return set(re.findall(r'href="([^"#?]+)"', html))


def test_every_ingredient_is_linked_from_its_product(app):
    s = app.site
    for e in s.entries:
        links = page_links(app, e)
        ri = recipe_inputs(s, e)
        want = {y.url for y, _ in ri[1]} if ri else {y.url for y in s.made_from(e)}
        assert want <= links, (e.slug, want - links)


def test_every_use_links_both_ways(app):
    s = app.site
    for e in s.entries:
        for x, _, _ in uses(s, e):
            assert x.url in page_links(app, e), (e.slug, x.slug)  # материал → продукт
            assert e.url in page_links(app, x), (x.slug, e.slug)  # продукт → материал


def test_made_from_matches_planner_both_ways(app):
    s = app.site
    for e in s.entries:
        for x, _, _ in uses(s, e):
            assert e in s.made_from(x), (e.slug, x.slug)  # модель связей и планировщик согласованы
