"""SSR-сервер food-baking. Весь текст и ссылки — в серверном HTML; JS только
добавляет таймеры и отметки «взвешено». Внешних API при чтении нет."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import http.server
import json
import os
import re
import socketserver
import time
import urllib.parse
from base64 import b64decode
from dataclasses import dataclass, field
from pathlib import Path

import jinja2

from .drafts import DOUGH_LABELS, HISTORY
from .site import GROUPS, TAGS, Recipe, Site, ru_date

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"
EDITOR_SECRET = Path(
    os.environ.get(
        "FOOD_BAKING_B_EDITOR_SECRET", str(Path.home() / ".config" / "food-baking-b-preview" / "editor.json")
    )
)
HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
    "frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
}


def plural(n: int, one: str, few: str, many: str) -> str:
    m = abs(n) % 100
    if 11 <= m <= 14:
        return many
    return one if m % 10 == 1 else few if 2 <= m % 10 <= 4 else many


SNIPPET_MAX = 160


def snippet(text: str, limit: int = SNIPPET_MAX) -> str:
    """Описание для сниппета: целиком, если помещается; иначе — по границе фразы, запятой или тире."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = max(text.rfind(". ", 0, limit), text.rfind("; ", 0, limit))
    if cut >= limit // 3:
        return text[: cut + 1].rstrip(";") + ("" if text[cut] == "." else ".")
    for sep in (", ", " — "):
        cut = text.rfind(sep, 0, limit - 1)
        if cut >= limit // 2:
            return text[:cut].rstrip(",;:—– ") + "…"
    return text[: text.rfind(" ", 0, limit - 1)].rstrip(",;:—– ") + "…"


def with_examples(head: str, titles: list[str], limit: int = 160) -> str:
    """Описание из данных: «<head>: название, название…» — столько названий, сколько помещается в limit."""
    out, shown = head, 0
    for t in titles:
        nxt = out + (": " if not shown else ", ") + t
        tail = "." if shown + 1 == len(titles) else " и другие."
        if len(nxt + tail) > limit:
            break
        out, shown = nxt, shown + 1
    if not shown:
        return head + "."
    return out + ("." if shown == len(titles) else " и другие.")


@dataclass
class Meta:
    title: str
    description: str
    canonical: str | None
    index: bool
    crumbs: list = field(default_factory=list)
    ld: list = field(default_factory=list)
    kind: str = "page"
    prev: str | None = None
    next: str | None = None

    def robots(self, site: Site) -> str:
        if not site.indexable:
            return "noindex, nofollow"
        return "index, follow" if self.index else "noindex, follow"

    def ld_json(self) -> list[str]:
        return [json.dumps(x, ensure_ascii=False).replace("</", "<\\/") for x in self.ld]


def crumbs_ld(site: Site, crumbs) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": n, "item": site.abs(p)} for i, (n, p) in enumerate(crumbs)
        ],
    }


def items_ld(site: Site, recipes: list[Recipe]) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "url": site.abs(r.url)} for i, r in enumerate(recipes)
        ],
    }


def website_ld(site: Site) -> dict:
    """WebSite с поиском: поиск на сайте действительно есть (/poisk/?q=)."""
    return {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": site.cfg["name"],
        "url": site.abs("/"),
        "inLanguage": "ru",
        "potentialAction": {
            "@type": "SearchAction",
            "target": {"@type": "EntryPoint", "urlTemplate": site.abs("/poisk/") + "?q={search_term_string}"},
            "query-input": "required name=search_term_string",
        },
    }


def iso(m) -> str | None:
    if not m:
        return None
    h, mm = divmod(int(m), 60)
    return "PT" + (f"{h}H" if h else "") + (f"{mm}M" if mm else "")


def recipe_ld(site: Site, r: Recipe) -> dict:
    ld = {
        "@context": "https://schema.org",
        "@type": "Recipe",
        "name": r.title,
        "description": r.intro,
        "url": site.abs(r.url),
        "recipeCategory": r.group_label,
        "recipeYield": f"{r.servings} порц.",
        "recipeIngredient": [f"{i['name']}, {i['amount']}" for i in r.ingredients],
        "recipeInstructions": [
            {"@type": "HowToStep", "position": n + 1, "text": s["text"], "url": site.abs(r.url) + f"#shag-{n + 1}"}
            for n, s in enumerate(r.steps)
        ],
        "datePublished": r.published_at,
        "dateModified": r.updated_at,
        "inLanguage": "ru",
        "keywords": ", ".join(TAGS.get(t, t) for t in r.tags),
    }
    if r.image:  # только изображение с установленными правами (data/media/images.json)
        ld["image"] = [site.abs(f"/static/media/{r.image['file']}-{w}.webp") for w in r.image["widths"]]
    for k, v in (
        ("prepTime", r.times["prep_minutes"]),
        ("cookTime", r.times["cook_minutes"]),
        ("totalTime", r.times["total_minutes"]),
    ):
        if v:
            ld[k] = iso(v)
    return ld


