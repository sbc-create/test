"""Перенесено из варианта B: вход «Что мешает дома» — проблема → инструкции по порядку с прогрессом чек-листа."""

import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from udobdom.server import App  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return App()


def canon(html):
    m = re.search(r'<link rel="canonical" href="([^"]+)"', html)
    return m.group(1) if m else None


def test_all_configured_problems_are_published(app):
    cfg = yaml.safe_load((ROOT / "config" / "problems.yaml").read_text())["problems"]
    assert list(app.site.problems) == [p["slug"] for p in cfg]  # ни одна не скрыта из-за снятого материала


def test_problem_pages(app):
    st, html, _ = app.route("/problemy/", {})
    assert st == 200 and canon(html) == app.site.abs("/problemy/")
    assert html.count('href="/problemy/') >= len(app.site.problems)
    for slug, pr in app.site.problems.items():
        st, html, _ = app.route(f"/problemy/{slug}/", {})
        assert st == 200 and canon(html) == app.site.abs(f"/problemy/{slug}/")
        assert [m.url for m in pr["items"]] == re.findall(r'<h2 class="seq__t"><a href="([^"]+)"', html)
        assert '"@type": "ItemList"' in html or '"@type":"ItemList"' in html
    assert app.route("/problemy/net-takoj/", {})[0] == 404


def test_material_links_back_and_sitemap(app):
    urls = app.sitemap_urls()
    assert "/problemy/" in urls and all(f"/problemy/{s}/" in urls for s in app.site.problems)
    m = app.site.problems["mebel-mozhet-upast"]["items"][0]
    _, html, _ = app.route(m.url, {})
    assert 'class="solves"' in html and 'href="/problemy/mebel-mozhet-upast/"' in html
    _, html, _ = app.route("/", {})
    assert all(f'href="/problemy/{s}/"' in html for s in app.site.problems)
