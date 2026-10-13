"""Приёмочные тесты games-rpg (вариант party-planner)."""

import copy
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from quest import content  # noqa: E402
from quest.net import Client, Refused  # noqa: E402
from quest.server import App  # noqa: E402
from quest.site import Site  # noqa: E402
from quest.sources import load_all  # noqa: E402


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


def test_sections_and_ownership(app):
    s = app.site
    assert len(s.entries) >= 12
    assert set(s.games) == {g for g, v in s.ownership["games"].items() if v["owner"] == "games-rpg"}
    assert {"personazhi", "bildy", "kvesty", "mehaniki"} <= set(s.sections("baldurs-gate-3"))
    assert s.version and "Patch 8" in s.version.src["name"]


def test_validator_rejects_foreign_game_numbers_tiers():
    assert all(not errs(m) for m in content.load_materials())
    m = mat("klass-voin")
    bad = copy.deepcopy(m)
    bad["game"] = "celeste"
    assert any("принадлежит сайту games-story" in e for e in errs(bad))
    bad = copy.deepcopy(m)
    bad["points"].append("Уровень 13: третья атака")
    assert any("число 13" in e for e in errs(bad))
    bad = copy.deepcopy(m)
    bad["summary"] += " Это лучший билд и имба."
    assert any("запрещённое" in e for e in errs(bad))


def test_parsers_reject_unreliable_tables_and_find_intro():
    by = {r["name"]: r for r in load_all().values()}
    assert by["Fighter"]["progression_parsed"] and [r["level"] for r in by["Fighter"]["progression"]] == list(
        range(1, 13)
    )
    assert not by["Wizard"]["progression_parsed"] and by["Wizard"]["progression"] == []
    for n in ("Shadowheart", "Wyll", "Lae'zel"):
        assert re.search(r"is an? (Origin|recruitable)", by[n]["lead"][0], re.I), n


def test_entry_shows_source_facts(app):
    _, html, _ = get(app, "/baldurs-gate-3/personazhi/gale/")
    for k, v in app.site.by_slug["gale"].abilities:
        assert f"<dt>{k}</dt><dd>{v}</dd>" in html
    _, html, _ = get(app, "/baldurs-gate-3/bildy/klass-voin/")
    assert len(re.findall(r'<tr><th scope="row">\d+</th>', html)) == 12
    _, html, _ = get(app, "/baldurs-gate-3/bildy/klass-volshebnik/")
    assert "Что класс получает по уровням" not in html
    _, html, _ = get(app, "/baldurs-gate-3/kvesty/kvest-spasti-halsina/")
    assert len(re.findall(r'data-check="\d+"', html)) == len(app.site.by_slug["kvest-spasti-halsina"].stages)


def test_party_summary_ties_and_limit(app):
    p = app.site.party("baldurs-gate-3", ["gale", "karlach", "shadowheart"])
    best = {k: (v, {e.slug for e in w}) for k, (v, w) in p["best"].items()}
    assert best["Ловкость"] == (13, {"gale", "karlach", "shadowheart"}) and best["Сила"] == (17, {"karlach"})
    st, html, _ = get(app, "/otryad/", {"p": ["gale", "karlach", "wyll", "astarion", "laezel"]})
    assert st == 200 and "учтены первые четыре" in html and canon(html) is None
    assert html.count('<tr><th scope="row">') == 6
    _, html, _ = get(app, "/otryad/", {"p": ["nikto"]})
    assert "Отряд пока пуст" in html


def test_character_table_sorts_by_ability(app):
    _, html, _ = get(app, "/baldurs-gate-3/personazhi/", {"sort": ["INT"]})
    order = re.findall(r'<th scope="row"><a href="/baldurs-gate-3/personazhi/([a-z]+)/"', html)
    vals = [app.site.by_slug[x].src["abilities"]["INT"] for x in order]
    assert vals == sorted(vals, reverse=True) and canon(html) is None and 'aria-sort="descending"' in html


def test_sitemap_urls_200_canonical_unique(app):
    titles = []
    for p in app.sitemap_urls():
        st, html, _ = get(app, p)
        assert st == 200 and canon(html) == app.site.abs(p), p
        assert len(re.findall(r"<h1[ >]", html)) == 1, p
        titles.append(re.search(r"<title>(.*?)</title>", html).group(1))
    assert len(titles) == len(set(titles))


