"""Приёмочные тесты варианта C (device-queue): очередь рецептов на прибор."""

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


def test_identity_port_storage(app):
    c = app.site.cfg
    assert (c["variant_id"], c["server"]["port"], c["storage_namespace"]) == ("device-queue", 8874, "fac")
    assert not (ROOT / "static" / "css" / "panel.css").exists()


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
