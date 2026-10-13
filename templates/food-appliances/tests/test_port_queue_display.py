"""Перенесено в B: очередь рецептов на прибор (из C) и табло параметров рецепта (из A)."""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from techkitchen.server import App  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return App()


def get(app, p, q=None):
    return app.route(p, q or {})


def canon(html):
    m = re.search(r'<link rel="canonical" href="([^"]+)"', html)
    return m.group(1) if m else None


def test_queue_sums_and_groups_follow_source(app):
    s = app.site
    q = s.queue([r.slug for r in s.recipes])
    for a, d in q.items():
        rs = s.for_appliance(a)
        assert d["min"] == sum(t["min"] for r in rs for t in r.appliance_times)
        assert d["max"] == sum(t["max"] or t["min"] for r in rs for t in r.appliance_times)
        for temp, group in d["groups"].items():
            assert all((r.temperatures[0]["value_c"] if r.temperatures else None) == temp for r in group)
        temps = [t for t in d["groups"] if t is not None]
        assert temps == sorted(temps, reverse=True) and (None not in d["groups"] or list(d["groups"])[-1] is None)


def test_queue_page_states(app):
    st, html, _ = get(app, "/ochered/")
    assert st == 200 and canon(html) == app.site.abs("/ochered/") and 'class="qdev"' not in html
    a, b = app.site.recipes[2], app.site.recipes[3]
    st, html, _ = get(app, "/ochered/", {"r": [a.slug, b.slug, "neizvestno"]})
    assert st == 200 and canon(html) is None and html.count('data-done="') == 2
    assert get(app, "/ochered/", {"r": ["neizvestno"]})[0] == 400
    assert "/ochered/" in app.sitemap_urls()
    _, html, _ = get(app, "/ochered/", {"r": ["neizvestno"]})
    assert 'role="alert"' in html and "noindex" in html


def test_queue_reachable(app):
    _, html, _ = get(app, "/")
    assert html.count('href="/ochered/"') >= 2 and "data-q-link" in html


def test_display_links_to_source_steps(app):
    for r in app.site.recipes:
        _, html, _ = get(app, r.url)
        board = re.search(r'<section class="display".*?</section>', html, re.S).group(0)
        for x in list(r.modes) + list(r.temperatures) + list(r.appliance_times):
            assert f'href="#shag-{x["step"]}"' in board
            assert f'id="shag-{x["step"]}"' in html
        if not r.temperatures:
            assert "не указана" in board