def test_404s_and_other_sites_games(app):
    for p in ("/celeste/", "/minecraft/", "/baldurs-gate-3/net/", "/baldurs-gate-3/bildy/shadowheart/"):
        assert get(app, p)[0] == 404, p


def test_preview_closed_and_production_switch(app):
    _, html, _ = get(app, "/")
    assert 'content="noindex, nofollow"' in html and 'content="party-planner"' in html
    s = copy.copy(app.site)
    s.cfg = copy.deepcopy(app.site.cfg)
    s.cfg.update(mode="production", production_authorized=True)
    s.cfg["origin"]["production"] = "https://rpg.test"
    _, html, _ = get(App(s), s.entries[0].url)
    assert 'content="index, follow"' in html and canon(html).startswith("https://rpg.test/")
    s.cfg["origin"]["production"] = None
    with pytest.raises(RuntimeError):
        s.abs("/")


def test_network_policy_and_foreign_content(tmp_path):
    with pytest.raises(Refused):
        Client()._check("https://evil.example/")
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"site_id": "games-story", "items": [], "sources": {}, "ownership": {}}))
    with pytest.raises(PermissionError):
        Site(content=p)


def test_no_cross_template_code():
    bad = re.compile(
        r"saga|flora|sezon|udobdom|fooddaily|bakebook|weekplan|techkitchen|wt-template-(?!games-rpg)|/srv/sites", re.I
    )
    for p in ROOT.rglob("*"):
        assert not p.is_symlink(), p
        if (
            p.is_file()
            and p.suffix in (".py", ".html", ".css", ".js", ".yaml")
            and "node_modules" not in p.parts
            and p.name != "test_games_rpg.py"
        ):
            assert not bad.search(p.read_text(errors="replace")), p


def test_price_filter_has_no_false_positive_on_slashing():
    assert content.FORBIDDEN.search("стоит 120 руб.") and content.FORBIDDEN.search("за 300 рублей")
    assert content.FORBIDDEN.search("цена 50 руб")
    assert not content.FORBIDDEN.search("2d6 рубящего урона")


def test_items_section_and_passport_from_source(app):
    s = app.site
    assert "predmety" in s.sections("baldurs-gate-3")
    e = s.by_slug["predmet-phalar-aluve"]
    assert [d["dice"] for d in e.item["damage"]] == ["1d8 + 1", "1d10 + 1"] and e.item["enchantment"] == 1
    _, html, _ = get(app, e.url)
    assert '<dd>1d10 + 1 <span lang="en">Slashing</span></dd>' in html
    _, html, _ = get(app, s.by_slug["predmet-adamantine-splint"].url)
    assert "<dt>Класс доспеха</dt><dd>18</dd>" in html and "gp" not in html  # цена не показывается


def test_meta_descriptions_fit_snippet_and_sections_are_informative(app):
    from quest.server import SNIPPET_MAX, snippet

    assert snippet("Раз. Два три.", 8) == "Раз."
    assert snippet("слово " * 40).endswith("…") and len(snippet("слово " * 40)) <= SNIPPET_MAX
    long_clause = "Начало фразы " + "и ещё слова " * 8 + ", хвост " + "без точки " * 10
    assert snippet(long_clause).endswith("слова…")  # режется по запятой, а не посреди хвоста
    s = app.site
    for path in re.findall(r"<loc>https?://[^/]+(/[^<]*)</loc>", get(app, "/sitemap.xml")[1]):
        _, html, _ = get(app, path)
        desc = re.search(r'<meta name="description" content="([^"]*)"', html).group(1)
        assert 20 <= len(desc) <= SNIPPET_MAX, (path, len(desc))
    # в B «Персонажи» — своя страница-таблица; общий маршрут раздела проверяется на «Билдах»
    from quest.server import plural

    _, html, _ = get(app, "/baldurs-gate-3/bildy/")
    n = len(s.sections("baldurs-gate-3")["bildy"][1])
    word = plural(n, "материал", "материала", "материалов")
    assert f'content="Билды Baldur&#39;s Gate 3: {n} {word} по bg3.wiki, сверено с Patch 8."' in html