class App:
    def __init__(self, site: Site | None = None):
        self.site = site or Site()
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(ROOT / "templates"),
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True,
            undefined=jinja2.StrictUndefined,
        )
        self.hashes = {
            str(p.relative_to(STATIC)): hashlib.sha256(p.read_bytes()).hexdigest()[:10]
            for p in STATIC.rglob("*")
            if p.is_file()
        }
        self.env.globals.update(
            site=self.site,
            DOUGH=DOUGH_LABELS,
            TAGS=TAGS,
            GROUPS=GROUPS,
            asset=lambda rel: f"/static/{rel}?v={self.hashes.get(rel, '0')}",
            plural=plural,
            year=time.strftime("%Y"),
        )
        self.env.filters["ru_date"] = ru_date

    def render(self, tpl: str, meta: Meta, **ctx) -> str:
        return self.env.get_template(tpl).render(meta=meta, **ctx)

    def listing(self, title, desc, path, crumbs, items, n=1, pages=1, index=True, kind="listing") -> Meta:
        own = path if n == 1 else f"{path}page/{n}/"
        if n > 1:
            title, desc = f"{title} — страница {n}", f"{desc} Страница {n} из {pages}."
        s = self.site
        return Meta(
            title,
            desc,
            s.abs(own),
            index,
            crumbs,
            [crumbs_ld(s, crumbs), items_ld(s, items)],
            kind,
            s.abs(path if n == 2 else f"{path}page/{n - 1}/") if n > 1 else None,
            s.abs(f"{path}page/{n + 1}/") if n < pages else None,
        )

    def route(self, path: str, q: dict) -> tuple[int, str, dict]:
        s = self.site
        g = lambda k: (q.get(k) or [""])[0].strip()  # noqa: E731
        if path == "/pechem/":
            want = [x for x in q.get("r", []) if x][:20]
            bs = s.bake_set(want)
            error = "Таких рецептов в книге нет — отметьте из списка." if want and not bs["recipes"] else None
            n = len(bs["recipes"])
            meta = Meta(
                f"Пеку несколько: {n} {'рецепт' if n % 10 == 1 and n % 100 != 11 else ('рецепта' if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14) else 'рецептов')}"
                if n
                else "Пеку несколько: общий список продуктов",
                "Отметьте рецепты — сайт сложит продукты в один список и расставит рецепты по температуре духовки.",
                None if want else s.abs(path),
                not want,
                kind="batch",
            )
            meta.crumbs = [("Главная", "/"), ("Пеку несколько", path)]
            return (400 if error else 200), self.render("batch.html", meta, bs=bs, picked=want, error=error), {}
        if path == "/":
            groups = s.groups()
            season = s.season(time.localtime().tm_mon)
            shown = {r.slug for r in season[2][:4]} if season else set()
            tea = [r for r in s.tags().get("k-chayu", []) if r.slug not in shown][:4]  # без повтора сезонных
            tea = tea if len(tea) >= 2 else []
            shown |= {r.slug for r in tea}
            # «Новые» — без карточек, уже показанных выше; полными рядами по 4, если рецептов больше четырёх
            fresh = [
                r
                for r in sorted(s.recipes, key=lambda r: (r.published_at, r.updated_at), reverse=True)
                if r.slug not in shown
            ][:8]
            if len(fresh) > 4:
                fresh = fresh[: len(fresh) // 4 * 4]
            meta = Meta(
                f"{s.cfg['name']} — рецепты домашней выпечки",
                with_examples(
                    f"{len(s.recipes)} {plural(len(s.recipes), 'рецепт', 'рецепта', 'рецептов')} домашней выпечки "
                    "с температурой духовки, временем и формой",
                    [v.lower() for k, v in GROUPS.items() if k in groups],
                ),
                s.abs("/"),
                True,
                kind="home",
                ld=[website_ld(s), items_ld(s, fresh)],
            )
            return (
                200,
                self.render("home.html", meta, groups=groups, tea=tea, season=season, fresh=fresh),
                {},
            )
        if path == "/duhovka/":
            crumbs = [("Главная", "/"), ("По температуре", path)]
            meta = Meta(
                "Выпечка по температуре духовки",
                "Разогрели духовку — смотрите, что печётся при этой температуре: "
                + ", ".join(f"{t} °C" if t else "без духовки" for t, _ in s.by_temp())
                + ".",
                s.abs(path),
                True,
                crumbs,
                [crumbs_ld(s, crumbs)],
                kind="temps",
            )
            return 200, self.render("temps.html", meta), {}
        m = re.fullmatch(r"/recepty/([a-z]+)/", path)
        if m and m.group(1) in s.groups():
            key = m.group(1)
            items = s.groups()[key]
            label = GROUPS[key]
            meta = self.listing(
                f"{label}: рецепты",
                with_examples(
                    f"{label} — {len(items)} {plural(len(items), 'рецепт', 'рецепта', 'рецептов')}",
                    [r.title for r in items],
                ),
                path,
                [("Главная", "/"), ("Рецепты", "/recepty/"), (label, path)],
                items,
                kind="group",
                index=s.group_indexable(items),
            )
            return 200, self.render("listing.html", meta, heading=label, items=items), {}
        m = re.fullmatch(r"/recepty/(?:page/(\d+)/)?", path)
        if m:
            n = int(m.group(1) or 1)
            flt = {"dough": g("testo"), "oven": g("duhovka")}
            sort = g("sort") if g("sort") in ("temp", "vremya", "nazvanie") else ""
            table = g("vid") == "tablica"
            filtered = any(flt.values()) or bool(sort) or table
            items = s.sorted_by(s.filter(**flt) if any(flt.values()) else s.recipes, sort)
            chunk, pages = s.page(items, n)
            if n > pages or (m.group(1) and n == 1) or (filtered and n > 1):
                return self.not_found()
            if filtered:  # подбор и таблица сравнения — весь результат на одной странице, без пагинации
                chunk, pages = items, 1
            meta = self.listing(
                "Все рецепты выпечки",
                with_examples(
                    f"Все {len(s.recipes)} {plural(len(s.recipes), 'рецепт', 'рецепта', 'рецептов')} выпечки",
                    [v.lower() for k, v in GROUPS.items() if k in s.groups()],
                ),
                "/recepty/",
                [("Главная", "/"), ("Рецепты", "/recepty/")],
                chunk,
                n,
                pages,
            )
            if filtered:
                meta.index, meta.canonical, meta.prev, meta.next, meta.title = False, None, None, None, "Подбор выпечки"
            return (
                200,
                self.render(
                    "catalog.html",
                    meta,
                    items=chunk,
                    n=n,
                    pages=pages,
                    flt=flt,
                    sort=sort,
                    filtered=filtered,
                    table=table,
                    total=len(items),
                ),
                {},
            )
        m = re.fullmatch(r"/recept/([a-z0-9-]+)/", path)
        if m and m.group(1) in s.by_slug:
            r = s.by_slug[m.group(1)]
            crumbs = (
                [("Главная", "/"), ("Рецепты", "/recepty/")]
                + ([(r.dough_label, f"/testo/{r.dough}/")] if r.dough in s.doughs() else [])
                + [(r.title, r.url)]
            )
            meta = Meta(
                r.seo_title,
                snippet(r.seo_description),
                s.abs(r.url),
                True,
                crumbs,
                [recipe_ld(s, r), crumbs_ld(s, crumbs)],
                "recipe",
            )
            return 200, self.render("recipe.html", meta, r=r), {}
        if path == "/testo/":
            meta = Meta(
                "Виды теста",
                "Рецепты, сгруппированные по виду теста — определяется по составу.",
                s.abs(path),
                True,
                [("Главная", "/"), ("Виды теста", path)],
                kind="dough_index",
            )
            meta.ld = [crumbs_ld(s, meta.crumbs)]
            return 200, self.render("doughs.html", meta), {}
        m = re.fullmatch(r"/testo/([a-z-]+)/", path)
        if m and m.group(1) in s.doughs():
            key = m.group(1)
            label, desc = DOUGH_LABELS[key]
            items = s.doughs()[key]
            meta = self.listing(
                label, desc, path, [("Главная", "/"), ("Виды теста", "/testo/"), (label, path)], items, kind="dough"
            )
            return 200, self.render("dough.html", meta, key=key, items=items, pitfalls=s.pitfalls_for(key)), {}
        m = re.fullmatch(r"/oshibki/([a-z-]+)/", path)
        if m and s.pitfalls_for(m.group(1)):
            key = m.group(1)
            label = DOUGH_LABELS[key][0]
            title = f"{label}: на чём ошибаются"
            meta = Meta(
                title,
                f"Предупреждения из шагов рецептов — {label.lower()}: что сделать, чтобы не испортить.",
                s.abs(path),
                True,
                [("Главная", "/"), ("Виды теста", "/testo/"), (label, f"/testo/{key}/"), ("Ошибки", path)],
                kind="pitfalls",
            )
            meta.ld = [crumbs_ld(s, meta.crumbs)]
            return 200, self.render("pitfalls.html", meta, key=key, rows=s.pitfalls_for(key)), {}
        m = re.fullmatch(r"/teg/([a-z-]+)/", path)
        if m and m.group(1) in s.tags():
            key = m.group(1)
            items = s.tags()[key]
            meta = self.listing(
                f"Выпечка: {TAGS[key].lower()}",
                with_examples(
                    f"«{TAGS[key]}» — {len(items)} {plural(len(items), 'рецепт', 'рецепта', 'рецептов')}",
                    [r.title for r in items],
                ),
                path,
                [("Главная", "/"), ("Рецепты", "/recepty/"), (TAGS[key], path)],
                items,
                kind="tag",
                index=len(items) >= 3,
            )
            return 200, self.render("listing.html", meta, heading=TAGS[key], items=items), {}
        if path == "/poisk/":
            qq = g("q")[:120]
            meta = Meta(
                f"Поиск: {qq}" if qq else "Поиск выпечки", "Поиск по названию и продуктам.", None, False, kind="search"
            )
            return 200, self.render("search.html", meta, q=qq, items=s.search(qq) if qq else []), {}
        if path == "/konfidencialnost/":
            meta = Meta(
                "Конфиденциальность",
                "Какие данные записывает сайт «Тесто и десерты»: журнал веб-сервера, хранилище браузера; "
                "без cookies, счётчиков и рекламы.",
                s.abs(path),
                True,
                [("Главная", "/"), ("Конфиденциальность", path)],
                kind="info",
            )
            return 200, self.render("privacy.html", meta), {}
        if path == "/o-proekte/":
            meta = Meta(
                "О проекте",
                "«Тесто и десерты» — рецепты домашней выпечки: откуда состав, температура и время, "
                "что умеет сайт и чего на нём нет.",
                s.abs(path),
                True,
                [("Главная", "/"), ("О проекте", path)],
                kind="info",
            )
            return 200, self.render("about.html", meta), {}
        if path == "/robots.txt":
            body = (
                "User-agent: *\nDisallow: /\n"
                if not s.indexable
                else (
                    "User-agent: *\nDisallow: /poisk/\nDisallow: /redaktor/\nDisallow: /*?\n\n"
                    f"Sitemap: {s.abs('/sitemap.xml')}\n"
                )
            )
            return 200, body, {"Content-Type": "text/plain; charset=utf-8"}
        if path == "/sitemap.xml":
            return 200, self.sitemap(), {"Content-Type": "application/xml; charset=utf-8"}
        if path == "/healthz":
            return (
                200,
                json.dumps({"site_id": s.cfg["site_id"], "recipes": len(s.recipes)}),
                {"Content-Type": "application/json"},
            )
        return self.not_found()

    def sitemap_urls(self) -> list[tuple[str, str | None]]:
        s = self.site
        urls = [
            ("/", s.recipes[0].updated_at if s.recipes else None),
            ("/recepty/", None),
            ("/pechem/", None),
            ("/duhovka/", None),
            ("/testo/", None),
            ("/o-proekte/", None),
            ("/konfidencialnost/", None),
        ]
        urls += [
            (f"/recepty/{k}/", max(r.updated_at for r in v)) for k, v in s.groups().items() if s.group_indexable(v)
        ]
        _, pages = s.page(s.recipes, 1)
        urls += [(f"/recepty/page/{n}/", None) for n in range(2, pages + 1)]
        urls += [(f"/testo/{k}/", max(r.updated_at for r in v)) for k, v in s.doughs().items()]
        urls += [(f"/oshibki/{k}/", None) for k in s.doughs() if s.pitfalls_for(k)]
        urls += [(f"/teg/{k}/", None) for k, v in s.tags().items() if len(v) >= 3]
        urls += [(r.url, r.updated_at) for r in s.recipes]
        return urls

    def sitemap(self) -> str:
        rows = "\n".join(
            f"<url><loc>{self.site.abs(p)}</loc>{f'<lastmod>{lm}</lastmod>' if lm else ''}</url>"
            for p, lm in self.sitemap_urls()
        )
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            f"\n{rows}\n</urlset>\n"
        )

    def not_found(self):
        meta = Meta("Страница не найдена", "Такой страницы нет.", None, False, kind="404")
        return 404, self.render("404.html", meta), {}

    def editor(self, auth: str | None) -> tuple[int, str, dict]:
        user = None
        if EDITOR_SECRET.exists() and auth and auth.startswith("Basic "):
            try:
                u, pw = b64decode(auth[6:]).decode().split(":", 1)
                sec = json.loads(EDITOR_SECRET.read_text())
                h = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(sec["salt"]), n=2**14, r=8, p=1).hex()
                if hmac.compare_digest(u, sec["user"]) and hmac.compare_digest(h, sec["hash"]):
                    user = u
            except Exception:
                user = None
        if not user:
            return (
                401,
                "Требуется вход редактора",
                {"WWW-Authenticate": 'Basic realm="food-baking editor"', "Content-Type": "text/plain; charset=utf-8"},
            )
        drafts = {p.stem: json.loads(p.read_text()) for p in (ROOT / "data" / "drafts").glob("*.json")}
        history = [json.loads(x) for x in HISTORY.read_text().splitlines()] if HISTORY.exists() else []
        meta = Meta("Редактор", "Состояние материалов", None, False, kind="editor")
        return 200, self.render("editor.html", meta, recipes=self.site.recipes, drafts=drafts, history=history), {}


