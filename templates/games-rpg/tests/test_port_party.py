"""Перенесено из варианта B: планировщик отряда (работает без JS)."""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from quest.server import App  # noqa: E402

GID = "baldurs-gate-3"


@pytest.fixture(scope="module")
def app():
    return App()


def canon(html):
    m = re.search(r'<link rel="canonical" href="([^"]+)"', html)
    return m.group(1) if m else None


def test_party_summary_ties_and_limit(app):
    p = app.site.party(GID, ["gale", "karlach", "shadowheart"])
    best = {k: (v, {e.slug for e in w}) for k, (v, w) in p["best"].items()}
    for k, (v, who) in best.items():  # максимум и все его обладатели — из характеристик источника
        ab = {e.slug: e.src["abilities"] for e in p["members"]}
        en = next(c for c, ru in __import__("quest.site", fromlist=["ABIL_RU"]).ABIL_RU.items() if ru == k)
        assert v == max(a[en] for a in ab.values()) and who == {s for s, a in ab.items() if a[en] == v}
    st, html, _ = app.route("/otryad/", {"p": ["gale", "karlach", "wyll", "astarion", "laezel"]})
    assert st == 200 and "учтены первые четыре" in html and canon(html) is None
    assert html.count('<tr><th scope="row">') == 6
    _, html, _ = app.route("/otryad/", {"p": ["nikto"]})
    assert "Отряд пока пуст" in html and canon(html) is None and "Таких спутников в справочнике нет" in html


def test_party_page_indexable_and_linked(app):
    st, html, _ = app.route("/otryad/", {})
    assert st == 200 and canon(html) == app.site.abs("/otryad/")
    assert html.count('name="p"') == len(app.site.characters(GID)) == 9
    assert "/otryad/" in app.sitemap_urls()
    _, html, _ = app.route("/", {})
    assert html.count('href="/otryad/"') >= 2
