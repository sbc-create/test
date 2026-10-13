"""Приёмочные тесты варианта C (index-compare): указатель А–Я и сравнение предметов."""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from quest.server import App  # noqa: E402


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
    assert (c["variant_id"], c["server"]["port"], c["storage_namespace"]) == ("index-compare", 8871, "grpg-index")
    assert not (ROOT / "static" / "js" / "codex.js").exists()


def test_glossary_lists_every_entry_alphabetically(app):
    _, html, _ = get(app, "/")
    names = re.findall(r'<dt><a href="[^"]+" lang="en">([^<]+)</a>', html)
    assert len(names) == len(app.site.entries) and names == sorted(names, key=str.lower)


def test_type_filter_states(app):
    st, html, _ = get(app, "/", {"tip": ["item"]})
    assert st == 200 and canon(html) is None and html.count('class="gl__row"') == 4
    st, html, _ = get(app, "/", {"tip": ["xx"]})
    assert st == 400 and 'role="alert"' in html and canon(html) is None


def test_items_comparison_from_infobox(app):
    st, html, _ = get(app, "/baldurs-gate-3/sravnenie-predmetov/")
    assert st == 200 and html.count('<tr><th scope="row">') == 4
    assert '<td class="num" data-label="КД">18</td>' in html and "gp" not in html
    assert "/baldurs-gate-3/sravnenie-predmetov/" in app.sitemap_urls()
