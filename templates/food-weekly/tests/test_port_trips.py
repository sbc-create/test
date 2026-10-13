"""Перенесено из варианта B: покупки плана двумя закупками (пн–ср, чт–вс) и одним списком."""

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


def num(amount):
    return [float(x.replace(",", ".")) for x in re.findall(r"\d+(?:,\d+)?", amount.split(" ")[0])]


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
    st, html, _ = app.route(f"/menyu/{PLAN}/pokupki/", {})
    assert st == 200 and 'id="zakupka-1"' in html and 'id="zakupka-2"' in html and 'id="zakupka-all"' in html
    assert all(f'data-list="{PLAN}:{k}"' in html for k in ("1", "2", "all"))
    assert 'href="#zakupka-1"' in html and 'href="#zakupka-2"' in html


def test_week_links_to_each_trip_keep_swaps(app):
    _, html, _ = app.route(f"/menyu/{PLAN}/", {"s": ["d1-breakfast-0:lenivye-vareniki"]})
    links = re.findall(rf'href="(/menyu/{PLAN}/pokupki/[^"]*#zakupka-[12])"', html)
    assert len(links) == 2 and all("?" in x for x in links)


def test_own_week_list_unchanged(app):
    _, html, _ = app.route("/svoya-nedelya/", {"d1-breakfast": ["lenivye-vareniki"]})
    assert 'data-list="own"' in html and "zakupka-1" not in html
