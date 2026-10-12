"""Приёмочные тесты games-survival (вариант craft-tree)."""

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


def test_entry_page_shows_recipes_and_links(app):
    e = app.site.by_slug["palka"]
    _, html, _ = get(app, e.url)
    assert html.count('class="rec"') == len(e.recipes)
    for r in e.recipes:
        assert f"× {r['count']}" in html
    assert 'href="/minecraft/predmety/doski/"' in html and 'href="/minecraft/predmety/fakel/"' in html


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
    assert 'content="noindex, nofollow"' in html and 'content="craft-tree"' in html
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
