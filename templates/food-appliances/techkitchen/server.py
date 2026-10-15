"""SSR-сервер food-appliances."""

from __future__ import annotations

import hashlib
import json
import re
import socketserver
import urllib.parse
from dataclasses import dataclass, field
from http import server as http_server
from pathlib import Path

import jinja2

from .site import APPLIANCES, CATEGORIES, Recipe, Site

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"
HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; "
    "frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
}


@dataclass
class Meta:
    title: str
    description: str
    canonical: str | None
    index: bool
    crumbs: list = field(default_factory=list)
    ld: list = field(default_factory=list)
    kind: str = "page"


def iso(m):
    if not m:
        return None
    h, mm = divmod(int(m), 60)
    return "PT" + (f"{h}H" if h else "") + (f"{mm}M" if mm else "")


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
        h = {
            str(p.relative_to(STATIC)): hashlib.sha256(p.read_bytes()).hexdigest()[:10]
            for p in STATIC.rglob("*")
            if p.is_file()
        }
        self.env.globals.update(
            site=self.site,
            APPLIANCES=APPLIANCES,
            CATEGORIES=CATEGORIES,
            asset=lambda rel: f"/static/{rel}?v={h.get(rel, '0')}",
        )

    def robots(self, meta: Meta) -> str:
        if not self.site.indexable:
            return "noindex, nofollow"
        return "index, follow" if meta.index else "noindex, follow"

    def render(self, tpl, meta, **ctx):
        return self.env.get_template(tpl).render(meta=meta, robots=self.robots(meta), **ctx)

    def crumbs_ld(self, crumbs):
        return {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "name": n, "item": self.site.abs(p)}
                for i, (n, p) in enumerate(crumbs)
            ],
        }

    def items_ld(self, recipes):
        return {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "url": self.site.abs(r.url)} for i, r in enumerate(recipes)
            ],
        }

    def recipe_ld(self, r: Recipe):
        ld = {
            "@context": "https://schema.org",
            "@type": "Recipe",
            "name": r.title,
            "description": r.intro,
            "url": self.site.abs(r.url),
            "recipeCategory": r.appliance_label,
            "recipeYield": f"{r.servings} порц.",
            "recipeIngredient": [f"{i['name']}, {i['amount']}" for i in r.ingredients],
            "recipeInstructions": [
                {
                    "@type": "HowToStep",
                    "position": n + 1,
                    "text": s["text"],
                    "url": self.site.abs(r.url) + f"#shag-{n + 1}",
                }
                for n, s in enumerate(r.steps)
            ],
            "tool": [r.appliance_label],
            "datePublished": r.published_at,
        }
        if r.total:
            ld["totalTime"] = iso(r.total)
        return ld

    def route(self, path: str, q: dict):
        s = self.site
        if path == "/":
            meta = Meta(
                f"{s.cfg['name']} — рецепты для мультиварки и аэрогриля",
                "Выберите прибор: рецепты с режимами, температурой и временем ровно из источника рецепта.",
                s.abs("/"),
                True,
                kind="home",
            )
            return 200, self.render("home.html", meta), {}
        m = re.fullmatch(r"/pribor/([a-z]+)/(?:([a-z]+)/)?", path)
        if m and m.group(1) in APPLIANCES:
            a = m.group(1)
            label, desc = APPLIANCES[a]
            if m.group(2):
                cats = s.categories(a)
                if m.group(2) not in cats:
                    return self.not_found()
                c = m.group(2)
                items = cats[c]
                crumbs = [("Главная", "/"), (label, f"/pribor/{a}/"), (CATEGORIES[c], path)]
                meta = Meta(
                    f"{label}: {CATEGORIES[c].lower()}",
                    f"Рецепты для прибора «{label}», главный продукт — {CATEGORIES[c].lower()}.",
                    s.abs(path),
                    True,
                    crumbs,
                    [self.crumbs_ld(crumbs), self.items_ld(items)],
                    "category",
                )
                return 200, self.render("listing.html", meta, heading=meta.title, items=items, appliance=a), {}
            items = s.for_appliance(a)
            crumbs = [("Главная", "/"), (label, path)]
            meta = Meta(
                f"Рецепты для прибора: {label.lower()}",
                desc,
                s.abs(path),
                True,
                crumbs,
                [self.crumbs_ld(crumbs), self.items_ld(items)],
                "appliance",
            )
            return 200, self.render("appliance.html", meta, a=a, items=items), {}
        m = re.fullmatch(r"/recept/([a-z0-9-]+)/", path)
        if m and m.group(1) in s.by_slug:
            r = s.by_slug[m.group(1)]
            crumbs = [("Главная", "/"), (r.appliance_label, f"/pribor/{r.appliance}/"), (r.title, r.url)]
            meta = Meta(
                r.seo_title,
                r.seo_description,
                s.abs(r.url),
                True,
                crumbs,
                [self.recipe_ld(r), self.crumbs_ld(crumbs)],
                "recipe",
            )
            return 200, self.render("recipe.html", meta, r=r), {}
        m = re.fullmatch(r"/rezhim/([a-z0-9-]+)/", path)
        if m and m.group(1) in s.modes():
            e = s.modes()[m.group(1)]
            label = APPLIANCES[e["appliance"]][0]
            crumbs = [("Главная", "/"), (label, f"/pribor/{e['appliance']}/"), (f"Режим «{e['name']}»", path)]
            meta = Meta(
                f"{label}: режим «{e['name']}»",
                f"Рецепты, где используется режим «{e['name']}», с временем каждого рецепта.",
                s.abs(path),
                True,
                crumbs,
                [self.crumbs_ld(crumbs), self.items_ld(e["recipes"])],
                "mode",
            )
            return 200, self.render("mode.html", meta, e=e), {}
        if path == "/kak-chitat-rezhimy/":
            crumbs = [("Главная", "/"), ("Как читать режимы", path)]
            meta = Meta(
                "Как читать режимы и температуры в рецептах для техники",
                "Почему параметры прибора относятся к одному рецепту и как их проверять для своей модели.",
                s.abs(path),
                True,
                crumbs,
                [self.crumbs_ld(crumbs)],
                "article",
            )
            return 200, self.render("article.html", meta), {}
        if path == "/poisk/":
            qq = (q.get("q") or [""])[0].strip()[:120]
            meta = Meta(
                f"Поиск: {qq}" if qq else "Поиск рецептов для техники",
                "Поиск по блюду, продукту и режиму.",
                None,
                False,
                kind="search",
            )
            return 200, self.render("search.html", meta, q=qq, items=s.search(qq) if qq else []), {}
        if path == "/robots.txt":
            return (
                200,
                (
                    "User-agent: *\nDisallow: /\n"
                    if not s.indexable
                    else f"User-agent: *\nDisallow: /poisk/\nSitemap: {s.abs('/sitemap.xml')}\n"
                ),
                {"Content-Type": "text/plain; charset=utf-8"},
            )
        if path == "/sitemap.xml":
            return 200, self.sitemap(), {"Content-Type": "application/xml; charset=utf-8"}
        if path == "/healthz":
            return (
                200,
                json.dumps({"site_id": s.cfg["site_id"], "recipes": len(s.recipes)}),
                {"Content-Type": "application/json"},
            )
        return self.not_found()

    def sitemap_urls(self):
        s = self.site
        urls = ["/", "/kak-chitat-rezhimy/"]
        for a in APPLIANCES:
            if s.for_appliance(a):
                urls.append(f"/pribor/{a}/")
                urls += [f"/pribor/{a}/{c}/" for c in s.categories(a)]
        urls += [f"/rezhim/{k}/" for k in s.modes()]
        urls += [r.url for r in s.recipes]
        return urls

    def sitemap(self):
        rows = "\n".join(f"<url><loc>{self.site.abs(p)}</loc></url>" for p in self.sitemap_urls())
        return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{rows}\n</urlset>\n'

    def not_found(self):
        return (
            404,
            self.render("404.html", Meta("Страница не найдена", "Такой страницы нет.", None, False, kind="404")),
            {},
        )


def make_handler(app: App):
    class H(http_server.BaseHTTPRequestHandler):
        server_version = "food-appliances"
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
                }.get(p.suffix, "application/octet-stream")
                return self.send(
                    200, p.read_bytes(), {"Content-Type": ct, "Cache-Control": "public, max-age=31536000, immutable"}
                )
            if u.path not in ("/", "/healthz") and not u.path.endswith("/") and "." not in u.path.rsplit("/", 1)[-1]:
                return self.send(301, "", {"Location": u.path + "/" + (f"?{u.query}" if u.query else "")})
            try:
                self.send(*app.route(u.path, urllib.parse.parse_qs(u.query)))
            except Exception:
                import traceback

                traceback.print_exc()
                self.send(500, "Внутренняя ошибка", {"Content-Type": "text/plain; charset=utf-8"})

    return H


class Server(socketserver.ThreadingMixIn, http_server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main() -> int:
    app = App()
    bind, port = app.site.cfg["server"]["bind"], app.site.cfg["server"]["port"]
    if bind != "127.0.0.1":
        raise SystemExit("preview слушает только петлю")
    print(json.dumps({"listening": f"http://{bind}:{port}/", "recipes": len(app.site.recipes)}), flush=True)
    Server((bind, port), make_handler(app)).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
