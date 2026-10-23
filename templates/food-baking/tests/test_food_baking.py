"""Приёмочные тесты food-baking: контент, SEO, функции, изоляция."""

import copy
import gzip
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bakebook import drafts  # noqa: E402

# Черновики сверяются с закрытыми снимками источников (var/<сайт>/private/*.json.gz): сырой текст страниц
# в git не хранится (права и срок хранения). В чистой копии без var/ эти тесты не выполняются — SKIPPED
# с причиной; в рабочей копии со снимками выполняются как обычно.
NEEDS_PRIVATE = pytest.mark.skipif(
    not any(drafts.PRIVATE.glob("*.json.gz")),
    reason="нет закрытых снимков источников var/<сайт>/private — проверка черновиков не выполнялась",
)

from bakebook.net import Client, Refused, Robots  # noqa: E402
from bakebook.server import App  # noqa: E402
from bakebook.site import Site  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return App()


def get(app, path, q=None):
    return app.route(path, q or {})


def ld(html):
    return [json.loads(x) for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]


def canon(html):
    m = re.search(r'<link rel="canonical" href="([^"]+)"', html)
    return m.group(1) if m else None


# --- контент ---------------------------------------------------------------
def test_at_least_12_full_recipes_in_several_groups(app):
    s = app.site
    assert len(s.recipes) >= 12
    assert len({r.group for r in s.recipes}) >= 5
    assert all(len(r.ingredients) >= 2 and len(r.steps) >= 2 and r.servings for r in s.recipes)


@NEEDS_PRIVATE
def test_all_drafts_pass_validation():
    out = {p.name: drafts.validate(json.loads(p.read_text())) for p in drafts.DRAFTS.glob("*.json")}
    assert not {k: v for k, v in out.items() if v}


def _fixture(tmp_path, monkeypatch):
    """Синтетическая фикстура вместо закрытых снимков: факты и «исходные шаги» во временном каталоге."""
    case = json.loads((ROOT / "tests" / "fixtures" / "validator_case.json").read_text())
    facts, private = tmp_path / "facts", tmp_path / "private"
    facts.mkdir()
    private.mkdir()
    (facts / f"{case['record_id']}.json").write_text(json.dumps(case["facts"], ensure_ascii=False))
    (private / f"{case['record_id']}.json.gz").write_bytes(
        gzip.compress(json.dumps({"steps": case["source_steps"]}, ensure_ascii=False).encode())
    )
    monkeypatch.setattr(drafts, "FACTS", facts)
    monkeypatch.setattr(drafts, "PRIVATE", private)
    return case["draft"]


def test_validator_accepts_clean_fixture(tmp_path, monkeypatch):
    assert drafts.validate(_fixture(tmp_path, monkeypatch)) == []


def test_validator_rejects_invented_oven_number(tmp_path, monkeypatch):
    bad = copy.deepcopy(_fixture(tmp_path, monkeypatch))
    bad["steps"][-1]["text"] += " Выпекайте при 999 градусах."
    assert any("число 999" in e for e in drafts.validate(bad))


def test_validator_rejects_reordered_and_missing_ingredient(tmp_path, monkeypatch):
    bad = copy.deepcopy(_fixture(tmp_path, monkeypatch))
    bad["steps"].reverse()
    bad["ingredients"] = bad["ingredients"][:-1]
    errs = drafts.validate(bad)
    assert any("порядок" in e for e in errs) and any("ингредиенты" in e for e in errs)


def test_drafts_consistent_with_public_facts():
    """Без закрытых снимков: черновики против фактов из git — индексы ингредиентов, номера шагов,
    температура духовки (полная сверка текста — test_all_drafts_pass_validation)."""
    for p in drafts.DRAFTS.glob("*.json"):
        d = json.loads(p.read_text())
        f = json.loads((drafts.FACTS / f"{d['record_id']}.json").read_text())
        assert sorted(i["fact_index"] for i in d["ingredients"]) == list(range(len(f["ingredients"]))), p.name
        n = f.get("step_count")
        if n:
            assert all(0 <= r < n for s in d["steps"] for r in s["source_steps"]), p.name
        oven = {str(x["value_c"]) for x in (f.get("oven") or {}).get("temperatures", [])}
        for s in d["steps"]:
            for x in re.findall(r"(\d+)\s*°C", s["text"]):
                assert x in oven, (p.name, x)


def test_oven_facts_only_from_source(app):
    for r in app.site.recipes:
        mapped = [
            (b, next((k for k, s in enumerate(r.steps) if b["step"] in s["src"]), None)) for b in r.oven["bake_times"]
        ]
        expected = [(b["min"], k + 1) for b, k in mapped if k is not None]
        assert [(t["minutes"], t["step"]) for t in r.timers] == expected
    assert app.site.by_slug["keks-s-kabachkom-i-ananasom"].timers[0]["minutes"] == 80


# --- SEO --------------------------------------------------------------------
def test_sitemap_urls_200_self_canonical_unique_titles(app):
    titles = []
    for path, _ in app.sitemap_urls():
        st, html, _ = get(app, path)
        assert st == 200, path
        assert canon(html) == app.site.abs(path), path
        assert len(re.findall(r"<h1[ >]", html)) == 1, path
        titles.append(re.search(r"<title>(.*?)</title>", html).group(1))
    assert len(titles) == len(set(titles))


