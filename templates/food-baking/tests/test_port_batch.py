"""«Пеку несколько» — перенесено из варианта C: несколько рецептов → общий список и порядок духовки."""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bakebook.server import App  # noqa: E402

PAIR = ["yablochnoe-myagkoe-pechene", "limonnyj-keks"]


@pytest.fixture(scope="module")
def app():
    return App()


def get(app, p, q=None):
    return app.route(p, q or {})


def canon(html):
    m = re.search(r'<link rel="canonical" href="([^"]+)"', html)
    return m.group(1) if m else None


def test_sums_only_same_name_and_unit(app):
    bs = app.site.bake_set(PAIR)
    for it in bs["items"]:
        total = 0.0
        for slug in PAIR:
            for i in app.site.by_slug[slug].raw["ingredients"]:
                if i["name"].strip().lower().replace("ё", "е") == it["name"].lower().replace("ё", "е"):
                    k = 1000 if i["unit"] in ("kg", "l") else 1
                    unit = {"kg": "g", "l": "ml"}.get(i["unit"], i["unit"])
                    if unit == it["unit"] and i["quantity"] is not None:
                        total += i["quantity"] * k
        assert abs(total - it["q"]) < 1e-6, it["name"]


def test_oven_groups_by_top_temperature(app):
    bs = app.site.bake_set([r.slug for r in app.site.recipes])
    temps = [t for t, _ in bs["oven"]]
    hot = [t for t in temps if t is not None]
    assert hot == sorted(hot, reverse=True) and (None not in temps or temps[-1] is None)
    assert sum(len(rs) for _, rs in bs["oven"]) == len(app.site.recipes)


def test_page_states(app):
    st, html, _ = get(app, "/pechem/")
    assert st == 200 and canon(html) == app.site.abs("/pechem/") and "data-blist" not in html
    st, html, _ = get(app, "/pechem/", {"r": PAIR})
    assert st == 200 and canon(html) is None and "data-blist" in html
    assert get(app, "/pechem/", {"r": ["neizvestno"]})[0] == 400
    st, html, _ = get(app, "/pechem/", {"r": ["neizvestno"]})
    assert 'role="alert"' in html and "noindex" in html


def test_reachable_from_nav_home_sitemap(app):
    assert any(p == "/pechem/" for p, _ in app.sitemap_urls())
    _, html, _ = get(app, "/")
    assert html.count('href="/pechem/"') >= 2
    _, html, _ = get(app, "/recepty/")
    assert 'href="/pechem/" data-b-link' in html
