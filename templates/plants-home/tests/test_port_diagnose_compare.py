"""Перенесено из варианта B: «Что случилось?» (симптом → вид → текст справочника) и таблица сравнения видов."""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from flora.server import App  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return App()


def canon(html):
    m = re.search(r'<link rel="canonical" href="([^"]+)"', html)
    return m.group(1) if m else None


def test_diagnose_lists_every_species_problem_from_source(app):
    st, html, _ = app.route("/chto-sluchilos/", {})
    assert st == 200 and canon(html) == app.site.abs("/chto-sluchilos/")
    n = sum(1 for t, ps in app.site.problems().items() for p in ps for x in p.problems if x["tag"] == t)
    assert html.count('<li class="row">') == n and n > 0
    for t in app.site.problems():
        assert f'href="/problema/{t}/"' in html
    assert "/chto-sluchilos/" in app.sitemap_urls()


def test_catalog_sort_and_table(app):
    _, html, _ = app.route("/katalog/", {"sort": ["uhod"], "vid": ["tablica"]})
    assert '<table class="cmp">' in html and canon(html) is None and "noindex" in html
    rows = re.findall(r'<tr><th scope="row"><a href="([^"]+)"', html)
    assert len(rows) == len(app.site.plants)
    order = {"Low": 0, "Medium": 1, "High": 2}
    by_url = {p.url: p for p in app.site.plants}
    ranks = [order.get(by_url[u].maint_en, 3) for u in rows]
    assert ranks == sorted(ranks)
    _, html, _ = app.route("/katalog/", {"sort": ["evil"], "vid": ["evil"]})
    assert canon(html) == app.site.abs("/katalog/") and '<table class="cmp">' not in html


def test_table_never_claims_safety_without_source(app):
    _, html, _ = app.route("/katalog/", {"vid": ["tablica"]})
    for p in app.site.plants:
        row = re.search(rf'<tr><th scope="row"><a href="{re.escape(p.url)}">.*?</tr>', html).group(0)
        if not p.poison and not p.poison_note:
            assert "нет данных" in row and "не ядовито" not in row