def test_recipe_jsonld_matches_visible(app):
    for r in app.site.recipes:
        _, html, _ = get(app, r.url)
        rec = next(x for x in ld(html) if x["@type"] == "Recipe")
        assert len(rec["recipeIngredient"]) == html.count("data-weigh=")  # вариант B: строки таблицы «Отвесить»
        assert len(rec["recipeInstructions"]) == len(re.findall(r'<li id="shag-\d+"', html))
        for k in ("image", "aggregateRating", "author", "nutrition", "video", "review"):
            assert k not in rec


def test_preview_closed_and_production_switch(app):
    _, html, _ = get(app, "/")
    assert 'content="noindex, nofollow"' in html and "Disallow: /" in get(app, "/robots.txt")[1]
    s = copy.copy(app.site)
    s.cfg = copy.deepcopy(app.site.cfg)
    s.cfg.update(mode="production", production_authorized=True)
    s.cfg["origin"]["production"] = "https://baking.test"
    prod = App(s)
    _, html, _ = get(prod, s.recipes[0].url)
    assert 'content="index, follow"' in html and canon(html).startswith("https://baking.test/")
    s2 = copy.copy(s)
    s2.cfg = copy.deepcopy(s.cfg)
    s2.cfg["origin"]["production"] = None
    with pytest.raises(RuntimeError):
        s2.abs("/")


def test_filters_search_not_indexed_and_404s(app):
    _, html, _ = get(app, "/recepty/", {"testo": ["zavarnoe"]})
    assert canon(html) is None
    _, html, _ = get(app, "/poisk/", {"q": ["слива"]})
    assert canon(html) is None and 'class="bcard' in html
    for p in ("/recept/net/", "/testo/drozhzhevoe/", "/teg/limon/", "/oshibki/net/", "/recepty/page/1/"):
        assert get(app, p)[0] == 404, p


def test_tags_on_recipe_link_to_live_pages(app):
    n = 0
    for r in app.site.recipes:
        for href, _ in app.site.tag_links(r):
            n += 1
            assert get(app, href)[0] == 200
    assert n >= 5


def test_pitfalls_link_to_steps(app):
    _, html, _ = get(app, "/oshibki/zavarnoe/")
    for href in re.findall(r'href="(/recept/[^"#]+)#shag-(\d+)"', html):
        st, page, _ = get(app, href[0])
        assert st == 200 and f'id="shag-{href[1]}"' in page


def test_no_fake_media(app):
    for r in app.site.recipes:
        _, html, _ = get(app, r.url)
        assert "<img" not in html and "<video" not in html and "★" not in html


# --- сеть и изоляция ---------------------------------------------------------
@pytest.mark.parametrize(
    "url", ["http://eda.rambler.ru/", "https://evil.example/", "https://127.0.0.1/", "https://eda.rambler.ru:8443/"]
)
def test_network_policy(url):
    with pytest.raises(Refused):
        Client()._check(url)


def test_robots_longest_match():
    r = Robots("User-agent: *\nDisallow: /*?\nAllow: *?page=\n")
    assert r.allows("https://x/a?page=2") and not r.allows("https://x/a?s=1")


def test_foreign_site_content_refused(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"site_id": "food-weekly", "items": []}))
    with pytest.raises(PermissionError):
        Site(content=p)


def test_no_cross_template_references():
    bad = re.compile(r"food-daily|fooddaily|food_daily|wt-template-(?!food-baking)|/srv/sites|\.\./+themes", re.I)
    for p in ROOT.rglob("*"):
        if p.is_symlink():
            pytest.fail(f"симлинк в шаблоне: {p}")
        if (
            p.is_file()
            and p.suffix in (".py", ".html", ".css", ".js", ".yaml")
            and "node_modules" not in p.parts
            and p.name != "test_food_baking.py"
        ):
            assert not bad.search(p.read_text(errors="replace")), p


def test_content_has_no_source_step_text():
    data = json.loads((ROOT / "data" / "content.json").read_text())
    assert data["site_id"] == "food-baking"
    for it in data["items"]:
        assert "_steps" not in it and "editor_notes" not in it


def test_cooling_and_chilling_shown_only_when_action_and_time_are_stated_together(app):
    """Остывание/холодильник — из шага источника: действие и время в одной части шага, время после действия."""
    from bakebook.site import Site

    s = Site()
    assert s.by_slug["pirog-gryaz-missisipi"].rests == [
        {"label": "Остывание", "time": "≈ 1 ч", "step": 5},
        {"label": "В холодильнике", "time": "3–5 ч", "step": 9},
    ]
    # «ещё 15-20 минут до румяности и остудите» — время выпечки, не остывания
    assert s.by_slug["tort-karpatka"].rests == []
    # «оставьте в форме на 10-15 минут, затем … остудите» — время относится к форме, не к остыванию
    assert s.by_slug["bananovyj-hleb"].rests == []
    html = get(app, "/recept/pirog-gryaz-missisipi/")[1]
    assert "В холодильнике" in html and "3–5 ч" in html and 'href="#shag-9"' in html
