"""Приёмочные тесты plants-home (вариант plant-catalog)."""

import copy
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from flora import content  # noqa: E402
from flora.net import Client, Refused  # noqa: E402
from flora.server import App  # noqa: E402
from flora.site import Site  # noqa: E402
from flora.sources import load_all, parse_ncsu  # noqa: E402


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


def test_twelve_plus_species_with_conditions(app):
    s = app.site
    assert len(s.plants) >= 12
    assert len({p.sci for p in s.plants}) == len(s.plants)
    for p in s.plants:
        assert p.light and p.care and p.checklist and p.raw["producer"]["mode"] == "manual_standin", p.slug


def test_validator_keeps_facts_species_specific():
    assert all(not errs(m) for m in content.load_materials())
    m = mat("aspidistra-vysokaya")
    bad = copy.deepcopy(m)
    bad["problems"] = [{"tag": "tlya", "text": "Бывает тля."}]  # источник аспидистры тлю не называет
    assert any("не названа источником" in e for e in errs(bad))
    bad = copy.deepcopy(m)
    bad["care"][0]["text"] = "Нужно 4 часа солнца."
    assert any("число 4" in e for e in errs(bad))
    bad = copy.deepcopy(m)
    bad["care"][0]["text"] = "В марте переставьте ближе к окну."
    assert any("месяц" in e for e in errs(bad))
    bad = copy.deepcopy(m)
    bad["summary"] = "Подходит всем растениям."
    assert any("запрещённое" in e for e in errs(bad))
    bad = copy.deepcopy(mat("monstera-delikatesnaya"))
    bad["calc"][0]["result"] = "20.0"
    assert any("≠" in e for e in errs(bad))


def test_ncsu_parser_fields_and_problems():
    raw = """<title>Ficus elastica (Rubber Plant) | NC State</title><h1>Ficus elastica Play pronunciation</h1>
    <dl><dt>Light:</dt><dd><span>Partial Shade (Direct sunlight only part of the day, 2-6 hours)</span></dd>
    <dt>Maintenance:</dt><dd><span>Low</span></dd></dl>
    <dt>Description</dt><dd><p>Grow warm.</p>
    <p>Diseases, Insect Pests, and Other Plant Problems:</p><p>Scale can occur.</p>
    <p>Quick ID Hints:</p></dd>"""
    r = parse_ncsu(raw, "u")
    assert r["name"] == "Ficus elastica" and r["attrs"]["Maintenance:"] == ["Low"]
    assert r["problems"] == "Scale can occur." and r["description"] == ["Grow warm."]


def test_sitemap_urls_200_canonical_unique(app):
    titles = []
    for p in app.sitemap_urls():
        st, html, _ = get(app, p)
        assert st == 200 and canon(html) == app.site.abs(p), p
        assert len(re.findall(r"<h1[ >]", html)) == 1, p
        titles.append(re.search(r"<title>(.*?)</title>", html).group(1))
    assert len(titles) == len(set(titles))


def test_toxicity_is_never_invented(app):
    _, html, _ = get(app, "/rastenie/aspidistra-vysokaya/")
    assert "источник не указывает — это не значит, что растение безопасно" in html
    _, html, _ = get(app, "/rastenie/shlyumbergera-dekabrist/")
    assert "источник указывает, что растение не ядовито" in html
    _, html, _ = get(app, "/rastenie/zamiokulkas/")
    assert "средняя (по источнику)" in html


def test_light_and_problem_pages_list_only_matching_species(app):
    for slug in app.site.lights():
        _, html, _ = get(app, f"/svet/{slug}/")
        listed = set(re.findall(r'class="pc__t"><a href="/rastenie/([a-z-]+)/"', html))
        assert listed == {p.slug for p in app.site.plants if slug in p.light_slugs}
    for tag, ps in app.site.problems().items():
        _, html, _ = get(app, f"/problema/{tag}/")
        assert set(re.findall(r'<h2><a href="/rastenie/([a-z-]+)/"', html)) == {p.slug for p in ps}


def test_catalog_filters(app):
    st, html, _ = get(app, "/katalog/", {"svet": ["ten"], "uhod": ["Low"]})
    assert canon(html) is None
    listed = set(re.findall(r'class="pc__t"><a href="/rastenie/([a-z-]+)/"', html))
    assert listed == {p.slug for p in app.site.filter("ten", "Low")} and listed
    _, html, _ = get(app, "/katalog/", {"svet": ["solnce"], "uhod": ["Medium"]})
    assert 'class="empty"' in html and ">Сбросить</a>" in html
    _, html, _ = get(app, "/katalog/", {"svet": ["luna"]})
    assert "Такого фильтра нет" in html


def test_404s(app):
    for p in ("/rastenie/net/", "/svet/luna/", "/problema/net/", "/podborki/net/"):
        assert get(app, p)[0] == 404, p


def test_preview_closed_and_production_switch(app):
    _, html, _ = get(app, "/")
    assert 'content="noindex, nofollow"' in html and 'content="my-collection"' in html
    s = copy.copy(app.site)
    s.cfg = copy.deepcopy(app.site.cfg)
    s.cfg.update(mode="production", production_authorized=True)
    s.cfg["origin"]["production"] = "https://plants.test"
    _, html, _ = get(App(s), s.plants[0].url)
    assert 'content="index, follow"' in html and canon(html).startswith("https://plants.test/")
    s.cfg["origin"]["production"] = None
    with pytest.raises(RuntimeError):
        s.abs("/")


def test_network_policy_and_foreign_content(tmp_path):
    with pytest.raises(Refused):
        Client()._check("https://evil.example/")
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"site_id": "garden-season", "items": [], "sources": {}}))
    with pytest.raises(PermissionError):
        Site(content=p)


def test_no_cross_template_code():
    bad = re.compile(
        r"sezon|udobdom|fooddaily|bakebook|weekplan|techkitchen|wt-template-(?!plants-home)|/srv/sites", re.I
    )
    for p in ROOT.rglob("*"):
        assert not p.is_symlink(), p
        if (
            p.is_file()
            and p.suffix in (".py", ".html", ".css", ".js", ".yaml")
            and "node_modules" not in p.parts
            and p.name != "test_plants_home.py"
        ):
            assert not bad.search(p.read_text(errors="replace")), p
