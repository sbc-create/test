"""SEO-матрица на репрезентативных URL и функции сайта.

Страницы рендерятся тем же App, что обслуживает preview; HTML разбирается
как есть. Матрица типов страниц — docs/SEO-MATRIX.md.
"""

import copy
import json
import re
from collections import Counter

import pytest

from fooddaily.server import App


def get(app, path, q=None):
    return app.route(path, q or {})


def jsonld(html):
    return [json.loads(x) for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]


def meta(html, name):
    m = re.search(rf'<meta name="{name}" content="([^"]*)"', html)
    return m.group(1) if m else None


def canonical(html):
    m = re.search(r'<link rel="canonical" href="([^"]+)"', html)
    return m.group(1) if m else None


def indexable_paths(app):
    return [p for p, _ in app.sitemap_urls()]


def test_enough_recipes_and_sections(site):
    assert len(site.recipes) >= 20
    assert len({r.category for r in site.recipes}) >= 5


def test_new_sorted_by_publication(site):
    dates = [r.published_at for r in site.recipes]
    assert dates == sorted(dates, reverse=True)


def test_every_sitemap_url_is_200_with_self_canonical(app):
    for p in indexable_paths(app):
        st, html, _ = get(app, p)
        assert st == 200, p
        assert canonical(html) == app.site.abs(p), p


def test_titles_descriptions_h1_unique(app):
    titles, descs = Counter(), Counter()
    for p in indexable_paths(app):
        _, html, _ = get(app, p)
        titles[re.search(r"<title>(.*?)</title>", html).group(1)] += 1
        descs[meta(html, "description")] += 1
        assert len(re.findall(r"<h1[ >]", html)) == 1, p
    assert max(titles.values()) == 1, [t for t, n in titles.items() if n > 1]
    assert max(descs.values()) == 1, [t for t, n in descs.items() if n > 1]


def test_recipe_jsonld_matches_visible(app, site):
    for r in site.recipes:
        st, html, _ = get(app, r.url)
        ld = next(x for x in jsonld(html) if x["@type"] == "Recipe")
        assert len(ld["recipeIngredient"]) == len(re.findall(r'<li class="ing"', html))
        assert len(ld["recipeInstructions"]) == len(re.findall(r'<li class="step"', html))
        for forbidden in ("aggregateRating", "review", "author", "nutrition", "image", "video"):
            assert forbidden not in ld, (r.slug, forbidden)
        for step in ld["recipeInstructions"]:
            assert (
                step["text"].replace('"', "&#34;")[:40] in html.replace("&quot;", "&#34;") or step["text"][:40] in html
            )
        assert ld["recipeYield"].startswith(str(r.yield_n)) if r.yield_n else "recipeYield" not in ld
        bc = next(x for x in jsonld(html) if x["@type"] == "BreadcrumbList")
        assert [i["name"] for i in bc["itemListElement"]][-1] == r.title


def test_preview_is_closed(app):
    assert not app.site.indexable
    for p in ["/", "/recepty/", site_recipe(app)]:
        _, html, _ = get(app, p)
        assert meta(html, "robots") == "noindex, nofollow"
    assert "Disallow: /" in app.robots()


def site_recipe(app):
    return app.site.recipes[0].url


def test_search_and_filters_not_indexable(app):
    for p, q in [("/poisk/", {"q": ["творог"]}), ("/recepty/", {"produkt": ["kurica"]})]:
        _, html, _ = get(app, p, q)
        assert canonical(html) is None
    prod = production_app(app)
    _, html, _ = get(prod, "/recepty/", {"produkt": ["kurica"]})
    assert meta(html, "robots") == "noindex, follow"
    _, html, _ = get(prod, "/poisk/", {"q": ["творог"]})
    assert meta(html, "robots") == "noindex, follow"


def production_app(app):
    """Переключатель режима: production с тестовым origin, только в памяти теста."""
    s = copy.copy(app.site)
    s.cfg = copy.deepcopy(app.site.cfg)
    s.cfg.update(mode="production", production_authorized=True)
    s.cfg["origin"]["production"] = "https://food-daily.test"
    a = App(s)
    return a


def test_production_switch(app):
    prod = production_app(app)
    _, html, _ = get(prod, site_recipe(prod))
    assert meta(html, "robots") == "index, follow"
    assert canonical(html).startswith("https://food-daily.test/")
    assert "Sitemap: https://food-daily.test/sitemap.xml" in prod.robots()
    assert "127.0.0.1" not in prod.sitemap()


def test_production_without_domain_is_blocked(app):
    s = copy.copy(app.site)
    s.cfg = copy.deepcopy(app.site.cfg)
    s.cfg["mode"] = "production"
    with pytest.raises(RuntimeError):
        s.abs("/")


def test_pagination_self_canonical_and_404_beyond(app):
    _, html, _ = get(app, "/recepty/page/2/")
    assert canonical(html).endswith("/recepty/page/2/")
    assert get(app, "/recepty/page/1/")[0] == 404
    assert get(app, "/recepty/page/99/")[0] == 404


def test_no_orphan_recipes(app):
    linked = set()
    for p in indexable_paths(app):
        if p.startswith("/recept/"):
            continue
        _, html, _ = get(app, p)
        linked |= set(re.findall(r'href="(/recept/[a-z0-9-]+/)"', html))
    assert {r.url for r in app.site.recipes} <= linked


