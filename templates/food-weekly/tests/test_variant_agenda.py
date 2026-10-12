"""Приёмочные тесты варианта B (agenda-trips): таблица планов, повестка по дням, две закупки."""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from weekplan import planner  # noqa: E402
from weekplan.server import App  # noqa: E402

PLAN = "bystraya-nedelya-dlya-dvoih"


@pytest.fixture(scope="module")
def app():
    return App()


def get(app, p, q=None):
    return app.route(p, q or {})


def num(amount):
    return [float(x.replace(",", ".")) for x in re.findall(r"\d+(?:,\d+)?", amount.split(" ")[0])]


def test_variant_identity_and_port(app):
    _, html, _ = get(app, "/")
    assert '<meta name="site-factory-variant-id" content="agenda-trips">' in html
    assert app.cfg["server"]["port"] == 8865 and "8849" not in app.cfg["origin"]["preview"]


def test_home_table_matches_plans(app):
    _, html, _ = get(app, "/")
    assert html.count('<tr>\n<th scope="row">') == len(app.plans)
    for slug, plan in app.plans.items():
        s = app.summary(slug)
        days, _ = planner.resolve(plan, app.catalogs, {})
        assert s["dishes"] == len({d["slug"] for day in days for m in planner.MEALS for d in day[m]})
        assert f'<td class="num" data-label="Разных блюд">{s["dishes"]}</td>' in html


def test_two_trips_add_up_to_whole_week(app):
    plan = app.plans[PLAN]
    days, _ = planner.resolve(plan, app.catalogs, {})
    whole = {(i["name"], i["unit"]): num(i["amount"]) for i in planner.shopping_list(days, plan["people"])["items"]}
    parts: dict = {}
    for chunk in (days[:3], days[3:]):
        for i in planner.shopping_list(chunk, plan["people"])["items"]:
            q = num(i["amount"])
            prev = parts.get((i["name"], i["unit"]), [0.0] * len(q))
            parts[(i["name"], i["unit"])] = [a + b for a, b in zip(prev, q, strict=False)]
    assert set(parts) == set(whole)
    for k, q in whole.items():
        assert abs(parts[k][0] - q[0]) <= 0.15 * max(1, len(days)), k  # суммы округлены при выводе


def test_shopping_page_has_trips_and_whole(app):
    st, html, _ = get(app, f"/menyu/{PLAN}/pokupki/")
    assert st == 200 and 'id="zakupka-1"' in html and 'id="zakupka-2"' in html
    assert f'data-list="{PLAN}:1"' in html and f'data-list="{PLAN}:2"' in html and f'data-list="{PLAN}:all"' in html


def test_week_is_agenda_with_swaps(app):
    _, html, _ = get(app, f"/menyu/{PLAN}/")
    assert html.count('class="agenda__day"') == 7 and 'class="week"' not in html
    assert html.count('<details class="swap">') == sum(
        len(day[m]) for day in app.plans[PLAN]["days"] for m in planner.MEALS
    )
    key = "d1-dinner-0"
    alt = next(
        a["slug"]
        for a in planner.alternatives(app.catalogs, "food-daily", "dinner")
        if a["slug"] != app.plans[PLAN]["days"][0]["dinner"][0]["slug"]
    )
    st, html, _ = get(app, f"/menyu/{PLAN}/", {"s": [f"{key}:{alt}"]})
    assert st == 200 and "заменено" in html and 'rel="canonical"' not in html


def test_storage_namespace_is_own():
    js = (ROOT / "static" / "js" / "agenda.js").read_text()
    assert '"fwb.bought."' in js and '"fw.' not in js
    assert not (ROOT / "static" / "js" / "planner.js").exists()
