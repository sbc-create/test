"""Готовность к открытию индексации bestreciept.site и чистота публичного интерфейса.

* Один флаг production_authorized согласованно переключает robots.txt, meta robots, X-Robots-Tag и sitemap —
  без противоречий в обоих состояниях. Сейчас индексация закрыта (проверяет test_domain_config).
* В публичном HTML нет служебных надписей: модели, черновики, варианты, задания, пути, «ИИ», статусы проверки.
* Изображение публикуется только с происхождением и правами.
"""

import json
import re
import sys
import threading
import urllib.request
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fooddaily import views  # noqa: E402
from fooddaily.server import App, Server, make_handler  # noqa: E402
from fooddaily.views import Site  # noqa: E402

ORIGIN = "https://bestreciept.site"
FORBIDDEN = [
    r"\bИИ\b",
    r"нейросет",
    r"\bQwen\b",
    r"\bClaude\b",
    r"\bмодел[иьяей]\b",
    r"черновик",
    r"сгенерирован",
    r"\bV[1-5]\b",
    r"вариант V",
    r"\bjob[_ -]?id\b",
    r"\bfdj-[0-9a-f]",
    r"/home/",
    r"/srv/",
    r"\bvar/",
    r"рабочее название",
    r"предварительн",
    r"не провер",
    r"не готовил",
    r"готовится к запуску",
    r"manual_standin",
    r"review_status",
    r"импорт",
    r"TODO",
    r"BLOCKED_",
]


def domain_cfg(tmp_path: Path, authorized: bool) -> Path:
    cfg = yaml.safe_load((ROOT / "config" / "site.bestreciept.yaml").read_text())
    cfg["production_authorized"] = authorized
    p = tmp_path / f"site.{'open' if authorized else 'closed'}.yaml"
    p.write_text(yaml.safe_dump(cfg, allow_unicode=True))
    return p


def serve(app: App):
    srv = Server(("127.0.0.1", 0), make_handler(app))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def visible_text(html: str) -> str:
    """Текст, видимый посетителю и роботу: без ссылок источника (домены) и без служебных meta варианта."""
    html = re.sub(r'<meta name="site-factory-[^>]+>', "", html)
    return re.sub(r"\s+", " ", html)


@pytest.mark.parametrize("authorized", [False, True])
def test_indexing_switch_is_consistent(tmp_path, authorized):
    app = App(Site(config_path=domain_cfg(tmp_path, authorized)))
    assert app.site.indexable is authorized
    robots = app.route("/robots.txt", {})[1]
    urls = [p for p, _ in app.sitemap_urls()]
    srv, base = serve(app)
    try:
        for path in urls:
            with urllib.request.urlopen(base + path) as r:
                html, xrt = r.read().decode(), r.headers.get("X-Robots-Tag")
            meta = re.search(r'name="robots" content="([^"]+)"', html).group(1)
            canon = re.search(r'<link rel="canonical" href="([^"]+)"', html).group(1)
            assert canon == ORIGIN + path, path  # каждая страница карты — сама себе canonical
            if authorized:
                assert meta == "index, follow" and xrt is None, path
            else:
                assert meta.startswith("noindex") and xrt == "noindex, nofollow", path
    finally:
        srv.shutdown()
    if authorized:
        assert "Disallow: /\n" not in robots and f"Sitemap: {ORIGIN}/sitemap.xml" in robots
        for p in ("/poisk/", "/izbrannoe/", "/spisok-pokupok/", "/redaktor/"):
            assert f"Disallow: {p}" in robots
    else:
        assert "Disallow: /" in robots.splitlines() and "Sitemap:" not in robots


def test_sitemap_has_no_service_pages(app):
    urls = [p for p, _ in app.sitemap_urls()]
    assert len(urls) == len(set(urls))
    bad = [u for u in urls if "?" in u or u.startswith(("/poisk", "/izbrannoe", "/spisok", "/redaktor", "/api"))]
    assert not bad and "/kontakty/" not in urls
    assert sum(u.startswith("/recept/") for u in urls) == len(app.site.recipes)


def public_pages(app):
    paths = [p for p, _ in app.sitemap_urls()] + ["/poisk/?q=творог", "/poisk/?q=нетакого", "/net-takoj/"]
    for p in paths:
        path, _, q = p.partition("?")
        query = {k: [v] for k, v in (x.split("=", 1) for x in q.split("&") if x)}
        yield p, app.route(path, query)


def test_no_technical_text_in_public_html(app):
    for p, (_, html, _) in public_pages(app):
        text = visible_text(html)
        for pat in FORBIDDEN:
            assert not re.search(pat, text), (
                p,
                pat,
                re.search(pat, text) and text[re.search(pat, text).start() - 60 :][:140],
            )


def test_home_answers_what_and_how_to_find(app):
    _, html, _ = app.route("/", {})
    assert '<form class="search search--hero" action="/poisk/"' in html
    assert "Популярное" not in html  # данных о популярности нет
    for key in views.CATEGORIES:
        assert (f'href="/recepty/{key}/"' in html) == bool(app.site.category(key))
    assert 'href="/na-kompaniyu/"' in html  # инструмент варианта C остаётся на главной
    ld = [json.loads(x) for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]
    assert {x["@type"] for x in ld} == {"WebSite", "ItemList"}


