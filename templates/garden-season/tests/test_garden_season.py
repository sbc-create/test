"""Приёмочные тесты garden-season (вариант region-timeline)."""

import copy
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sezon import content  # noqa: E402
from sezon.net import Client, Refused  # noqa: E402
from sezon.server import App  # noqa: E402
from sezon.site import Site  # noqa: E402
from sezon.sources import load_all, parse_osu  # noqa: E402


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


def test_works_cover_seasons_regions_and_crops(app):
    s = app.site
    assert len(s.works) >= 12
    assert len({m for w in s.works for m in w.months}) >= 10
    assert {"or-all", "or-west", "uk"} <= {r for w in s.works for r in w.regions}
    for w in s.works:
        assert w.timing and w.steps and w.checklist and w.raw["producer"]["mode"] == "manual_standin"


def test_validator_keeps_regional_timing_regional():
    assert all(not errs(m) for m in content.load_materials())
    m = mat("malina-obrezka")
    bad = copy.deepcopy(m)
    bad["timing"][0]["region"] = "or-all"  # срок Западного Орегона выдан за общий
    assert any("регион" in e for e in errs(bad))
    bad = copy.deepcopy(m)
    bad["timing"][0]["month"] = 4
    assert any("месяц" in e for e in errs(bad))
    bad = copy.deepcopy(m)
    bad["steps"].append({"text": "В июне повторите обрезку.", "refs": []})
    assert any("июнь" in e for e in errs(bad))
    bad = copy.deepcopy(m)
    bad["summary"] += " Так делают везде."
    assert any("везде" in e for e in errs(bad))
    bad = copy.deepcopy(mat("uborka-i-hranenie-kartofelya"))
    bad["steps"][2]["text"] = "Храните при 7 °C."
    assert any("число 7" in e for e in errs(bad))
    bad = copy.deepcopy(mat("uborka-i-hranenie-kartofelya"))
    bad["calc"][0]["result"] = "5"
    assert any("≠" in e for e in errs(bad))
    bad = copy.deepcopy(m)
    bad["limits"].append({"kind": "university", "text": "Без ссылки."})
    assert any("без источника" in e for e in errs(bad))


def test_osu_parser_regions_and_time_prefixes():
    raw = """<title>October garden calendar | OSU Extension Service</title><p>Recommendations in this calendar are
    not necessarily applicable to all areas of Oregon.</p><h2>Planting</h2><ul><li><p>Plant garlic.</p></li>
    <li><p><strong>Western Oregon:</strong> Harvest squash.</p></li>
    <li><p>Coastal and western valleys: Spray potatoes.</p></li>
    <li><p>Early October: Reduce water.</p></li></ul>Trade-name products"""
    r = parse_osu(raw, "u")
    assert r["month"] == 10 and r["caveat"]
    assert [(i["region"], i.get("when")) for i in r["items"]] == [
        ("or-all", None),
        ("or-west", None),
        ("or-local", None),
        ("or-all", "Early October"),
    ]


def test_sitemap_urls_200_canonical_unique(app):
    titles = []
    for p in app.sitemap_urls():
        st, html, _ = get(app, p)
        assert st == 200 and canon(html) == app.site.abs(p), p
        assert len(re.findall(r"<h1[ >]", html)) == 1, p
        titles.append(re.search(r"<title>(.*?)</title>", html).group(1))
    assert len(titles) == len(set(titles))


def test_work_page_shows_region_for_every_timing_and_howto_matches(app):
    for w in app.site.works:
        _, html, _ = get(app, w.url)
        when = html.split('class="year__list"')[1].split("</ul>")[0]
        assert when.count("<li>") == len(w.timing) and when.count('class="rg rg--') == len(w.timing)
        assert html.count('class="year__row"') == len(w.regions)
        ld = [json.loads(x) for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]
        h = next(x for x in ld if x["@type"] == "HowTo")
        assert len(h["step"]) == len(w.steps)
        for k in ("image", "aggregateRating", "author", "estimatedCost", "totalTime", "video"):
            assert k not in h
        for n in re.findall(r'href="#ist-(\d+)"', html):
            assert f'id="ist-{n}"' in html


