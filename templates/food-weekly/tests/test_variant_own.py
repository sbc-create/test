"""Приёмочные тесты варианта C (own-week): своя неделя из каталога → список покупок."""

import re
import sys
from pathlib import Path
from urllib.parse import parse_qs

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from weekplan import planner  # noqa: E402
from weekplan.server import App  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return App()


def get(app, p, q=None):
    return app.route(p, q or {})


def canon(html):
    m = re.search(r'<link rel="canonical" href="([^"]+)"', html)
    return m.group(1) if m else None


def test_identity_port_storage(app):
    assert (app.cfg["variant_id"], app.cfg["server"]["port"], app.cfg["storage_namespace"]) == ("own-week", 8873, "fwc")
    assert not (ROOT / "static" / "js" / "planner.js").exists()


def test_only_own_category_accepted(app):
    days, notes = planner.custom_days(
        app.catalogs, {(1, "breakfast"): "plov-s-kuricej", (1, "dinner"): "plov-s-kuricej"}
    )
    assert days[0]["breakfast"] == [] and days[0]["dinner"][0]["slug"] == "plov-s-kuricej" and len(notes) == 1


def test_seed_from_plan_equals_plan_shopping(app):
    slug, plan = next(iter(app.plans.items()))
    _, html, _ = get(app, "/svoya-nedelya/")
    qs = re.search(rf'href="/svoya-nedelya/\?([^"]+)">{re.escape(plan["title"])}<', html).group(1).replace("&amp;", "&")
    q = parse_qs(qs)
    _, own, _ = get(app, "/svoya-nedelya/", q)
    days, _ = planner.resolve(plan, app.catalogs, {})
    first_only = [{m: d[m][:1] for m in planner.MEALS} for d in days]  # своя неделя — одно блюдо на приём пищи
    expected = planner.shopping_list(first_only, plan["people"])
    for it in expected["items"]:
        assert f"<b>{it['amount']}</b>" in own, it["name"]


def test_page_states(app):
    st, html, _ = get(app, "/svoya-nedelya/")
    assert st == 200 and canon(html) == app.abs("/svoya-nedelya/") and html.count("<select") == 21
    st, html, _ = get(app, "/svoya-nedelya/", {"d2-lunch": ["grecheskij-salat"]})
    assert st == 200 and canon(html) is None and 'data-list="own"' in html
    assert get(app, "/svoya-nedelya/", {"lyudi": ["0"]})[0] == 400
    assert "/svoya-nedelya/" in app.sitemap_urls()