def test_home_shows_each_recipe_once_and_links_resolve(app):
    """Подборки главной не повторяют одну карточку в соседних секциях; каждая ссылка главной открывается."""
    _, html, _ = app.route("/", {})
    main = html[html.index("<main") : html.index('<footer class="foot">')]
    slugs = re.findall(r'<article class="card[^"]*" data-slug="([^"]+)"', main)
    assert len(slugs) >= 8 and len(slugs) == len(set(slugs)), slugs
    for href in set(re.findall(r'href="(/[^"#?]*)"', main)):
        if not href.startswith("/static/"):
            assert app.route(href, {})[0] == 200, href


def test_footer_links_are_real_pages(app):
    _, html, _ = app.route("/", {})
    foot = html[html.index('<footer class="foot">') :]
    links = re.findall(r'href="(/[^"]*)"', foot)
    assert "/o-proekte/" in links and "/konfidencialnost/" in links and "/kontakty/" not in links
    for href in links:
        assert app.route(href, {})[0] == 200, href
    assert app.route("/kontakty/", {})[:3:2] == (301, {"Location": "/o-proekte/"})


def test_recipe_page_quick_answers_and_anchors(app):
    r = app.site.recipes[0]
    _, html, _ = app.route(r.url, {})
    assert 'href="#ingredienty"' in html and 'id="ingredienty"' in html
    assert 'href="#prigotovlenie"' in html and 'id="prigotovlenie"' in html
    assert re.search(r"<dt>Продукты</dt><dd>\d+</dd>", html)
    ld = next(
        x
        for x in (json.loads(y) for y in re.findall(r'ld\+json">(.*?)</script>', html, re.S))
        if x["@type"] == "Recipe"
    )
    assert "image" not in ld and "aggregateRating" not in ld and "author" not in ld
    assert ld["name"] == r.title and len(ld["recipeIngredient"]) == len(r.ingredients)


def test_images_require_rights(tmp_path):
    site = Site()
    slug = site.recipes[0].slug
    bad = tmp_path / "images.json"
    bad.write_text(
        json.dumps(
            {
                "items": {
                    slug: {
                        "file": slug,
                        "width": 800,
                        "height": 600,
                        "widths": [400],
                        "kind": "photo",
                        "alt": "x",
                        "source": "",
                        "license": "",
                    }
                }
            }
        )
    )
    with pytest.raises(ValueError):
        views.load_images(site.by_slug, bad)
    assert views.load_images(site.by_slug) == {}  # сейчас изображений с правами нет — и ни одной подмены


def test_chicken_search_is_meat_not_eggs(app):
    """«курица» — мясо курицы; «куриное яйцо» — яйца (основа «кури» не должна склеивать их)."""
    hits = app.site.search("курица")
    assert hits and all("kurica" in r.tags for r in hits), [r.title for r in hits]
    assert {r.slug for r in hits} == {r.slug for r in app.site.tag("kurica")}
    eggs = {r.slug for r in app.site.search("куриное яйцо")}
    assert eggs == {r.slug for r in app.site.search("яйцо")} and len(eggs) > len(hits) - 1
    assert views.norm("Куриные яйца, куриный желток, куриная грудка") == "яйца желток куриная грудка"


def test_search_matches_word_forms_not_word_middles(app):
    """Поиск: регистр и окончания не важны; часть слова в середине — не совпадение; пустой запрос — пусто."""
    s = app.site
    titles = lambda q: sorted(r.title for r in s.search(q))  # noqa: E731
    assert titles("сырник") == titles("сырники") == titles("СЫРНИКИ") and titles("сырник")
    assert titles("тыква") == titles("тыквой") and titles("тыква")
    assert not any("сырными" in r.search_text and "сырник" not in r.search_text for r in s.search("сырники"))
    # «пече» внутри «купечески» и «запеченная» — не «печень»; печёнки среди рецептов нет
    assert s.search("печень") == []
    assert s.search("") == [] and s.search("   ") == []
    assert titles("суп с курицей") == titles("суп курицей")
    code, html, _ = app.route("/poisk/", {"q": ["нетакогоблюда"]})
    assert code == 200 and "ничего нет" in html


def test_default_one_serving_is_not_shown_as_yield(app):
    """«1 порция» у источника — не выход (суп из 500 г тыквы): ни на карточке, ни в разметке, пересчёт кратный."""
    ones = [r for r in app.site.recipes if r.servings == 1]
    assert ones and all(r.yield_n is None for r in ones)
    for r in ones:
        _, html, _ = app.route(r.url, {})
        assert 'data-servings="0"' in html and "Выход в рецепте не указан" in html and '"recipeYield"' not in html
        assert "<dt>Порции</dt>" not in html
    _, html, _ = app.route("/recepty/", {})
    assert "1 порция" not in html
    p = app.site.party([ones[0].slug], 8)  # на компанию: количества как в рецепте, не ×8
    src = {(i.name.lower(), i.unit): i.quantity for i, _ in ones[0].ingredients if i.quantity and i.unit != "to_taste"}
    assert all(abs(src[(it["name"].lower(), it["unit"])] - it["q"]) < 1e-9 for it in p["items"])