def test_month_page_groups_by_region_and_empty_month(app):
    _, html, _ = get(app, "/kalendar/fevral/")
    heads = re.findall(r'<section aria-labelledby="h-([a-z-]+)"><h2', html)
    assert heads == [r for r in content.REGIONS if r in heads] and {"or-all", "or-west", "or-east"} <= set(heads)
    # Пустой месяц: после пополнения работ пустых месяцев нет — проверяем на копии сайта без декабрьских работ
    s = copy.copy(app.site)
    s.works = [w for w in app.site.works if 12 not in w.months]
    empty = App(s)
    st, html, _ = get(empty, "/kalendar/dekabr/")
    assert (
        st == 200
        and 'class="empty"' in html
        and canon(html) is None
        and "/kalendar/dekabr/" not in empty.sitemap_urls()
    )
    assert get(app, "/kalendar/xx/")[0] == 404


def test_crop_grid_does_not_mix_regions(app):
    g = app.site.crop_grid("malina")
    assert 2 in g["or-west"] and 2 in g["or-east"] and 2 not in g["or-all"]
    g = app.site.crop_grid("chesnok")
    assert g["or-all"].keys() == {10} and g["or-west"].keys() == {11} and g["uk"].keys() == {10}


def test_region_timeline_only_own_region_and_filters(app):
    for r in content.REGIONS:
        for m, ws in app.site.region_timeline(r).items():
            for w in ws:
                assert any(t["region"] == r and t.get("month") == m for t in w.timing), (r, m, w.slug)
    _, html, _ = get(app, "/region/or-west/")
    assert canon(html) and 'data-region="or-west"' in html
    st, html, _ = get(app, "/region/or-west/", {"tip": ["uhod"], "kultura": ["malina"]})
    assert (
        st == 200
        and canon(html) is None
        and "/rabota/malina-obrezka/" in html
        and "/rabota/sideraty-na-zimu/" not in html
    )
    _, html, _ = get(app, "/region/uk/", {"tip": ["zima"]})
    assert 'class="empty"' in html and "Сбросить фильтры" in html
    _, html, _ = get(app, "/region/uk/", {"kultura": ["banan"]})
    assert "Такого фильтра нет" in html


def test_calendar_month_list_filters(app):
    _, html, _ = get(app, "/kalendar/", {"region": ["uk"]})
    assert canon(html) is None and set(re.findall(r'<li><a href="/kalendar/([a-z]+)/">', html)) == {"oktyabr"}
    _, html, _ = get(app, "/kalendar/", {"region": ["uk"], "tip": ["zima"]})
    assert 'class="empty"' in html


def test_404s(app):
    for p in ("/rabota/net/", "/kultura/banan/", "/region/mars/", "/tip/net/", "/podborki/net/"):
        assert get(app, p)[0] == 404, p


def test_preview_closed_and_production_switch(app):
    _, html, _ = get(app, "/")
    assert 'content="noindex, nofollow"' in html and 'content="region-timeline"' in html
    s = copy.copy(app.site)
    s.cfg = copy.deepcopy(app.site.cfg)
    s.cfg.update(mode="production", production_authorized=True)
    s.cfg["origin"]["production"] = "https://dacha.test"
    _, html, _ = get(App(s), s.works[0].url)
    assert 'content="index, follow"' in html and canon(html).startswith("https://dacha.test/")
    s.cfg["origin"]["production"] = None
    with pytest.raises(RuntimeError):
        s.abs("/")


def test_network_policy_and_foreign_content(tmp_path):
    with pytest.raises(Refused):
        Client()._check("https://evil.example/")
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"site_id": "home-practical", "items": [], "sources": {}}))
    with pytest.raises(PermissionError):
        Site(content=p)


def test_no_cross_template_code():
    bad = re.compile(r"udobdom|fooddaily|bakebook|weekplan|techkitchen|wt-template-(?!garden-season)|/srv/sites", re.I)
    for p in ROOT.rglob("*"):
        assert not p.is_symlink(), p
        if (
            p.is_file()
            and p.suffix in (".py", ".html", ".css", ".js", ".yaml")
            and "node_modules" not in p.parts
            and p.name != "test_garden_season.py"
        ):
            assert not bad.search(p.read_text(errors="replace")), p
