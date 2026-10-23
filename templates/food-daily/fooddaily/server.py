"""SSR-сервер food-daily: весь основной текст и ссылки — в серверном HTML.

Клиентский JS только улучшает страницу (порции, избранное, список покупок,
режим готовки); рецепт виден и без него. Публичное чтение использует снимок
контента и не обращается ни к БД, ни к Qwen, ни к внешним API.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import http.server
import json
import os
import re
import secrets
import socketserver
import time
import urllib.parse
from base64 import b64decode
from pathlib import Path

import jinja2

from . import seo
from .views import CATEGORIES, PANTRY_GROUPS, PRODUCTS, SEASONAL, TAGS, TIME_BUCKETS, Site, ru_date

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"
TEMPLATES = ROOT / "templates"
EDITOR_SECRET = Path(
    os.environ.get(
        "FOOD_DAILY_C_EDITOR_SECRET",
        str(Path.home() / ".config" / "food-daily-c-preview" / "editor.json"),
    )
)


# Служебные страницы, которые больше не нужны: контактов с достоверными данными нет — адрес ведёт на «О проекте».
PAGE_REDIRECTS = {"/kontakty/": "/o-proekte/"}


def asset_hashes() -> dict[str, str]:
    out = {}
    for p in STATIC.rglob("*"):
        if p.is_file():
            out[str(p.relative_to(STATIC))] = hashlib.sha256(p.read_bytes()).hexdigest()[:10]
    return out


class App:
    def __init__(self, site: Site | None = None):
        self.site = site or Site()
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(TEMPLATES),
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True,
            undefined=jinja2.StrictUndefined,
        )
        self.hashes = asset_hashes()
        self.env.globals.update(
            site=self.site,
            CATEGORIES=CATEGORIES,
            TAGS=TAGS,
            TIME_BUCKETS=TIME_BUCKETS,
            asset=self.asset,
            year=time.strftime("%Y"),
            plural=seo.plural,
        )
        self.env.filters["ru_date"] = ru_date
        self.csrf_key = secrets.token_bytes(32)
        red = ROOT / "data" / "redirects.json"
        self.redirects = json.loads(red.read_text()) if red.exists() else {}

    def asset(self, rel: str) -> str:
        return f"/static/{rel}?v={self.hashes.get(rel, '0')}"

    def render(self, tpl: str, meta: seo.Meta, **ctx) -> str:
        return self.env.get_template(tpl).render(meta=meta, **ctx)

    # ---- маршруты ---------------------------------------------------------
    def route(self, path: str, query: dict) -> tuple[int, str, dict]:
        s = self.site
        if path in self.redirects:  # старые адреса материалов — постоянный редирект на текущий
            return 301, "", {"Location": self.redirects[path]}
        q1 = lambda k: (query.get(k) or [""])[0].strip()  # noqa: E731
        if path == "/":
            cols = s.collections()
            quick = (
                sorted(cols["bystro-do-30-minut"][2], key=lambda r: (r.total_minutes, r.title))[:6]
                if ("bystro-do-30-minut" in cols)
                else []
            )
            # ряды по 3 (сетка 3/2/1); каждая карточка на главной — один раз:
            # подборки ниже не повторяют те, что уже показаны выше
            shown = {r.slug for r in quick}

            def take(items, n):
                out = [r for r in items if r.slug not in shown][:n]
                shown.update(r.slug for r in out)
                return out

            def shelf(items, n=3):  # подборка показывается, если после повторов осталось ≥2 блюд
                got = take(sorted(items, key=lambda r: (r.total_minutes or 10**6, r.title)), n)
                if len(got) < 2:
                    shown.difference_update(r.slug for r in got)
                    return []
                return got

            # порядок — по задачам: быстро, завтрак, суп, второе на обед и ужин, из немногих продуктов
            shelves = [
                ("bf", "На завтрак", "/recepty/zavtraki/", "Все завтраки", shelf(s.category("zavtraki"))),
                ("soup", "Супы", "/recepty/supy/", "Все супы", shelf(s.category("supy"))),
                (
                    "main",
                    "К обеду и ужину: вторые блюда",
                    "/recepty/vtorye-blyuda/",
                    "Все вторые блюда",
                    shelf(s.category("vtorye-blyuda")),
                ),
            ]
            season_key = SEASONAL.get(time.localtime().tm_mon)
            if season_key in cols:
                shelves.append(
                    (
                        "season",
                        cols[season_key][0],
                        f"/podborki/{season_key}/",
                        "Вся подборка",
                        shelf(cols[season_key][2]),
                    )
                )
            if "do-shesti-produktov" in cols:
                shelves.append(
                    (
                        "few",
                        cols["do-shesti-produktov"][0],
                        "/podborki/do-shesti-produktov/",
                        "Вся подборка",
                        shelf(cols["do-shesti-produktov"][2]),
                    )
                )
            shelves = [x for x in shelves if x[4]]
            sections = [(k, CATEGORIES[k][0], len(s.category(k))) for k in CATEGORIES if s.category(k)]
            chips = sorted(s.product_options(), key=lambda kv: -len(s.tag(kv[0])))[:6]
            meta = seo.Meta(
                title=s.cfg["name"] + " — простые рецепты на каждый день",
                description=seo.with_examples(
                    f"{len(s.recipes)} {seo.plural(len(s.recipes), 'рецепт', 'рецепта', 'рецептов')} на каждый день "
                    "с точными количествами и пересчётом порций",
                    [label.lower() for _, label, _ in sections],
                ),
                canonical=s.abs("/"),
                index=True,
                page_type="home",
                jsonld=[
                    seo.website_ld(s),
                    seo.itemlist_ld(s, [r.url for r in quick] + [r.url for x in shelves for r in x[4]]),
                ],
            )
            return (
                200,
                self.render(
                    "home.html",
                    meta,
                    quick=quick,
                    shelves=shelves,
                    sections=sections,
                    chips=chips,
                    total=len(s.recipes),
                ),
                {},
            )
        if path == "/na-kompaniyu/":
            return self.party(query)
        if path == "/iz-holodilnika/":
            return self.fridge(query)
        m = re.fullmatch(r"/recepty/(?:page/(\d+)/)?", path)
        if m:
            n = int(m.group(1) or 1)
            filt = {"product": q1("produkt"), "time": q1("vremya"), "category": q1("tip")}
            sort = q1("sort") if q1("sort") in ("vremya", "nazvanie") else ""
            table = q1("vid") == "tablica"
            filtered = any(filt.values()) or bool(sort) or table
            items = s.filter(**filt) if any(filt.values()) else s.recipes
            if sort == "vremya":  # без указанного времени — в конце
                items = sorted(items, key=lambda r: (r.total_minutes is None, r.total_minutes or 0, r.title))
            elif sort == "nazvanie":
                items = sorted(items, key=lambda r: r.title)
            chunk, n, pages = s.page(items, n)
            if n > pages or (m.group(1) and n == 1):
                return self.not_found()
            meta = seo.listing_meta(
                s,
                title="Все рецепты",
                description="Каталог рецептов на каждый день: по разделам, " "продуктам и времени приготовления.",
                path="/recepty/",
                crumbs=[("Главная", "/"), ("Рецепты", "/recepty/")],
                page=n,
                pages=pages,
            )
            if filtered:  # неподготовленные сочетания фильтров не индексируются и не имеют своего canonical
                meta.index, meta.canonical, meta.prev, meta.next = False, None, None, None
                meta.title = "Подбор рецептов"
            # выбранные условия: подпись, адрес без этого условия и сколько рецептов найдётся без него
            names = {
                "product": ("produkt", "Продукт", dict(s.product_options())),
                "time": ("vremya", "Время", {k: v[0] for k, v in TIME_BUCKETS.items()}),
                "category": ("tip", "Раздел", {k: v[0] for k, v in CATEGORIES.items()}),
            }
            active = []
            for key, (_, label, opts) in names.items():
                if filt[key] in opts:
                    rest = {k: v for k, v in filt.items() if k != key}
                    qs = urllib.parse.urlencode(
                        [(names[k][0], v) for k, v in rest.items() if v]
                        + [(x, y) for x, y in (("sort", sort), ("vid", "tablica" if table else "")) if y]
                    )
                    n_without = len(s.filter(**rest)) if any(rest.values()) else len(s.recipes)
                    active.append(
                        (f"{label}: {opts[filt[key]].lower()}", "/recepty/" + ("?" + qs if qs else ""), n_without)
                    )
            return (
                200,
                self.render(
                    "catalog.html",
                    meta,
                    active=active,
                    items=chunk,
                    page=n,
                    pages=pages,
                    total=len(items),
                    filt=filt,
                    filtered=filtered,
                    sort=sort,
                    table=table,
                    base="/recepty/",
                    products=s.product_options(),
                ),
                {},
            )
        m = re.fullmatch(r"/recepty/([a-z-]+)/(?:page/(\d+)/)?", path)
        if m and m.group(1) in CATEGORIES:
            key, n = m.group(1), int(m.group(2) or 1)
            items = s.category(key)
            chunk, n, pages = s.page(items, n)
            if not items or n > pages or (m.group(2) and n == 1):
                return self.not_found()
            label, desc = CATEGORIES[key]
            meta = seo.listing_meta(
                s,
                title=f"{label}: рецепты",
                description=seo.with_examples(
                    f"{desc} {len(items)} {seo.plural(len(items), 'рецепт', 'рецепта', 'рецептов')}",
                    [r.title for r in items],
                ),
                path=f"/recepty/{key}/",
                crumbs=[("Главная", "/"), ("Рецепты", "/recepty/"), (label, f"/recepty/{key}/")],
                page=n,
                pages=pages,
                page_type="category",
                items=chunk,
            )
            return (
                200,
                self.render(
                    "listing.html",
                    meta,
                    heading=label,
                    lead=desc,
                    items=chunk,
                    page=n,
                    pages=pages,
                    base=f"/recepty/{key}/",
                ),
                {},
            )
        m = re.fullmatch(r"/(produkty|sposob)/([a-z-]+)/", path)
        if m:
            key = m.group(2)
            kind = "product" if m.group(1) == "produkty" else "method"
            pages_map = s.tag_pages()
            if key not in pages_map or TAGS[key][1] != kind:
                return self.not_found()
            label = TAGS[key][0]
            items = pages_map[key]
            title = f"Рецепты: {label.lower()}" if kind == "product" else f"{label}: рецепты"
            n_items = len(items)
            desc = seo.with_examples(
                f"{label} в {n_items} {seo.plural(n_items, 'рецепте', 'рецептах', 'рецептах')}"
                if kind == "product"
                else f"{label.capitalize()} — {n_items} {seo.plural(n_items, 'рецепт', 'рецепта', 'рецептов')}",
                [r.title for r in items],
            )
            meta = seo.listing_meta(
                s,
                title=title,
                description=desc,
                path=path,
                crumbs=[("Главная", "/"), (TAG_KIND_LABEL[kind], f"/{m.group(1)}/"), (label, path)],
                page=1,
                pages=1,
                index=s.tag_indexable(key),
                page_type="tag",
                items=items,
            )
            return (
                200,
                self.render(
                    "listing.html",
                    meta,
                    heading=title,
                    lead=desc,
                    items=items,
                    page=1,
                    pages=1,
                    base=path,
                ),
                {},
            )
        m = re.fullmatch(r"/podborki/([a-z0-9-]+)/", path)
        if m:
            cols = s.collections()
            if m.group(1) not in cols:
                return self.not_found()
            title, desc, items = cols[m.group(1)]
            meta = seo.listing_meta(
                s,
                title=title,
                description=seo.with_examples(desc.rstrip(".") + ". В подборке", [r.title for r in items]),
                path=path,
                crumbs=[("Главная", "/"), ("Подборки", "/podborki/"), (title, path)],
                page=1,
                pages=1,
                page_type="collection",
                items=items,
            )
            return (
                200,
                self.render(
                    "listing.html",
                    meta,
                    heading=title,
                    lead=desc,
                    items=items,
                    page=1,
                    pages=1,
                    base=path,
                ),
                {},
            )
        if path in ("/produkty/", "/sposob/"):
            kind = "product" if path == "/produkty/" else "method"
            rows = s.tag_index(kind)
            if not rows:
                return self.not_found()
            title = TAG_KIND_LABEL[kind]
            meta = seo.Meta(
                title=f"{title}: рецепты по темам",
                description=seo.with_examples(
                    "Рецепты по главному продукту" if kind == "product" else "Рецепты по способу приготовления",
                    [label.lower() for _, label, *_ in rows],
                ),
                canonical=s.abs(path),
                index=True,
                breadcrumbs=[("Главная", "/"), (title, path)],
                page_type="tag_index",
            )
            return 200, self.render("tags.html", meta, heading=title, rows=rows), {}
        if path == "/sovety/":
            meta = seo.Meta(
                title="Советы для кухни",
                description="Как понять, что блюдо готово, как работает пересчёт " "порций и чем заменить продукты.",
                canonical=s.abs(path),
                index=True,
                breadcrumbs=[("Главная", "/"), ("Советы", path)],
                page_type="article_index",
            )
            return 200, self.render("articles.html", meta, articles=list(s.articles.values())), {}
        m = re.fullmatch(r"/sovety/([a-z0-9-]+)/", path)
        if m:
            a = s.articles.get(m.group(1))
            if not a:
                return self.not_found()
            return 200, self.render("article.html", seo.article_meta(s, a), a=a), {}
        if path == "/podborki/":
            meta = seo.Meta(
                title="Подборки рецептов",
                description=seo.with_examples(
                    "Подборки рецептов по времени, продуктам и сезону",
                    [v[0].lower().replace(":", " —") for v in s.collections().values()],
                ),
                canonical=s.abs(path),
                index=True,
                breadcrumbs=[("Главная", "/"), ("Подборки", path)],
                page_type="collection_index",
            )
            return 200, self.render("collections.html", meta, collections=s.collections()), {}
        m = re.fullmatch(r"/recept/([a-z0-9-]+)/", path)
        if m:
            r = s.by_slug.get(m.group(1))
            if not r:
                return self.not_found()
            return 200, self.render("recipe.html", seo.recipe_meta(s, r), r=r), {}
        if path == "/poisk/":
            q = q1("q")[:120]
            found = s.search(q) if q else []
            # уточнение по разделу: только разделы, где есть найденные блюда; счётчик = число показанных карточек
            sections = [(k, CATEGORIES[k][0], sum(r.category == k for r in found)) for k in CATEGORIES]
            sections = sorted((x for x in sections if x[2]), key=lambda x: -x[2])
            razdel = q1("razdel") if q1("razdel") in CATEGORIES else ""
            items = [r for r in found if r.category == razdel] if razdel else found
            meta = seo.Meta(
                title=f"Поиск: {q}" if q else "Поиск рецептов",
                description="Поиск по названиям и продуктам.",
                canonical=None,
                index=False,
                page_type="search",
            )
            return (
                200,
                self.render(
                    "search.html", meta, q=q, items=items, found=found, sections=sections, razdel=razdel,
                    qs=urllib.parse.quote(q),
                ),
                {},
            )
        if path in ("/izbrannoe/", "/spisok-pokupok/"):
            fav = path == "/izbrannoe/"
            meta = seo.Meta(
                title="Избранное" if fav else "Список покупок",
                description="Хранится только в этом браузере, без регистрации.",
                canonical=None,
                index=False,
                page_type="tool",
            )
            catalog = [
                {
                    "slug": r.slug,
                    "title": r.title,
                    "url": r.url,
                    "time": r.time_label,
                    "category": r.category_label,
                }
                for r in s.recipes
            ]
            return (
                200,
                self.render("tool.html", meta, fav=fav, catalog=json.dumps(catalog, ensure_ascii=False)),
                {},
            )
        if path == "/o-proekte/":
            meta = seo.Meta(
                title="О проекте",
                description="«Будни на кухне» — простые домашние рецепты: откуда берутся состав и количества, "
                "что умеет сайт и чего на нём нет.",
                canonical=s.abs(path),
                index=True,
                breadcrumbs=[("Главная", "/"), ("О проекте", path)],
                page_type="info",
            )
            return 200, self.render("about.html", meta), {}
        if path == "/konfidencialnost/":
            meta = seo.Meta(
                title="Конфиденциальность",
                description="Какие данные записывает сайт «Будни на кухне»: журнал веб-сервера, хранилище браузера; "
                "без cookies, счётчиков и рекламы.",
                canonical=s.abs(path),
                index=True,
                breadcrumbs=[("Главная", "/"), ("Конфиденциальность", path)],
                page_type="info",
            )
            return 200, self.render("privacy.html", meta), {}
        if path in PAGE_REDIRECTS:
            return 301, "", {"Location": PAGE_REDIRECTS[path]}
        if path == "/robots.txt":
            return 200, self.robots(), {"Content-Type": "text/plain; charset=utf-8"}
        if path == "/sitemap.xml":
            return 200, self.sitemap(), {"Content-Type": "application/xml; charset=utf-8"}
        if path == "/api/catalog.v1.json":
            # Контракт recipe-catalog/1 для других сайтов сети (меню недели): только опубликованное,
            # только факты и адреса; тексты шагов не отдаются. Не индексируется (X-Robots-Tag, вне sitemap).
            return 200, json.dumps(self.catalog(), ensure_ascii=False), {"Content-Type": "application/json"}
        if path == "/healthz":
            return (
                200,
                json.dumps(
                    {
                        "site_id": s.cfg["site_id"],
                        "mode": s.mode,
                        "recipes": len(s.recipes),
                        "snapshot": s.generated_at,
                    }
                ),
                {"Content-Type": "application/json"},
            )
        return self.not_found()

    def catalog(self) -> dict:
        s = self.site
        return {
            "schema": "recipe-catalog/1",
            "site_id": s.cfg["site_id"],
            "mode": s.mode,
            "origin": s.origin,
            "generated_at": s.generated_at,
            "items": [
                {
                    "content_id": r.raw["content_id"],
                    "version": r.raw["version"],
                    "slug": r.slug,
                    "path": r.url,
                    "title": r.title,
                    "category": r.category,
                    "category_label": r.category_label,
                    "servings": r.servings,
                    "total_minutes": r.total_minutes,
                    "review_status": r.raw["review_status"],
                    "ingredients": [
                        {"name": i.name, "quantity": i.quantity, "quantity_max": i.quantity_max, "unit": i.unit}
                        for i, _ in r.ingredients
                    ],
                }
                for r in s.recipes
            ],
        }

    def party(self, query: dict) -> tuple[int, str, dict]:
        """На компанию: без выбора — индексируемая форма; с выбором — noindex без canonical; гостей вне 1–20 — 400."""
        s = self.site
        want = [x for x in query.get("r", []) if x][:12]
        raw = (query.get("gosti") or [""])[0].strip()
        guests = int(raw) if raw.isdigit() else (0 if raw else 6)
        error = None
        if not 1 <= guests <= 20:
            error, guests = "Число гостей — от 1 до 20.", 6
        p = s.party(want, guests)
        if want and not p["recipes"] and not error:
            error = "Таких рецептов на сайте нет — отметьте из списка."
        asked = bool(want or raw)
        crumbs = [("Главная", "/"), ("На компанию", "/na-kompaniyu/")]
        meta = seo.Meta(
            title="Готовим на компанию: общий список продуктов"
            if not p["recipes"]
            else f"На компанию: {guests} "
            + (
                "гость"
                if guests % 10 == 1 and guests % 100 != 11
                else "гостя"
                if guests % 10 in (2, 3, 4) and guests % 100 not in (12, 13, 14)
                else "гостей"
            ),
            description="Отметьте блюда и число гостей — продукты всех рецептов пересчитаются в один список.",
            canonical=None if asked else s.abs("/na-kompaniyu/"),
            index=not asked,
            page_type="page",
            breadcrumbs=crumbs,
            jsonld=[seo.breadcrumb_ld(s, crumbs)],
        )
        body = self.render("party.html", meta, p=p, guests=guests, picked=want, error=error)
        return (400 if error else 200), body, {}

    def fridge(self, query: dict) -> tuple[int, str, dict]:
        """Подбор «что есть дома». Без параметров — индексируемая страница выбора;
        с параметрами — noindex без canonical, неизвестные продукты — 400."""
        s = self.site
        options = s.fridge_products()
        known = {k for k, *_ in options}
        raw = [x.strip() for x in query.get("est", []) if x.strip()][:30]
        have = [k for k in dict.fromkeys(raw) if k in known]
        crumbs = [("Главная", "/"), ("Из холодильника", "/iz-holodilnika/")]
        meta = seo.Meta(
            title="Что приготовить из того, что есть дома",
            description="Отметьте продукты, которые есть дома, — покажем рецепты, где они нужны, и чего не хватает.",
            canonical=s.abs("/iz-holodilnika/"),
            index=True,
            page_type="page",
            breadcrumbs=crumbs,
            jsonld=[seo.breadcrumb_ld(s, crumbs)],
        )
        error = None
        if raw:
            meta.index, meta.canonical = False, None
            if not have:
                error = "Таких продуктов в рецептах нет. Отметьте продукты из списка."
            else:
                meta.title = "Подбор: " + ", ".join(PRODUCTS[k][0].lower() for k in have)
        rows = s.fridge(have) if have else []
        groups = [(g, [o for o in options if o[2] == i]) for i, g in enumerate(PANTRY_GROUPS)]
        picked = [(k, PRODUCTS[k][0], urllib.parse.urlencode([("est", x) for x in have if x != k])) for k in have]
        body = self.render("fridge.html", meta, groups=groups, have=have, picked=picked, rows=rows, error=error)
        return (400 if error else 200), body, {}

    def not_found(self) -> tuple[int, str, dict]:
        meta = seo.Meta(
            title="Страница не найдена",
            description="Такой страницы нет.",
            canonical=None,
            index=False,
            page_type="404",
        )
        return 404, self.render("404.html", meta, recipes=self.site.recipes[:3]), {}

    def robots(self) -> str:
        if not self.site.indexable:
            return "# preview: индексация закрыта\nUser-agent: *\nDisallow: /\n"
        return (
            f"User-agent: *\nDisallow: /poisk/\nDisallow: /izbrannoe/\nDisallow: /spisok-pokupok/\n"
            f"Disallow: /redaktor/\nDisallow: /*?\n\nSitemap: {self.site.abs('/sitemap.xml')}\n"
        )

    def sitemap_urls(self) -> list[tuple[str, str | None]]:
        """Только индексируемые canonical URL со статусом 200."""
        s = self.site
        urls: list[tuple[str, str | None]] = [
            ("/", s.recipes[0].updated_at[:10] if s.recipes else None),
            ("/recepty/", None),
            ("/na-kompaniyu/", None),
            ("/iz-holodilnika/", None),
            ("/podborki/", None),
            ("/o-proekte/", None),
            ("/konfidencialnost/", None),
        ]
        for key in CATEGORIES:
            items = s.category(key)
            if items:
                urls.append((f"/recepty/{key}/", max(r.updated_at for r in items)[:10]))
                _, _, pages = s.page(items, 1)
                urls += [(f"/recepty/{key}/page/{n}/", None) for n in range(2, pages + 1)]
        _, _, pages = s.page(s.recipes, 1)
        urls += [(f"/recepty/page/{n}/", None) for n in range(2, pages + 1)]
        for key, items in s.tag_pages().items():
            if s.tag_indexable(key):
                urls.append(
                    (
                        f"/{'produkty' if TAGS[key][1] == 'product' else 'sposob'}/{key}/",
                        max(r.updated_at for r in items)[:10],
                    )
                )
        urls += [(f"/podborki/{k}/", None) for k in s.collections()]
        urls += [
            (p, None) for p in ("/produkty/", "/sposob/") if s.tag_index("product" if p == "/produkty/" else "method")
        ]
        if s.articles:
            urls.append(("/sovety/", max(a["updated"] for a in s.articles.values())))
            urls += [(f"/sovety/{a['slug']}/", a["updated"]) for a in s.articles.values()]
        urls += [(r.url, r.updated_at[:10]) for r in s.recipes]
        return urls

    def sitemap(self) -> str:
        rows = []
        for path, lastmod in self.sitemap_urls():
            lm = f"<lastmod>{lastmod}</lastmod>" if lastmod else ""
            rows.append(f"<url><loc>{self.site.abs(path)}</loc>{lm}</url>")
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "\n".join(rows)
            + "\n</urlset>\n"
        )

    # ---- редактор -----------------------------------------------------
    def editor_auth(self, header: str | None) -> str | None:
        if not EDITOR_SECRET.exists() or not header or not header.startswith("Basic "):
            return None
        try:
            user, pw = b64decode(header[6:]).decode().split(":", 1)
        except Exception:
            return None
        sec = json.loads(EDITOR_SECRET.read_text())
        h = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(sec["salt"]), n=2**14, r=8, p=1).hex()
        return user if hmac.compare_digest(user, sec["user"]) and hmac.compare_digest(h, sec["hash"]) else None

    def csrf(self, user: str) -> str:
        return hmac.new(self.csrf_key, user.encode(), "sha256").hexdigest()


TAG_KIND_LABEL = {"product": "Продукты", "method": "Способы приготовления"}

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
    "frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


def make_handler(app: App):
    from . import editor_web

    class Handler(http.server.BaseHTTPRequestHandler):
        server_version = "food-daily"
        sys_version = ""

        def log_message(self, fmt, *args):  # журнал без query string и заголовков
            pass

        def _send(self, status: int, body: str | bytes, headers: dict | None = None):
            data = body.encode() if isinstance(body, str) else body
            self.send_response(status)
            h = {"Content-Type": "text/html; charset=utf-8", **SECURITY_HEADERS, **(headers or {})}
            if not app.site.indexable:
                h["X-Robots-Tag"] = "noindex, nofollow"
            h["Content-Length"] = str(len(data))
            for k, v in h.items():
                self.send_header(k, v)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)

        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            u = urllib.parse.urlsplit(self.path)
            if u.path.startswith("/static/"):
                rel = u.path[len("/static/") :]
                p = (STATIC / rel).resolve()
                if STATIC.resolve() not in p.parents or not p.is_file():
                    return self._send(*app.not_found()[:2])
                ctype = {
                    ".css": "text/css; charset=utf-8",
                    ".js": "text/javascript; charset=utf-8",
                    ".svg": "image/svg+xml",
                    ".png": "image/png",
                    ".webp": "image/webp",
                    ".woff2": "font/woff2",
                    ".ico": "image/x-icon",
                    ".vtt": "text/vtt",
                }.get(p.suffix, "application/octet-stream")
                return self._send(
                    200,
                    p.read_bytes(),
                    {"Content-Type": ctype, "Cache-Control": "public, max-age=31536000, immutable"},
                )
            if u.path.startswith("/redaktor"):
                return editor_web.handle(self, app, "GET", u)
            if u.path not in ("/", "/healthz") and not u.path.endswith("/") and "." not in u.path.rsplit("/", 1)[-1]:
                return self._send(301, "", {"Location": u.path + "/" + (("?" + u.query) if u.query else "")})
            try:
                status, body, headers = app.route(u.path, urllib.parse.parse_qs(u.query))
            except Exception:  # ошибка отдаётся кодом 500, а не обрывом соединения
                import traceback

                traceback.print_exc()
                status, body, headers = (
                    500,
                    "Внутренняя ошибка",
                    {"Content-Type": "text/plain; charset=utf-8"},
                )
            self._send(status, body, headers)

        def do_POST(self):
            u = urllib.parse.urlsplit(self.path)
            if u.path.startswith("/redaktor"):
                return editor_web.handle(self, app, "POST", u)
            self._send(
                405,
                "method not allowed",
                {"Content-Type": "text/plain; charset=utf-8", "Allow": "GET, HEAD"},
            )

    return Handler


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="food-daily serve")
    ap.add_argument("--port", type=int)
    a = ap.parse_args(argv)
    app = App()
    bind = app.site.cfg["server"]["bind"]
    if bind not in ("127.0.0.1", "::1"):
        raise SystemExit("preview слушает только петлю")
    port = a.port or app.site.cfg["server"]["port"]
    srv = Server((bind, port), make_handler(app))
    print(
        json.dumps(
            {
                "listening": f"http://{bind}:{port}/",
                "mode": app.site.mode,
                "recipes": len(app.site.recipes),
            }
        ),
        flush=True,
    )
    srv.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
