"""Приёмочные тесты food-weekly."""

import copy
import json
import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from weekplan import planner  # noqa: E402
from weekplan.net import Refused, robots_allows  # noqa: E402
from weekplan.server import App  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return App()


def get(app, path, q=None):
    return app.route(path, q or {})


def canon(html):
    m = re.search(r'<link rel="canonical" href="([^"]+)"', html)
    return m.group(1) if m else None


def test_three_full_7_day_plans_with_real_refs(app):
    assert len(app.plans) >= 3
    cat = app.catalogs["food-daily"]["items"]
    for p in app.plans.values():
        assert len(p["days"]) == 7
        for d in p["days"]:
            for meal in planner.MEALS:
                assert d[meal], (p["slug"], meal)
                for ref in d[meal]:
                    assert ref["slug"] in cat and cat[ref["slug"]]["content_id"].startswith("fd-")


def test_plan_with_missing_recipe_is_rejected(app):
    cats = copy.deepcopy(app.catalogs)
    cats["food-daily"]["items"].pop("plov-s-kuricej")
    with pytest.raises(planner.PlanError):
        planner.load_plans(cats)


def test_shopping_list_scales_by_people_and_keeps_units_apart(app):
    plan = app.plans["semejnaya-nedelya-na-chetveryh"]
    days, _ = planner.resolve(plan, app.catalogs, {})
    sl = planner.shopping_list(days, plan["people"])
    # ручной пересчёт одного продукта: сумма quantity * people / servings по всем блюдам
    expect = 0.0
    for d in days:
        for meal in planner.MEALS:
            for dish in d[meal]:
                for ing in dish["item"]["ingredients"]:
                    if planner.product_name(ing["name"]) == "Куриные яйца" and ing["unit"] == "pcs" and ing["quantity"]:
                        expect += ing["quantity"] * plan["people"] / dish["item"]["servings"]
    row = next(x for x in sl["items"] if x["name"] == "Куриные яйца" and x["unit"] == "pcs")
    assert row["amount"].startswith(planner.fmt(expect))
    units = {(x["name"], x["unit"]) for x in sl["items"]}
    assert len(units) == len(sl["items"])
    assert not any(x["name"].lower() == "вода" for x in sl["items"])


def test_swap_changes_week_and_list_but_only_within_meal(app):
    plan = app.plans["bystraya-nedelya-dlya-dvoih"]
    ok, _ = planner.resolve(plan, app.catalogs, planner.parse_swaps("d1-breakfast-0:lenivye-vareniki"))
    assert ok[0]["breakfast"][0]["slug"] == "lenivye-vareniki" and ok[0]["breakfast"][0]["swapped"]
    bad, notes = planner.resolve(plan, app.catalogs, planner.parse_swaps("d1-breakfast-0:plov-s-kuricej"))
    assert bad[0]["breakfast"][0]["slug"] == "syrniki-s-ezhevikoj" and notes
    base = planner.shopping_list(planner.resolve(plan, app.catalogs, {})[0], 2)
    assert planner.shopping_list(ok, 2) != base


def test_swap_params_are_sanitized():
    assert planner.parse_swaps("d9-dinner-0:x,d1-lunch-0:<script>,junk") == {}


def test_urls_canonical_and_swaps_not_indexed(app):
    titles = []
    for path in app.sitemap_urls():
        st, html, _ = get(app, path)
        assert st == 200, path
        assert canon(html) == app.abs(path)
        assert len(re.findall(r"<h1[ >]", html)) == 1, path
        titles.append(re.search(r"<title>(.*?)</title>", html).group(1))
    assert len(titles) == len(set(titles))
    _, html, _ = get(app, "/menyu/bystraya-nedelya-dlya-dvoih/", {"s": ["d1-dinner-0:plov-s-kuricej"]})
    assert canon(html) is None


def test_recipe_links_go_to_registry_origin_not_copies(app):
    _, html, _ = get(app, "/menyu/bystraya-nedelya-dlya-dvoih/")
    origin = yaml.safe_load((ROOT / "config" / "network.yaml").read_text())["sites"]["food-daily"]["origin"]["preview"]
    links = re.findall(rf'href="({re.escape(origin)}/recept/[a-z0-9-]+/)"', html)
    assert len(links) >= 21
    assert "Ход работы" not in html and "Как готовить" not in html  # тексты рецептов не копируются


def test_preview_closed_production_needs_domain(app):
    _, html, _ = get(app, "/")
    assert 'content="noindex, nofollow"' in html and "Disallow: /" in get(app, "/robots.txt")[1]
    a2 = App()
    a2.cfg = copy.deepcopy(a2.cfg)
    a2.cfg["mode"] = "production"
    with pytest.raises(RuntimeError):
        a2.abs("/")


def test_404s(app):
    for p in ("/menyu/net/", "/menyu/bystraya-nedelya-dlya-dvoih/den-8/", "/podborki/net/", "/x/"):
        assert get(app, p)[0] == 404


def test_robots_parser():
    assert not robots_allows("User-agent: *\nDisallow: /a\n", "https://x/a/b")
    assert robots_allows("User-agent: *\nDisallow: /*?\nAllow: /*?page=\n", "https://x/l?page=2")


def test_feed_contract_rejects_non_loopback(monkeypatch, tmp_path):
    from weekplan import net

    cfg = {"audit_hosts": [], "sites": {"food-daily": {"catalog_feed": "https://evil.example/api/catalog.v1.json"}}}
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "network.yaml").write_text(json.dumps(cfg))
    monkeypatch.setattr(net, "ROOT", tmp_path)
    with pytest.raises(Refused):
        net.network_feed("food-daily")


def test_no_cross_template_code():
    bad = re.compile(r"fooddaily|bakebook|wt-template-(?!food-weekly)|/srv/sites|\.\./+themes", re.I)
    for p in ROOT.rglob("*"):
        assert not p.is_symlink(), p
        if (
            p.is_file()
            and p.suffix in (".py", ".html", ".css", ".js")
            and "node_modules" not in p.parts
            and p.name != "test_food_weekly.py"
        ):
            assert not bad.search(p.read_text(errors="replace")), p


def test_day_abbreviations_are_correct(app):
    _, html, _ = get(app, "/menyu/")
    for bad in ("<span>Че</span>", "<span>Пя</span>", "<span>Су</span>", "<span>Во</span>"):
        assert bad not in html
    assert "<span>Чт</span>" in html and "<span>Вс</span>" in html


def test_variant_identity_meta(app):
    _, html, _ = app.route("/", {})
    assert '<meta name="site-factory-variant-id" content="own-week">' in html
    assert '<meta name="site-factory-variant-version" content="1">' in html