def test_tag_pages_thresholds(site):
    for items in site.tag_pages().values():
        assert len(items) >= site.cfg["seo"]["tag_page_min_items"]
    assert all(len(v[2]) >= 3 for v in site.collections().values())


def test_search_normalization(site):
    assert site.search("ТВОРОЖНАЯ   запеканка") and site.search("клёцками") == site.search("клецками")
    assert site.search("zzzz") == []


def test_filters(site):
    supy = site.filter(category="supy")
    assert supy and all(r.category == "supy" for r in supy)
    fast = site.filter(time="do-20")
    assert all(r.total_minutes <= 20 for r in fast)
    assert site.filter(product="tvorog", category="supy") == []


def test_no_internal_details_for_reader(app, site):
    for p in [site.recipes[0].url, "/", "/recepty/"]:
        _, html, _ = get(app, p)
        for bad in (
            "fdj-",
            "job_id",
            "claude/",
            "ai_draft",
            "manual_standin",
            "rec-",
            "editor_notes",
        ):
            assert bad not in html, (p, bad)


def test_unpublished_blocked_recipe_is_404(app):
    assert get(app, "/recept/tomatnyj-sup-s-zapechennym-percem/")[0] == 404


def test_no_fake_video_or_ratings(app, site):
    for r in site.recipes:
        _, html, _ = get(app, r.url)
        assert "<video" not in html and "VideoObject" not in html and "Play" not in html
        assert "★" not in html and "рейтинг" not in html.lower()


def test_cards_always_have_titles(app):
    _, html, _ = get(app, "/recepty/")
    cards = re.findall(r'<article class="card card--[a-z-]+".*?</article>', html, re.S)
    assert cards and all(
        re.search(r'class="card__title"><a class="card__link" href="[^"]+">[^<]{3,}</a>', c) for c in cards
    )


def test_source_attribution_shows_domain(app, site):
    r = site.recipes[0]
    _, html, _ = get(app, r.url)
    domain = r.source["url"].split("/")[2]
    assert f">{domain}</a>" in html and r.source["url"] in html


def test_recipe_tags_are_links_to_live_pages(app, site):
    found = 0
    for r in site.recipes:
        _, html, _ = get(app, r.url)
        block = re.search(r'<ul class="tags".*?</ul>', html, re.S)
        if not block:
            continue
        for href in re.findall(r'<a href="([^"]+)"', block.group(0)):
            found += 1
            assert get(app, href)[0] == 200, href
    assert found >= 10


def test_tag_indexes_and_articles(app, site):
    for p in ("/produkty/", "/sposob/", "/sovety/"):
        st, html, _ = get(app, p)
        assert st == 200 and canonical(html) == app.site.abs(p)
    for slug, a in site.articles.items():
        st, html, _ = get(app, f"/sovety/{slug}/")
        assert st == 200
        ld = next(x for x in jsonld(html) if x["@type"] == "Article")
        assert ld["headline"] == a["title"] and a["title"] in html
        assert "author" not in ld and "image" not in ld
    assert get(app, "/sovety/net-takogo/")[0] == 404


def test_itemlist_matches_visible_cards(app):
    for p in ("/recepty/supy/", "/produkty/kurica/", "/podborki/bystro-do-30-minut/"):
        _, html, _ = get(app, p)
        il = next(x for x in jsonld(html) if x["@type"] == "ItemList")
        urls = [e["url"].replace(app.site.origin, "") for e in il["itemListElement"]]
        cards = re.findall(r'<article class="card[^"]*".*?<a class="card__link" href="([^"]+)"', html, re.S)
        assert urls == cards, p


def test_no_category_illustration_posing_as_dish(app, site):
    # значок раздела 24×18 рядом с его названием допустим; иллюстрация раздела на месте фото блюда — нет
    _, html, _ = get(app, site.recipes[0].url)
    head = html[html.index('class="recipe__head"'): html.index('class="recipe__body"')]
    assert "recipe__illo" not in html and "<img" not in head
    _, html, _ = get(app, "/recepty/")
    grid = re.search(r'<div class="grid">.*?</div>\s*<nav|<div class="grid">.*', html, re.S).group(0)
    imgs = re.findall(r"<img[^>]*>", grid)
    assert imgs and all('width="24" height="18"' in i and 'alt=""' in i for i in imgs)
    assert len(imgs) == grid.count('class="card__cat"') and "card__media" not in grid


def test_catalog_contract_v1(app, site):
    st, body, headers = get(app, "/api/catalog.v1.json")
    data = json.loads(body)
    assert st == 200 and headers["Content-Type"] == "application/json"
    assert data["schema"] == "recipe-catalog/1" and data["site_id"] == "food-daily"
    assert len(data["items"]) == len(site.recipes)
    for it in data["items"]:
        assert it["path"].startswith("/recept/") and "steps" not in it and it["ingredients"]
    assert "/api/catalog.v1.json" not in app.sitemap()


def test_variant_identity_meta(app):
    _, html, _ = app.route("/", {})
    assert '<meta name="site-factory-variant-id" content="party-list">' in html
    assert '<meta name="site-factory-variant-version" content="1">' in html
