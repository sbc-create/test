"""Приёмочные тесты варианта B (fridge-first): подбор «что есть дома», каталог-таблица, отметки шагов."""

import re
from pathlib import Path

from fooddaily.views import TAGS

ROOT = Path(__file__).resolve().parents[1]


def get(app, path, q=None):
    return app.route(path, q or {})


def canon(html):
    m = re.search(r'<link rel="canonical" href="([^"]+)"', html)
    return m.group(1) if m else None


def test_variant_identity_and_port(app):
    _, html, _ = get(app, "/")
    assert '<meta name="site-factory-variant-id" content="fridge-first">' in html
    assert app.site.cfg["server"]["port"] == 8863 and "8847" not in app.site.cfg["origin"]["preview"]


def test_fridge_ranks_by_matches_then_missing(site):
    rows = site.fridge(["kurica", "ris"])
    assert rows and sorted(rows[0][1]) == ["kurica", "ris"]  # плов: оба продукта
    got = [len(g) for _, g, _ in rows]
    assert got == sorted(got, reverse=True)
    for r, g, miss in rows:
        prods = {t for t in r.tags if TAGS[t][1] == "product"}
        assert set(g) | set(miss) == prods and set(g) <= {"kurica", "ris"}
    assert site.fridge([]) == []


def test_fridge_page_states(app):
    st, html, _ = get(app, "/iz-holodilnika/")
    assert st == 200 and canon(html) == app.site.abs("/iz-holodilnika/") and 'class="match"' not in html
    st, html, _ = get(app, "/iz-holodilnika/", {"est": ["kurica"]})
    assert st == 200 and canon(html) is None and 'class="match"' in html
    assert html.count('class="match__row"') == len(app.site.tag("kurica"))
    assert 'value="kurica" checked' in html
    st, html, _ = get(app, "/iz-holodilnika/", {"est": ["kvantovyj"]})
    assert st == 400 and 'role="alert"' in html


def test_fridge_in_sitemap_and_home_picker(app):
    assert any(p == "/iz-holodilnika/" for p, _ in app.sitemap_urls())
    _, html, _ = get(app, "/")
    assert 'action="/iz-holodilnika/"' in html
    assert html.count('name="est"') == len(app.site.fridge_products())


def test_catalog_table_and_sort(app):
    _, html, _ = get(app, "/recepty/", {"sort": ["vremya"]})
    assert '<table class="cat">' in html and canon(html) is None
    mins = [r.total_minutes for r in app.site.recipes]
    first = re.search(r'<tr><th scope="row"><a href="([^"]+)"', html).group(1)
    fastest = min((r for r in app.site.recipes if r.total_minutes), key=lambda r: (r.total_minutes, r.title))
    assert first == fastest.url and any(mins)
    _, html, _ = get(app, "/recepty/", {"sort": ["evil"]})
    assert canon(html) == app.site.abs("/recepty/")


def test_recipe_has_step_marks_not_cook_modal(app, site):
    _, html, _ = get(app, site.recipes[0].url)
    assert html.count("data-step-check=") == len(site.recipes[0].d["steps"])
    assert "data-cook" not in html


def test_storage_namespace_is_own():
    js = (ROOT / "static" / "js" / "fridge.js").read_text()
    keys = set(re.findall(r'"(fdb?\.[a-z.]+)', js))
    assert keys and all(k.startswith("fdb.") for k in keys)
    assert not (ROOT / "static" / "js" / "site.js").exists() and not (ROOT / "static" / "css" / "site.css").exists()
