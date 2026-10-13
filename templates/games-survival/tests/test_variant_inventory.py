"""Приёмочные тесты варианта C (inventory-first): что можно сделать из того, что есть."""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from craft.inventory import craftable, needs  # noqa: E402
from craft.server import App  # noqa: E402


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
    assert (c["variant_id"], c["server"]["port"], c["storage_namespace"]) == ("inventory-first", 8872, "gsv-inv")
    assert not (ROOT / "static" / "js" / "plan.js").exists()


def test_quantities_are_slot_counts(app):
    s = app.site
    for e in s.entries:
        for r in e.recipes:
            assert sum(n["qty"] for n in needs(s, r)) == r["slots"], e.slug


def test_planks_and_sticks(app):
    now, almost = craftable(app.site, {"doski", "palka"})
    assert {e.slug for e, *_ in now} == {
        "kirka",
        "topor",
        "lopata",
        "mech",
        "lestnica",
        "palka",
        "stupeni",
        "sunduk",
        "verstak",
        "zabor",
    }
    kirka = next(r for e, r, *_ in now if e.slug == "kirka")
    assert kirka["result"] == "Wooden Pickaxe"  # доски и палки — деревянная кирка, а не «любая»
    miss = {e.slug: [m["title"] for m in ms] for e, r, ns, ms in almost}
    assert miss["fakel"] == ["Coal"] and miss["shchit"] == ["Iron Ingot"] and miss["krovat"] == ["White Wool"]


def test_nothing_from_nothing(app):
    assert craftable(app.site, set()) == ([], [])


def test_page_states(app):
    st, html, _ = get(app, "/iz-togo-chto-est/")
    assert st == 200 and canon(html) == app.site.abs("/iz-togo-chto-est/")
    st, html, _ = get(app, "/iz-togo-chto-est/", {"est": ["doski", "palka"]})
    assert st == 200 and canon(html) is None and "Можно сделать сейчас: 10" in html and "(на сайте нет)" in html
    st, html, _ = get(app, "/iz-togo-chto-est/", {"est": ["almaz"]})
    assert st == 400 and 'role="alert"' in html
