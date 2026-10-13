"""Перенесено из варианта B: подбор «что есть дома», каталог-таблица и сортировка в каталоге C."""

import re

from fooddaily.views import TAGS


def get(app, path, q=None):
    return app.route(path, q or {})


def canon(html):
    m = re.search(r'<link rel="canonical" href="([^"]+)"', html)
    return m.group(1) if m else None


def test_fridge_ranks_by_matches_then_missing(site):
    rows = site.fridge(["kurica", "ris"])
    assert rows and sorted(rows[0][1]) == ["kurica", "ris"]
    got = [len(g) for _, g, _ in rows]
    assert got == sorted(got, reverse=True)
    for r, g, miss in rows:
        prods = {t for t in r.tags if TAGS[t][1] == "product"}
        assert set(g) | set(miss) == prods and set(g) <= {"kurica", "ris"}
    assert site.fridge([]) == []


def test_fridge_page_states(app):
    st, html, _ = get(app, "/iz-holodilnika/")
    assert st == 200 and canon(html) == app.site.abs("/iz-holodilnika/") and 'class="match"' not in html
    assert html.count('name="est"') == len(app.site.fridge_products())
    st, html, _ = get(app, "/iz-holodilnika/", {"est": ["kurica"]})
    assert st == 200 and canon(html) is None and 'class="match"' in html and "noindex" in html
    assert html.count('class="match__row"') == len(app.site.tag("kurica"))
    assert 'value="kurica" checked' in html
    st, html, _ = get(app, "/iz-holodilnika/", {"est": ["kvantovyj"]})
    assert st == 400 and 'role="alert"' in html and 'class="match"' not in html


def test_fridge_reachable(app):
    assert any(p == "/iz-holodilnika/" for p, _ in app.sitemap_urls())
    _, html, _ = get(app, "/")
    assert html.count('href="/iz-holodilnika/"') >= 2  # шапка и главная
    _, html, _ = get(app, "/na-kompaniyu/")
    assert 'href="/iz-holodilnika/"' in html


def test_catalog_sort_and_table(app):
    _, html, _ = get(app, "/recepty/", {"sort": ["vremya"], "vid": ["tablica"]})
    assert '<table class="cat">' in html and canon(html) is None and "noindex" in html
    first = re.search(r'<tr><th scope="row"><a href="([^"]+)"', html).group(1)
    fastest = min((r for r in app.site.recipes if r.total_minutes), key=lambda r: (r.total_minutes, r.title))
    assert first == fastest.url
    _, html, _ = get(app, "/recepty/", {"sort": ["nazvanie"]})
    assert '<table class="cat">' not in html and canon(html) is None
    titles = [r.title for r in sorted(app.site.recipes, key=lambda r: r.title)]
    assert html.index(titles[0]) < html.index(titles[1])
    _, html, _ = get(app, "/recepty/", {"sort": ["evil"], "vid": ["evil"]})
    assert canon(html) == app.site.abs("/recepty/") and '<table class="cat">' not in html


def test_catalog_pager_keeps_sort_and_view(app):
    if len(app.site.recipes) <= app.site.cfg["pagination"]["per_page"]:
        return
    _, html, _ = get(app, "/recepty/", {"sort": ["vremya"], "vid": ["tablica"]})
    assert "sort=vremya" in html and "vid=tablica" in html.split("</table>")[1]
