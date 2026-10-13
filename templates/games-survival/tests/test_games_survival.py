"""Приёмочные тесты games-survival (вариант craft-planner)."""

import copy
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from craft import content  # noqa: E402
from craft.net import Client, Refused  # noqa: E402
from craft.plan import plan, recipe_inputs  # noqa: E402
from craft.server import App  # noqa: E402
from craft.site import Site, own_recipes  # noqa: E402
from craft.sources import load_all, parse_recipes  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return App()


def get(app, p, q=None):
    return app.route(p, q or {})


def canon(html):
    m = re.search(r'<link rel="canonical" href="([^"]+)"', html)
    return m.group(1) if m else None


def mat(slug):
    return json.loads((content.MATERIALS / f"{slug}.json").read_text())


def errs(m):
    return content.validate(m, load_all(), {x["slug"] for x in content.load_materials()})


def slugs(xs):
    return sorted(x.slug for x in xs)


def test_sections_and_ownership(app):
    s = app.site
    assert len(s.entries) >= 12
    assert set(s.games) == {"minecraft"}
    assert {"predmety", "resursy", "biomy"} <= set(s.sections("minecraft"))
    assert s.version and s.version.src["java_current"]


def test_validator_rejects_foreign_game_numbers_and_forbidden():
    assert all(not errs(m) for m in content.load_materials())
    m = mat("fakel")
    bad = copy.deepcopy(m)
    bad["game"] = "celeste"
    assert any("принадлежит сайту games-story" in e for e in errs(bad))
    bad = copy.deepcopy(m)
    bad["summary"] += " Из 5 палок выходит 13 факелов."
    assert any("число 13" in e for e in errs(bad))
    bad = copy.deepcopy(m)
    bad["summary"] += " Лучший гайд, tier S."
    assert any("запрещённое" in e for e in errs(bad))


def test_recipe_graph_comes_from_source(app):
    s = app.site
    by = s.by_slug
    assert slugs(s.made_from(by["doski"])) == ["brevno"]
    assert {"palka", "verstak", "sunduk"} <= set(slugs(s.used_for(by["doski"])))
    assert set(slugs(s.made_from(by["fakel"]))) == {"palka", "ugol"}
    assert set(slugs(s.used_for(by["palka"]))) >= {"fakel", "lestnica"}
    assert "vedro" in slugs(s.used_for(by["zheleznyj-slitok"]))
    # Количества — ровно из сетки источника
    assert ("Ladder", 3) in [(r["result"], r["count"]) for r in by["lestnica"].recipes]
    assert all(r["count"] == 4 for r in by["fakel"].recipes)


def test_recipe_parser_drops_foreign_rows_and_duplicates():
    for rec in load_all().values():
        for r in rec.get("recipes", []):
            assert not re.search(r"[\d%{}\[\]]", r["ingredients"]), r
            assert 1 <= r["slots"] <= 9 and r["count"] >= 1
    r = {"ingredients": "Planks", "slots": 2, "result": "Stick", "count": 4}
    assert own_recipes("Stick", [r, dict(r)]) == [r]
    assert (
        own_recipes("Chest", [{"ingredients": "Chest + Copper", "slots": 2, "result": "Copper Chest", "count": 1}])
        == []
    )
    assert parse_recipes("<p>нет сетки</p>") == []


def test_entry_page_shows_recipes_and_uses(app):
    e = app.site.by_slug["palka"]
    _, html, _ = get(app, e.url)
    assert html.count('<td class="num">') >= len(e.recipes)
    for r in e.recipes:
        assert f"× {r['count']}" in html
    assert 'href="/minecraft/predmety/doski/"' in html and 'href="/minecraft/predmety/fakel/"' in html
    assert 'action="/planirovshchik/"' in html


def test_slot_counts_come_from_source_grid(app):
    s = app.site
    by = s.by_slug
    per = {x.slug: q for x, q in recipe_inputs(s, by["shchit"])[1]}
    assert per == {"doski": 6, "zheleznyj-slitok": 1}
    assert {x.slug: q for x, q in recipe_inputs(s, by["lestnica"])[1]} == {"palka": 7}
    for e in s.entries:
        ri = recipe_inputs(s, e)
        if ri:
            assert sum(q for _, q in ri[1]) == ri[0]["slots"], e.slug


def test_planner_math(app):
    s = app.site
    p = plan(s, s.by_slug["fakel"], 16)
    assert [(st.entry.slug, st.crafts, st.made) for st in p.steps] == [
        ("doski", 1, 4),
        ("palka", 1, 4),
        ("fakel", 4, 16),
    ]
    assert {b.slug: q for b, q in p.base} == {"brevno": 1, "ugol": 4}
    p = plan(s, s.by_slug["shchit"], 1)
    doski = next(st for st in p.steps if st.entry.slug == "doski")
    assert (doski.need, doski.made, doski.surplus) == (6, 8, 2)
    # Слиток делается в печи — для планировщика это базовый ресурс, а не шаг крафта
    assert {b.slug for b, _ in plan(s, s.by_slug["zheleznyj-slitok"], 1).base} == {"zheleznyj-slitok"}
    with pytest.raises(ValueError):
        plan(s, s.by_slug["fakel"], 65)


