"""Приёмочные тесты games-story (вариант chapter-guides)."""

import copy
import html as htmlmod
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from saga import content  # noqa: E402
from saga.net import Client, Refused  # noqa: E402
from saga.server import App  # noqa: E402
from saga.site import Site  # noqa: E402
from saga.sources import berries, load_all  # noqa: E402


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


def test_chapters_and_ownership(app):
    s = app.site
    assert len(s.for_game("celeste")) >= 10
    assert set(s.games) == {g for g, v in s.ownership["games"].items() if v["owner"] == "games-story"}
    assert s.red_total("celeste") == sum(g.red for g in s.guides)


def test_validator_rejects_foreign_game_numbers_timecodes_unverified_video():
    assert all(not errs(m) for m in content.load_materials())
    m = mat("glava-1-forsaken-city")
    bad = copy.deepcopy(m)
    bad["game"] = "minecraft"  # игра другого сайта сети
    assert any("принадлежит сайту games-survival" in e for e in errs(bad))
    bad = copy.deepcopy(m)
    bad["summary"] += " В главе 27 клубник."
    assert any("число 27" in e for e in errs(bad))
    bad = copy.deepcopy(m)
    bad["tips"] = ["Смотрите с 3:15 в ролике."]
    assert any("запрещённое" in e for e in errs(bad))
    bad = copy.deepcopy(m)
    bad["videos"] = [m["src"]]  # страница вики — не проверенное видео
    assert any("не проверено через oEmbed" in e for e in errs(bad))


def test_berry_icons_parsed_not_guessed():
    cell = (
        '<span><a href="/wiki/Strawberry" title="Strawberry"><img/></a></span> <b>20</b> &#8226; '
        '<span><a href="/wiki/Golden_Strawberries" title="Golden Strawberries"><img/></a></span> 3'
    )
    assert berries(cell) == [{"kind": "Strawberry", "count": 20}, {"kind": "Golden Strawberries", "count": 3}]


def test_route_is_source_checkpoints_only(app):
    for g in app.site.guides:
        _, html, _ = get(app, g.url)
        route = re.findall(r'<li><span lang="en">(.*?)</span></li>', html)
        assert route == g.src.get("checkpoints", []), g.slug


def test_sitemap_urls_200_canonical_unique(app):
    titles = []
    for p in app.sitemap_urls():
        st, html, _ = get(app, p)
        assert st == 200 and canon(html) == app.site.abs(p), p
        assert len(re.findall(r"<h1[ >]", html)) == 1, p
        titles.append(re.search(r"<title>(.*?)</title>", html).group(1))
    assert len(titles) == len(set(titles))


def test_video_is_facade_with_verified_metadata(app):
    _, html, _ = get(app, "/video/")
    assert "<iframe" not in html  # плеер грузится только по нажатию
    for v in app.site.videos:
        assert v["embeddable"] and f'data-vid="{v["video_id"]}"' in html and v["channel"] in htmlmod.unescape(html)
    ld = [json.loads(x) for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]
    vids = [x for x in ld if x["@type"] == "VideoObject"]
    assert len(vids) == len(app.site.videos) and all("uploadDate" not in x and "duration" not in x for x in vids)


def test_404s_and_other_sites_games(app):
    for p in ("/igra/minecraft/", "/igra/baldurs-gate-3/", "/igra/celeste/net/", "/igra/celeste/glava-99/"):
        assert get(app, p)[0] == 404, p


def test_preview_closed_and_production_switch(app):
    _, html, _ = get(app, "/")
    assert 'content="noindex, nofollow"' in html and 'content="chapter-guides"' in html
    s = copy.copy(app.site)
    s.cfg = copy.deepcopy(app.site.cfg)
    s.cfg.update(mode="production", production_authorized=True)
    s.cfg["origin"]["production"] = "https://story.test"
    _, html, _ = get(App(s), s.guides[0].url)
    assert 'content="index, follow"' in html and canon(html).startswith("https://story.test/")
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
        r"flora|sezon|udobdom|fooddaily|bakebook|weekplan|techkitchen|wt-template-(?!games-story)|/srv/sites", re.I
    )
    for p in ROOT.rglob("*"):
        assert not p.is_symlink(), p
        if (
            p.is_file()
            and p.suffix in (".py", ".html", ".css", ".js", ".yaml")
            and "node_modules" not in p.parts
            and p.name != "test_games_story.py"
        ):
            assert not bad.search(p.read_text(errors="replace")), p


def test_meta_descriptions_fit_snippet(app):
    from saga.server import SNIPPET_MAX, snippet

    assert snippet("Раз. Два три.", 8) == "Раз."
    long_clause = "Начало фразы " + "и ещё слова " * 8 + ", хвост " + "без точки " * 10
    assert snippet(long_clause).endswith("слова…")
    for path in re.findall(r"<loc>https?://[^/]+(/[^<]*)</loc>", get(app, "/sitemap.xml")[1]):
        _, html, _ = get(app, path)
        desc = re.search(r'<meta name="description" content="([^"]*)"', html).group(1)
        assert 20 <= len(desc) <= SNIPPET_MAX, (path, len(desc))
