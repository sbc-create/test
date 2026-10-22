"""Готовность к открытию индексации myfood.mobi и чистота публичного интерфейса.

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

from bakebook import site as site_mod  # noqa: E402
from bakebook.server import App, Server, make_handler  # noqa: E402
from bakebook.site import GROUPS, Site  # noqa: E402

ORIGIN = "https://myfood.mobi"
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
    r"/home/",
    r"/srv/",
    r"\bvar/",
    r"рабочее название",
    r"предварительн",
    r"не провер",
    r"не пекла",
    r"редакция",
    r"Фото нет",
    r"manual_standin",
    r"review_status",
    r"импорт",
    r"TODO",
    r"BLOCKED_",
    r"версия \d",
]


@pytest.fixture(scope="module")
def app():
    return App()


def domain_cfg(tmp_path: Path, authorized: bool) -> Path:
    cfg = yaml.safe_load((ROOT / "config" / "site.myfood.yaml").read_text())
    cfg["production_authorized"] = authorized
    p = tmp_path / f"site.{'open' if authorized else 'closed'}.yaml"
    p.write_text(yaml.safe_dump(cfg, allow_unicode=True))
    return p


@pytest.mark.parametrize("authorized", [False, True])
def test_indexing_switch_is_consistent(tmp_path, authorized):
    app = App(Site(config=domain_cfg(tmp_path, authorized)))
    assert app.site.indexable is authorized
    robots = app.route("/robots.txt", {})[1]
    srv = Server(("127.0.0.1", 0), make_handler(app))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        for path, _ in app.sitemap_urls():
            with urllib.request.urlopen(base + path) as r:
                html, xrt = r.read().decode(), r.headers.get("X-Robots-Tag")
            meta = re.search(r'name="robots" content="([^"]+)"', html).group(1)
            assert re.search(r'<link rel="canonical" href="([^"]+)"', html).group(1) == ORIGIN + path, path
            if authorized:
                assert meta == "index, follow" and xrt is None, path
            else:
                assert meta.startswith("noindex") and xrt == "noindex, nofollow", path
    finally:
        srv.shutdown()
    if authorized:
        assert "Disallow: /\n" not in robots and f"Sitemap: {ORIGIN}/sitemap.xml" in robots
        assert "Disallow: /poisk/" in robots and "Disallow: /*?" in robots
    else:
        assert "Disallow: /" in robots.splitlines() and "Sitemap:" not in robots


def test_sitemap_has_no_service_pages(app):
    urls = [p for p, _ in app.sitemap_urls()]
    assert len(urls) == len(set(urls))
    assert not [u for u in urls if "?" in u or u.startswith(("/poisk", "/redaktor"))]
    assert sum(u.startswith("/recept/") for u in urls) == len(app.site.recipes)
    for k, items in app.site.groups().items():  # раздел из одного рецепта существует, но в карту не попадает
        assert (f"/recepty/{k}/" in urls) == (len(items) >= 2)


def test_no_technical_text_in_public_html(app):
    paths = [p for p, _ in app.sitemap_urls()] + [
        "/poisk/?q=кекс",
        "/poisk/?q=нетакого",
        "/net-takoj/",
        "/recepty/?vid=tablica",
        "/pechem/",
    ]
    for p in paths:
        path, _, q = p.partition("?")
        query = {k: [v] for k, v in (x.split("=", 1) for x in q.split("&") if x)}
        html = re.sub(r'<meta name="site-factory-[^>]+>', "", app.route(path, query)[1])
        for pat in FORBIDDEN:
            m = re.search(pat, html)
            assert not m, (p, pat, html[max(0, m.start() - 60) : m.start() + 80])


def test_home_answers_what_and_how_to_find(app):
    _, html, _ = app.route("/", {})
    assert 'class="find find--hero" action="/poisk/"' in html and "Популярное" not in html
    for k in GROUPS:
        assert (f'href="/recepty/{k}/"' in html) == (k in app.site.groups())
    assert 'href="/pechem/"' in html and 'href="/duhovka/' in html  # функции варианта B на виду
    ld = [json.loads(x) for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]
    assert {x["@type"] for x in ld} == {"WebSite", "ItemList"}


def test_footer_links_are_real_pages(app):
    _, html, _ = app.route("/", {})
    foot = html[html.index('<footer class="colophon">') :]
    links = re.findall(r'href="(/[^"]*)"', foot)
    assert "/o-proekte/" in links and "/konfidencialnost/" in links
    for href in links:
        assert app.route(href, {})[0] == 200, href


def test_group_pages_and_cards(app):
    for k, items in app.site.groups().items():
        st, html, _ = app.route(f"/recepty/{k}/", {})
        assert st == 200 and html.count('class="bcard ') == len(items)
        assert "noindex" in re.search(r'name="robots" content="([^"]+)"', html).group(1)
    assert app.route("/recepty/sloyki/", {})[0] == 404  # пустой раздел не показывается


def test_recipe_quick_answers_and_anchors(app):
    r = app.site.recipes[0]
    _, html, _ = app.route(r.url, {})
    assert 'href="#ingredienty"' in html and 'id="ingredienty"' in html
    assert 'href="#prigotovlenie"' in html and 'id="prigotovlenie"' in html
    assert re.search(r"Продукты \(\d+\)</a>", html) and 'class="jump__go" href="#prigotovlenie"' in html


def test_recipe_shows_no_empty_fields_or_default_yield(app):
    """Пустые поля не показываются («Форма — не указана»), «1 порция» у партии выпечки — не выход."""
    for r in app.site.recipes:
        _, html, _ = app.route(r.url, {})
        main = html.split("<main", 1)[1].split("</main>", 1)[0]
        assert "не указан" not in main, r.slug
        lds = [json.loads(x) for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]
        ld = next(x for x in lds if x.get("@type") == "Recipe")
        if r.servings <= 1:
            assert "<span>Выход</span>" not in main and "recipeYield" not in ld, r.slug
        else:
            assert f"<b>{r.servings} " in main and ld["recipeYield"] == f"{r.servings} порц.", r.slug
        if r.form:
            assert not re.search(r"(ого|его|ую)$", r.form) and r.form[0].isupper(), r.form
    assert app.site.by_slug["limonnyj-keks"].form == "Форма для английского кекса"
    assert app.site.by_slug["pechene-s-finikami-i-slivami"].form == "Силиконовая форма"


def test_images_require_rights(tmp_path):
    s = Site()
    slug = s.recipes[0].slug
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
        site_mod.load_images(s.by_slug, bad)
    assert site_mod.load_images(s.by_slug) == {}


def test_chicken_search_does_not_match_eggs(app):
    assert app.site.search("курица") == []  # в книге выпечки нет блюд с мясом курицы — яйца не совпадение
    assert site_mod.norm("Куриные яйца и куриный желток") == "яйца и желток"


def test_home_shows_each_recipe_once_and_links_resolve(app):
    """Сезонная подборка, «К чаю» и «Новые» не повторяют одну карточку; каждая ссылка главной открывается."""
    _, html, _ = app.route("/", {})
    main = html[html.index("<main") : html.index('<footer class="colophon">')]
    cards = re.findall(r'class="bcard__link" href="([^"]+)"', main)
    assert len(cards) >= 8 and len(cards) == len(set(cards)), cards
    for href in set(re.findall(r'href="(/[^"#?]*)"', main)):
        if not href.startswith("/static/"):
            assert app.route(href, {})[0] == 200, href


def test_search_matches_word_forms_not_word_middles(app):
    s = app.site
    titles = lambda q: sorted(r.title for r in s.search(q))  # noqa: E731
    assert titles("кекс") == titles("кексы") == titles("КЕКС") and titles("кекс")
    assert titles("слива") == titles("сливами") and titles("слива")
    assert titles("заварное") == titles("заварного") and titles("заварное")
    assert s.search("печень") == [] and titles("печенье") == titles("печенья") and titles("печенье")
    assert s.search("") == [] and s.search("  ") == []
    code, html, _ = app.route("/poisk/", {"q": ["нетакогоблюда"]})
    assert code == 200


def test_recipe_page_shows_related_existing_recipes(app):
    urls = {r.url for r in app.site.recipes}
    for r in app.site.recipes:
        _, html, _ = app.route(r.url, {})
        rel = re.findall(r'class="bcard__link" href="([^"]+)"', html)
        assert rel == [x.url for x in app.site.related(r)] and r.url not in rel and set(rel) <= urls, r.slug
    assert any(app.site.related(r) for r in app.site.recipes)


def test_404_offers_search_and_existing_sections(app):
    st, html, _ = app.route("/net-takoj-stranicy/", {})
    assert st == 404 and 'placeholder="' in html
    links = re.findall(r'class="gtile" href="([^"]+)"', html)
    assert len(links) == len(app.site.groups()) > 0
    assert all(app.route(u, {})[0] == 200 for u in links)
