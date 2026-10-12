"""SSR-сервер plants-home (вариант plant-catalog)."""

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

from flora.content import LIGHT, MAINT, PROBLEMS, TOPICS
from flora.site import Plant, Site

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


def plural(n: int, one: str, few: str, many: str) -> str:
    n = abs(n) % 100
    if 11 <= n <= 14:
        return many
    return one if n % 10 == 1 else few if 2 <= n % 10 <= 4 else many


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
            LIGHT=LIGHT,
            MAINT=MAINT,
            PROBLEMS=PROBLEMS,
            TOPICS=TOPICS,
            plural=plural,
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

    def items_ld(self, items: list[Plant]):
        return {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "url": self.site.abs(p.url), "name": p.ru_name}
                for i, p in enumerate(items)
            ],
        }

    def page(self, tpl, title, desc, path, crumbs, ld=(), kind="page", **ctx):
        meta = Meta(
            title, desc, self.site.abs(path), True, crumbs, [self.crumbs_ld(crumbs), *ld] if crumbs else list(ld), kind
        )
        return 200, self.render(tpl, meta, **ctx), {}

    def route(self, path: str, q: dict):
        s = self.site
        home = ("Главная", "/")
        if path == "/":
            return self.page(
                "home.html",
                "Домашние растения — условия и уход по конкретному виду",
                "Каталог комнатных растений: свет, полив, температура и проблемы — по университетскому справочнику "
                "для каждого вида отдельно.",
                "/",
                [],
                [{"@context": "https://schema.org", "@type": "WebSite", "name": s.cfg["name"], "url": s.abs("/")}],
                "home",
            )
        if path == "/katalog/":
            light = (q.get("svet") or [""])[0]
            maint = (q.get("uhod") or [""])[0]
            lights = s.lights()
            bad = [x for x, ok in ((light, light in lights), (maint, maint in MAINT)) if x and not ok]
            light = light if light in lights else ""
            maint = maint if maint in MAINT else ""
            filtered = bool(light or maint or bad)
            items = s.filter(light or None, maint or None)
            crumbs = [home, ("Каталог", path)]
            meta = Meta(
                "Каталог комнатных растений"
                + (f": {lights[light][1].lower()}" if light else "")
                + (f", уход {MAINT[maint]}" if maint else ""),
                "Все виды с фильтром по свету и сложности ухода.",
                None if filtered else s.abs(path),
                not filtered,
                crumbs,
                [self.crumbs_ld(crumbs), self.items_ld(items)],
                "catalog",
            )
            return (
                200,
                self.render("catalog.html", meta, items=items, light=light, maint=maint, bad=bad, lights=lights),
                {},
            )
        m = re.fullmatch(r"/rastenie/([a-z0-9-]+)/", path)
        if m and m.group(1) in s.by_slug:
            p = s.by_slug[m.group(1)]
            crumbs = [home, ("Каталог", "/katalog/"), (p.ru_name, p.url)]
            return self.page(
                "plant.html",
                f"{p.ru_name} ({p.sci}): свет, полив, проблемы",
                p.summary,
                p.url,
                crumbs,
                [],
                "plant",
                p=p,
            )
        if path == "/svet/":
            crumbs = [home, ("Освещение", path)]
            return self.page(
                "lights.html",
                "Освещение: какие растения для какого места",
                "Категории света по справочнику и виды для каждой.",
                path,
                crumbs,
            )
        m = re.fullmatch(r"/svet/([a-z]+)/", path)
        if m and m.group(1) in s.lights():
            lv = s.lights()[m.group(1)]
            items = s.with_light(m.group(1))
            crumbs = [home, ("Освещение", "/svet/"), (lv[1], path)]
            return self.page(
                "light.html",
                f"{lv[1]}: какие комнатные растения подойдут",
                f"{lv[1]} — {lv[2]}. Виды, которым это подходит по источнику.",
                path,
                crumbs,
                [self.items_ld(items)],
                "light",
                lv=lv,
                items=items,
            )
        if path == "/problemy/":
            crumbs = [home, ("Проблемы", path)]
            return self.page(
                "problems.html",
                "Проблемы комнатных растений: у каких видов что бывает",
                "Перелив, вредители, опадание листьев и бутонов — по видам.",
                path,
                crumbs,
            )
        m = re.fullmatch(r"/problema/([a-z-]+)/", path)
        if m and m.group(1) in s.problems():
            t = m.group(1)
            items = s.problems()[t]
            crumbs = [home, ("Проблемы", "/problemy/"), (PROBLEMS[t][0], path)]
            return self.page(
                "problem.html",
                f"{PROBLEMS[t][0]}: у каких растений и что делать",
                f"{PROBLEMS[t][0]} — что пишет справочник по каждому виду.",
                path,
                crumbs,
                [self.items_ld(items)],
                "problem",
                t=t,
                items=items,
            )
        if path == "/podborki/":
            crumbs = [home, ("Подборки", path)]
            return self.page(
                "collections.html",
                "Подборки комнатных растений",
                "Для тёмной комнаты, солнечного окна, неприхотливые, цветущие.",
                path,
                crumbs,
            )
        m = re.fullmatch(r"/podborki/([a-z0-9-]+)/", path)
        if m and m.group(1) in s.collections:
            c = s.collections[m.group(1)]
            crumbs = [home, ("Подборки", "/podborki/"), (c["title"], path)]
            return self.page(
                "collection.html", c["title"], c["lede"], path, crumbs, [self.items_ld(c["items"])], "collection", c=c
            )
        if path == "/kak-chitat/":
            crumbs = [home, ("Как читать карточки", path)]
            return self.page(
                "about.html",
                "Как читать карточки растений",
                "Откуда условия и почему они относятся к одному виду.",
                path,
                crumbs,
            )
        if path == "/istochniki/":
            crumbs = [home, ("Источники", path)]
            return self.page(
                "sources.html",
                "Источники: NC State Extension Plant Toolbox",
                "Страницы видов, по которым составлены карточки.",
                path,
                crumbs,
            )
        if path == "/poisk/":
            qq = (q.get("q") or [""])[0].strip()[:120]
            meta = Meta(
                f"Поиск: {qq}" if qq else "Поиск растений",
                "Поиск по названию, условиям и проблемам.",
                None,
                False,
                kind="search",
            )
            return 200, self.render("search.html", meta, q=qq, items=s.search(qq) if qq else []), {}
        if path == "/robots.txt":
            body = (
                "User-agent: *\nDisallow: /\n"
                if not s.indexable
                else f"User-agent: *\nDisallow: /poisk/\nDisallow: /*?\nSitemap: {s.abs('/sitemap.xml')}\n"
            )
            return 200, body, {"Content-Type": "text/plain; charset=utf-8"}
        if path == "/sitemap.xml":
            return 200, self.sitemap(), {"Content-Type": "application/xml; charset=utf-8"}
        if path == "/healthz":
            return (
                200,
                json.dumps({"site_id": s.cfg["site_id"], "variant": s.cfg["variant_id"], "plants": len(s.plants)}),
                {"Content-Type": "application/json"},
            )
        return self.not_found()

    def sitemap_urls(self):
        s = self.site
        urls = ["/", "/katalog/", "/svet/", "/problemy/", "/podborki/", "/kak-chitat/", "/istochniki/"]
        urls += [f"/svet/{x}/" for x in s.lights()]
        urls += [f"/problema/{t}/" for t in s.problems()]
        urls += [f"/podborki/{c}/" for c in s.collections]
        urls += [p.url for p in s.plants]
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
        server_version = "plants-home"
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
    print(json.dumps({"listening": f"http://{bind}:{port}/", "plants": len(app.site.plants)}), flush=True)
    Server((bind, port), make_handler(app)).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
