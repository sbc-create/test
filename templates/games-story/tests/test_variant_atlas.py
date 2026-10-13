"""Приёмочные тесты варианта C (atlas): персонажи, механики, «где я?» по чекпоинтам — только из источника."""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from saga.server import App  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return App()


def get(app, p, q=None):
    return app.route(p, q or {})


def canon(html):
    m = re.search(r'<link rel="canonical" href="([^"]+)"', html)
    return m.group(1) if m else None


def test_identity_port_storage(app):
    c = app.site.cfg
    assert (c["variant_id"], c["server"]["port"], c["storage_namespace"]) == ("atlas", 8870, "gst-atlas")
    assert not (ROOT / "static" / "js" / "summit.js").exists()


def test_characters_come_from_infoboxes(app):
    chars = app.site.characters("celeste")
    for slug, c in chars.items():
        assert all(c["name"] in g.src.get("characters", []) for g in c["guides"]), slug
        _, html, _ = get(app, f"/igra/celeste/personazh/{slug}/")
        block = re.search(r'<ol class="appear">.*?</ol>', html, re.S).group(0)
        assert block.count("<li>") == len(c["guides"])
    assert chars["madeline"]["guides"] and get(app, "/igra/celeste/personazh/nikto/")[0] == 404


def test_checkpoints_order_and_next(app):
    rows = app.site.checkpoints("celeste")
    assert len(rows) == sum(len(g.checkpoints) for g in app.site.for_game("celeste"))
    order = app.site.for_game("celeste")
    for r in rows:
        cps = r["guide"].checkpoints
        if r["next"]:
            assert cps[cps.index(r["name"], r["n"] - 1) + 1] == r["next"]
        elif r["next_guide"]:
            assert order.index(r["next_guide"]) == order.index(r["guide"]) + 1


def test_where_am_i_filter_states(app):
    st, html, _ = get(app, "/igra/celeste/gde-ya/")
    assert st == 200 and canon(html) == app.site.abs("/igra/celeste/gde-ya/")
    st, html, _ = get(app, "/igra/celeste/gde-ya/", {"q": ["Huge Mess"]})
    assert st == 200 and canon(html) is None and html.count('class="cp"') == 1 and "Celestial Resort" in html
    _, html, _ = get(app, "/igra/celeste/gde-ya/", {"q": ["zzzz"]})
    assert "Такого чекпоинта нет" in html


def test_atlas_pages_in_sitemap(app):
    urls = app.sitemap_urls()
    assert {"/igra/celeste/personazhi/", "/igra/celeste/mehaniki/", "/igra/celeste/gde-ya/"} <= set(urls)