def test_planner_page_input_validation(app):
    st, html, _ = get(app, "/planirovshchik/", {"item": ["fakel"], "n": ["16"]})
    assert st == 200 and "noindex" in html and canon(html) is None
    assert 'Уголь</a></th><td class="num">4</td>' in html and 'data-plan="fakel-16"' in html
    for q in ({"item": ["fakel"], "n": ["0"]}, {"item": ["fakel"], "n": ["abc"]}, {"item": ["brevno"], "n": ["1"]}):
        st, html, _ = get(app, "/planirovshchik/", q)
        assert st == 400 and 'role="alert"' in html, q
    st, html, _ = get(app, "/planirovshchik/")
    assert st == 200 and canon(html) == app.site.abs("/planirovshchik/")


def test_repair_is_not_a_recipe(app):
    assert all("Damaged" not in r["ingredients"] for r in app.site.by_slug["shchit"].recipes)


def test_sitemap_urls_200_canonical_unique(app):
    titles = []
    for p in app.sitemap_urls():
        st, html, _ = get(app, p)
        assert st == 200 and canon(html) == app.site.abs(p), p
        assert len(re.findall(r"<h1[ >]", html)) == 1, p
        assert 'href="#"' not in html, p
        titles.append(re.search(r"<title>(.*?)</title>", html).group(1))
    assert len(titles) == len(set(titles))


def test_404s_and_other_sites_games(app):
    for p in ("/celeste/", "/baldurs-gate-3/", "/minecraft/net/", "/minecraft/biomy/palka/"):
        assert get(app, p)[0] == 404, p


def test_search(app):
    assert "fakel" in slugs(app.site.search("факел"))
    assert app.site.search("квантовый") == []
    st, html, _ = get(app, "/poisk/", {"q": ["квантовый"]})
    assert st == 200 and "Ничего не нашлось" in html and "noindex" in html


def test_preview_closed_and_production_switch(app):
    _, html, _ = get(app, "/")
    assert 'content="noindex, nofollow"' in html and 'content="craft-planner"' in html
    assert get(app, "/robots.txt")[1].strip().endswith("Disallow: /")
    s = copy.copy(app.site)
    s.cfg = copy.deepcopy(app.site.cfg)
    s.cfg.update(mode="production", production_authorized=True)
    s.cfg["origin"]["production"] = "https://survival.test"
    _, html, _ = get(App(s), s.entries[0].url)
    assert 'content="index, follow"' in html and canon(html).startswith("https://survival.test/")
    s.cfg["origin"]["production"] = None
    with pytest.raises(RuntimeError):
        s.abs("/")


def test_network_policy_and_foreign_content(tmp_path):
    with pytest.raises(Refused):
        Client()._check("https://evil.example/")
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"site_id": "games-rpg", "items": [], "sources": {}, "ownership": {}}))
    with pytest.raises(PermissionError):
        Site(content=p)


def test_no_cross_template_code():
    bad = re.compile(
        r"saga|\bquest\.|flora|sezon|udobdom|fooddaily|bakebook|weekplan|techkitchen|wt-template-(?!games-survival)|/srv/sites",
        re.I,
    )
    for p in ROOT.rglob("*"):
        assert not p.is_symlink(), p
        if (
            p.is_file()
            and p.suffix in (".py", ".html", ".css", ".js", ".yaml")
            and "node_modules" not in p.parts
            and p.name != "test_games_survival.py"
        ):
            assert not bad.search(p.read_text(errors="replace")), p


def test_buildings_in_planner(app):
    s = app.site
    assert "postrojki" in s.sections("minecraft")
    p = plan(s, s.by_slug["zabor"], 6)  # 4 доски + 2 палки → 3 забора
    assert [(st.entry.slug, st.crafts, st.made) for st in p.steps] == [
        ("doski", 3, 12),
        ("palka", 1, 4),
        ("zabor", 2, 6),
    ]
    assert {b.slug: q for b, q in p.base} == {"brevno": 3}
    assert recipe_inputs(s, s.by_slug["krovat"]) is None  # шерсти на сайте нет — не цель планировщика
    _, html, _ = get(app, s.by_slug["dver"].url)
    assert "пока не разобран надёжно" in html


def test_tiered_tool_not_in_planner_but_wood_variants_are(app):
    s = app.site
    assert recipe_inputs(s, s.by_slug["kirka"]) is None  # уровни инструмента — не один предмет
    assert recipe_inputs(s, s.by_slug["doski"]) is not None  # породы дерева — равноценные доски
    assert "kirka" not in {e.slug for e in app.targets()}