def make_handler(app: App):
    class H(http.server.BaseHTTPRequestHandler):
        server_version = "food-baking"
        sys_version = ""

        def log_message(self, *a):
            pass

        def send(self, status, body, headers=None):
            data = body.encode() if isinstance(body, str) else body
            self.send_response(status)
            hh = {"Content-Type": "text/html; charset=utf-8", **HEADERS, **(headers or {})}
            if not app.site.indexable:
                hh["X-Robots-Tag"] = "noindex, nofollow"
            hh["Content-Length"] = str(len(data))
            for k, v in hh.items():
                self.send_header(k, v)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)

        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            u = urllib.parse.urlsplit(self.path)
            if u.path.startswith("/static/"):
                p = (STATIC / u.path[8:]).resolve()
                if STATIC.resolve() not in p.parents or not p.is_file():
                    return self.send(*app.not_found()[:2])
                ct = {
                    ".css": "text/css; charset=utf-8",
                    ".js": "text/javascript; charset=utf-8",
                    ".svg": "image/svg+xml",
                    ".webp": "image/webp",
                    ".woff2": "font/woff2",
                    ".txt": "text/plain; charset=utf-8",
                }.get(p.suffix, "application/octet-stream")
                return self.send(
                    200, p.read_bytes(), {"Content-Type": ct, "Cache-Control": "public, max-age=31536000, immutable"}
                )
            if u.path in ("/redaktor", "/redaktor/"):
                return self.send(*app.editor(self.headers.get("Authorization")))
            if u.path not in ("/", "/healthz") and not u.path.endswith("/") and "." not in u.path.rsplit("/", 1)[-1]:
                return self.send(301, "", {"Location": u.path + "/" + (f"?{u.query}" if u.query else "")})
            try:
                self.send(*app.route(u.path, urllib.parse.parse_qs(u.query)))
            except Exception:
                import traceback

                traceback.print_exc()
                self.send(500, "Внутренняя ошибка", {"Content-Type": "text/plain; charset=utf-8"})

    return H


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="food-baking serve")
    ap.add_argument("--port", type=int, help="другой локальный порт (чистая копия рядом с действующим превью)")
    new_port = ap.parse_args(argv).port
    app = App()
    bind, port = app.site.cfg["server"]["bind"], app.site.cfg["server"]["port"]
    port = new_port or port
    if bind not in ("127.0.0.1", "::1"):
        raise SystemExit("preview слушает только петлю")
    print(json.dumps({"listening": f"http://{bind}:{port}/", "recipes": len(app.site.recipes)}), flush=True)
    Server((bind, port), make_handler(app)).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
