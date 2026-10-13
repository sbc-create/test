"""Приёмочные тесты food-appliances."""

import copy
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from techkitchen import drafts  # noqa: E402

# Черновики сверяются с закрытыми снимками источников (var/<сайт>/private/*.json.gz): сырой текст страниц
# в git не хранится (права и срок хранения). В чистой копии без var/ эти тесты не выполняются — SKIPPED
# с причиной; в рабочей копии со снимками выполняются как обычно.
NEEDS_PRIVATE = pytest.mark.skipif(
    not any(drafts.PRIVATE.glob("*.json.gz")),
    reason="нет закрытых снимков источников var/<сайт>/private — проверка черновиков не выполнялась",
)

from techkitchen.importer import appliance_facts, mode_names  # noqa: E402
from techkitchen.net import Client, Refused, robots_allow, robots_rules  # noqa: E402
from techkitchen.server import App  # noqa: E402
from techkitchen.site import Site  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return App()


def get(app, p, q=None):
    return app.route(p, q or {})


def canon(html):
    m = re.search(r'<link rel="canonical" href="([^"]+)"', html)
    return m.group(1) if m else None


def test_12_full_recipes_two_appliances(app):
    s = app.site
    assert len(s.recipes) >= 12
    assert {r.appliance for r in s.recipes} >= {"multivarka", "aerogril"}
    for r in s.recipes:
        assert r.appliance_times and (r.modes or r.temperatures), r.slug


@NEEDS_PRIVATE
def test_drafts_valid_and_mode_invention_rejected():
    files = list(drafts.DRAFTS.glob("*.json"))
    assert all(not drafts.validate(json.loads(p.read_text())) for p in files)
    d = json.loads(next(p for p in files if "890d59" in p.name).read_text())
    bad = copy.deepcopy(d)
    bad["steps"][1]["text"] = "Обжарьте мясо на режиме «Турбо» 7–10 минут."
    assert any("режим «Турбо»" in e for e in drafts.validate(bad))
    bad = copy.deepcopy(d)
    bad["steps"][-1]["text"] = "Готовьте на режиме «плов» 95 минут, затем перемешайте."
    assert any("число 95" in e for e in drafts.validate(bad))


def test_mode_parser_handles_alternatives_and_prepositions():
    assert mode_names("Готовить в режиме «плов» или «крупы» в течение 1 часа") == ["плов", "крупы"]
    assert mode_names("Переключить на режим на «‎Тушение» и оставить") == ["Тушение"]
    f = appliance_facts("aerogril", ["Выпекать сырники в аэрогриле 20–25 минут при 180 градусах."])
    assert f["temperatures"][0]["value_c"] == 180 and f["times"][0] == {"min": 20, "max": 25, "step": 0}


def test_parameters_link_to_steps_of_same_recipe(app):
    for r in app.site.recipes:
        _, html, _ = get(app, r.url)
        for k in [m["step"] for m in r.modes] + [t["step"] for t in r.temperatures]:
            assert f'id="shag-{k}"' in html, (r.slug, k)


def test_sitemap_urls_200_canonical_unique(app):
    titles = []
    for p in app.sitemap_urls():
        st, html, _ = get(app, p)
        assert st == 200 and canon(html) == app.site.abs(p), p
        assert len(re.findall(r"<h1[ >]", html)) == 1
        titles.append(re.search(r"<title>(.*?)</title>", html).group(1))
    assert len(titles) == len(set(titles))


def test_recipe_jsonld_visible_and_no_fakes(app):
    for r in app.site.recipes:
        _, html, _ = get(app, r.url)
        ld = [json.loads(x) for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]
        rec = next(x for x in ld if x["@type"] == "Recipe")
        assert len(rec["recipeInstructions"]) == len(re.findall(r'<li id="shag-\d+"', html))
        for k in ("image", "aggregateRating", "author", "nutrition", "video"):
            assert k not in rec


def test_appliance_page_lists_only_its_recipes(app):
    for a in ("multivarka", "aerogril"):
        _, html, _ = get(app, f"/pribor/{a}/")
        found = set(re.findall(r'href="/recept/([a-z0-9-]+)/"', html))
        own = {r.slug for r in app.site.recipes if r.appliance == a}
        assert found == own, a
    _, html, _ = get(app, "/")
    assert 'href="/pribor/gril/"' not in html  # прибор без рецептов не показывается


def test_404_for_empty_appliance_category_mode(app):
    for p in ("/pribor/gril/", "/pribor/multivarka/ryba/", "/rezhim/aerogril-x/", "/recept/net/"):
        assert get(app, p)[0] == 404


def test_preview_closed_production_switch(app):
    _, html, _ = get(app, "/")
    assert 'content="noindex, nofollow"' in html
    s = copy.copy(app.site)
    s.cfg = copy.deepcopy(app.site.cfg)
    s.cfg.update(mode="production", production_authorized=True)
    s.cfg["origin"]["production"] = "https://tech.test"
    _, html, _ = get(App(s), s.recipes[0].url)
    assert 'content="index, follow"' in html and canon(html).startswith("https://tech.test/")


def test_network_and_robots():
    with pytest.raises(Refused):
        Client()._check("https://evil.example/")
    assert not robots_allow(
        robots_rules("User-agent: *\nDisallow: /on/demandware.store/\n"), "https://x/on/demandware.store/a"
    )


def test_foreign_content_refused(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"site_id": "food-daily", "items": []}))
    with pytest.raises(PermissionError):
        Site(content=p)


def test_no_cross_template_code():
    bad = re.compile(r"fooddaily|bakebook|weekplan|wt-template-(?!food-appliances)|/srv/sites|\.\./+themes", re.I)
    for p in ROOT.rglob("*"):
        assert not p.is_symlink(), p
        if (
            p.is_file()
            and p.suffix in (".py", ".html", ".css", ".js")
            and "node_modules" not in p.parts
            and p.name != "test_food_appliances.py"
        ):
            assert not bad.search(p.read_text(errors="replace")), p
