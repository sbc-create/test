"""Приёмочные тесты варианта B (oven-bench): по температуре, таблица сравнения, пекарский процент, отметки."""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bakebook.server import App  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return App()


def get(app, p, q=None):
    return app.route(p, q or {})


def canon(html):
    m = re.search(r'<link rel="canonical" href="([^"]+)"', html)
    return m.group(1) if m else None


def test_variant_identity_and_port(app):
    _, html, _ = get(app, "/")
    assert '<meta name="site-factory-variant-id" content="oven-bench">' in html
    assert app.site.cfg["server"]["port"] == 8864 and "8848" not in app.site.cfg["origin"]["preview"]


def test_home_groups_by_first_temperature(app):
    groups = app.site.by_temp()
    temps = [t for t, _ in groups]
    assert temps[-1] is None or None not in temps  # без духовки — в конце
    hot = [t for t in temps if t is not None]
    assert hot == sorted(hot, reverse=True)
    assert sum(len(v) for _, v in groups) == len(app.site.recipes)
    for t, items in groups:
        assert all((r.temps[0] if r.temps else None) == t for r in items)
    _, html, _ = get(app, "/duhovka/")  # страница «По температуре»; на главной — переходы к ней
    assert html.count('class="temp"') == len(groups)
    _, home, _ = get(app, "/")
    assert home.count('href="/duhovka/#t-') == len(groups)


def test_bakers_percentage_from_grams_only(app):
    r = app.site.by_slug["yablochnoe-myagkoe-pechene"]
    rows = {b["name"]: b["pct"] for b in r.bench}
    assert r.flour_g == 200 and rows["Зерновая мука"] == 100 and rows["Сливочное масло"] == 50 and rows["Сахар"] == 35
    assert rows["Куриное яйцо"] is None and rows["Яблоки"] is None  # штуки — без процента
    _, html, _ = get(app, r.url)
    assert "% от муки" in html and '<td class="num pct" data-label="от муки:">50 %</td>' in html
    for x in app.site.recipes:
        if not x.flour_g:
            assert "% от муки" not in get(app, x.url)[1], x.slug


def test_catalog_compare_table_and_sort(app):
    _, html, _ = get(app, "/recepty/")  # каталог — карточки; таблица сравнения — вид ?vid=tablica без своего canonical
    assert (
        'class="bgrid ' in html and canon(html) == app.site.abs("/recepty/") and 'href="/recepty/?vid=tablica"' in html
    )
    _, html, _ = get(app, "/recepty/", {"vid": ["tablica"]})
    assert (
        '<table class="cmp">' in html
        and canon(html) is None
        and html.count('<tr><th scope="row">') == len(app.site.recipes)
    )
    _, html, _ = get(app, "/recepty/", {"sort": ["temp"], "vid": ["tablica"]})
    assert canon(html) is None and 'content="noindex' in html
    first = re.search(r'<tr><th scope="row"><a href="([^"]+)"', html).group(1)
    assert first == app.site.by_temp()[0][1][0].url
    assert canon(get(app, "/recepty/", {"sort": ["evil"]})[1]) == app.site.abs("/recepty/")


def test_recipe_sheet_has_marks_and_timers_at_steps(app):
    r = next(x for x in app.site.recipes if x.timers)
    _, html, _ = get(app, r.url)
    assert html.count("data-step-done=") == len(r.steps)
    for t in r.timers:
        step = re.search(rf'<li id="shag-{t["step"]}">(.*?)</li>', html, re.S).group(1)
        assert f'data-minutes="{t["minutes"]}"' in step


def test_storage_namespace_is_own():
    js = (ROOT / "static" / "js" / "bench.js").read_text()
    keys = set(re.findall(r'"(fbb?\.[a-z]+\.)', js))
    assert keys == {"fbb.steps.", "fbb.weigh.", "fbb.batch.", "fbb.bought."}
    assert not (ROOT / "static" / "js" / "book.js").exists() and not (ROOT / "static" / "css" / "book.css").exists()
