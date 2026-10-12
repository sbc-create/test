"""Приёмочные тесты home-practical (вариант rooms-cards)."""

import copy
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from udobdom import content  # noqa: E402
from udobdom.net import Client, Refused  # noqa: E402
from udobdom.server import App  # noqa: E402
from udobdom.site import Site  # noqa: E402
from udobdom.sources import load_all, parse_ikea  # noqa: E402


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
    mats = content.load_materials()
    return content.validate(m, load_all(), {x["slug"] for x in mats})


def test_twelve_materials_six_rooms(app):
    s = app.site
    assert len(s.materials) >= 12
    assert {m.room for m in s.materials} == set(content.ROOMS)
    assert {m.task for m in s.materials} == set(content.TASKS)
    for m in s.materials:
        assert m.steps and m.checklist and m.sources and m.review_status == "ai_draft", m.slug
        assert m.raw["producer"]["mode"] == "manual_standin"


def test_all_materials_valid_and_validator_rejects_inventions():
    assert all(not errs(m) for m in content.load_materials())
    m = mat("povesit-nastennuyu-polku")
    bad = copy.deepcopy(m)
    bad["steps"][-1]["text"] = "Ставьте на полку вещи общей массой не больше 15 кг."
    assert any("число 15" in e for e in errs(bad))
    bad = copy.deepcopy(m)
    bad["limits"].append({"kind": "manufacturer", "text": "Полку можно вешать на гипсокартон."})
    assert any("требование без источника" in e for e in errs(bad))
    bad = copy.deepcopy(m)
    bad["limits"].append({"kind": "editorial", "src": m["sources"][0], "text": "Совет."})
    assert any("редакционный совет" in e for e in errs(bad))
    bad = copy.deepcopy(m)
    bad["summary"] += " Цена полки невысокая, работа займёт пару минут."
    assert any("запрещённое" in e for e in errs(bad))
    bad = copy.deepcopy(mat("razdelit-yashchik-komoda"))
    bad["calc"][0]["result"] = "72"
    assert any("≠" in e for e in errs(bad))
    bad = copy.deepcopy(m)
    bad["producer"] = {"mode": "qwen"}
    assert any("manual_standin" in e for e in errs(bad))


def test_ikea_parser_reads_measures_load_and_warning():
    raw = """<html><head><title>LACK wall shelf, white, 110x26 cm  - IKEA UK</title></head><body>
    <h2>Good to know</h2><p>Hidden suspension brackets are included.</p><p>IKEA of Sweden AB</p>
    <h2>Safety and compliance</h2><p>WARNING! Falling hazard – it must be securely anchored.</p>
    <h2>Assembly and documents</h2>
    <h2>Weight & measurements</h2><dt>Length</dt><dd>110 cm</dd><dt>Max. load</dt><dd>10 kg</dd>
    <h2>Package details</h2></body></html>"""
    r = parse_ikea(raw, "https://www.ikea.com/gb/en/p/lack-wall-shelf-white-90282180/")
    assert r["measures"] == {"Length": "110 cm", "Max. load": "10 kg"}
    assert r["safety"][0].startswith("WARNING") and r["article"] == "902.821.80"


def test_sitemap_urls_200_canonical_unique(app):
    titles = []
    for p in app.sitemap_urls():
        st, html, _ = get(app, p)
        assert st == 200 and canon(html) == app.site.abs(p), p
        assert len(re.findall(r"<h1[ >]", html)) == 1, p
        assert 'href="#"' not in html
        titles.append(re.search(r"<title>(.*?)</title>", html).group(1))
    assert len(titles) == len(set(titles))


def test_howto_matches_visible_and_no_fakes(app):
    for m in app.site.materials:
        _, html, _ = get(app, m.url)
        ld = [json.loads(x) for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]
        h = next(x for x in ld if x["@type"] == "HowTo")
        assert len(h["step"]) == len(re.findall(r'<li id="shag-\d+"', html))
        for k in ("image", "aggregateRating", "author", "estimatedCost", "totalTime", "video", "review"):
            assert k not in h
        for n in re.findall(r'href="#ist-(\d+)"', html):
            assert f'id="ist-{n}"' in html, (m.slug, n)


def test_manufacturer_and_editorial_are_separated(app):
    _, html, _ = get(app, "/instrukciya/zakrepit-komod-k-stene/")
    man = html.split("Требования производителя")[1].split("</div>")[0]
    ed = html.split("Совет редакции")[1].split("</div>")[0]
    assert "ist-" in man and "ist-" not in ed and "не требование производителя" in ed


def test_filters_reset_empty_and_noindex(app):
    st, html, _ = get(app, "/zadachi/", {"pomeshchenie": ["kuhnya"], "zadacha": ["mebel"]})
    assert st == 200 and 'class="empty"' in html and "Сбросить фильтры" in html and canon(html) is None
    st, html, _ = get(app, "/zadachi/", {"pomeshchenie": ["spalnya"]})
    assert html.count('class="card ') == len(app.site.in_room("spalnya")) and canon(html) is None
    st, html, _ = get(app, "/zadachi/", {"pomeshchenie": ["cherdak"]})
    assert "Такого фильтра нет" in html
    _, html, _ = get(app, "/poisk/", {"q": ["квантовый"]})
    assert "Ничего не нашлось" in html and 'content="noindex' in html


def test_search_finds_by_room_object_and_stem(app):
    s = app.site
    assert {m.slug for m in s.search("обувь")} == {"obuvnaya-polka-u-vhoda", "sezonnaya-obuv-v-korobkah"}
    assert "zakrepit-komod-k-stene" in {m.slug for m in s.search("комода")}
    assert s.search("") == []


def test_404s_and_collection_backed_tag(app):
    for p in (
        "/pomeshcheniya/cherdak/",
        "/instrukciya/net/",
        "/podborki/net/",
        "/teg/opasnost-padeniya/",
        "/zadachi/x/",
    ):
        assert get(app, p)[0] == 404, p
    assert app.site.tag_url("opasnost-padeniya") == "/podborki/krepim-k-stene/"


def test_preview_closed_and_production_switch(app):
    _, html, _ = get(app, "/")
    assert 'content="noindex, nofollow"' in html and 'name="site-factory-variant-id" content="home-audit"' in html
    s = copy.copy(app.site)
    s.cfg = copy.deepcopy(app.site.cfg)
    s.cfg.update(mode="production", production_authorized=True)
    s.cfg["origin"]["production"] = "https://dom.test"
    _, html, _ = get(App(s), s.materials[0].url)
    assert 'content="index, follow"' in html and canon(html).startswith("https://dom.test/")
    s.cfg["origin"]["production"] = None
    with pytest.raises(RuntimeError):
        s.abs("/")


def test_network_policy_and_foreign_content(tmp_path):
    with pytest.raises(Refused):
        Client()._check("https://evil.example/")
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"site_id": "food-daily", "items": [], "sources": {}}))
    with pytest.raises(PermissionError):
        Site(content=p)


def test_no_cross_template_code():
    bad = re.compile(
        r"fooddaily|bakebook|weekplan|techkitchen|wt-template-(?!home-practical)|/srv/sites|\.\./+themes", re.I
    )
    for p in ROOT.rglob("*"):
        assert not p.is_symlink(), p
        if (
            p.is_file()
            and p.suffix in (".py", ".html", ".css", ".js", ".yaml")
            and "node_modules" not in p.parts
            and p.name != "test_home_practical.py"
        ):
            assert not bad.search(p.read_text(errors="replace")), p
