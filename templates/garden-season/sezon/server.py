"""SSR-сервер garden-season (вариант month-calendar)."""

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

from sezon.content import CROPS, MONTH_SLUG, MONTHS_RU, REGIONS, TYPES
from sezon.site import REGION_NOTE, SOURCE_KIND, Site, Work

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"
HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; "
    "frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
}
MONTHS_GEN = [
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
]
MONTHS_PREP = [
    "январе",
    "феврале",
    "марте",
    "апреле",
    "мае",
    "июне",
    "июле",
    "августе",
    "сентябре",
    "октябре",
    "ноябре",
    "декабре",
]


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
            REGIONS=REGIONS,
            TYPES=TYPES,
            CROPS=CROPS,
            MONTHS=MONTHS_RU,
            MONTH_SLUG=MONTH_SLUG,
            MONTHS_PREP=MONTHS_PREP,
            REGION_NOTE=REGION_NOTE,
            SOURCE_KIND=SOURCE_KIND,
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

    def items_ld(self, items: list[Work]):
        return {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "url": self.site.abs(w.url), "name": w.title}
                for i, w in enumerate(items)
            ],
        }

    def howto_ld(self, w: Work):
        return {
            "@context": "https://schema.org",
            "@type": "HowTo",
            "name": w.title,
            "description": w.summary,
            "step": [
                {
                    "@type": "HowToStep",
                    "position": i + 1,
                    "text": x["text"],
                    "url": self.site.abs(f"{w.url}#shag-{i + 1}"),
                }
                for i, x in enumerate(w.steps)
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
                "Дача по сезону — календарь работ с регионом для каждого срока",
                "Сезонные работы в саду и огороде по месяцам. У каждого срока указан регион источника — "
                "сроки одного региона не выдаются за общие.",
                "/",
                [],
                [{"@context": "https://schema.org", "@type": "WebSite", "name": s.cfg["name"], "url": s.abs("/")}],
                "home",
            )
        if path == "/kalendar/":
            region = (q.get("region") or [""])[0]
            typ = (q.get("tip") or [""])[0]
            bad = [x for x, reg in ((region, REGIONS), (typ, TYPES)) if x and x not in reg]
            region = region if region in REGIONS else ""
            typ = typ if typ in TYPES else ""
            filtered = bool(region or typ or bad)
            crumbs = [home, ("Календарь", path)]
            grid = {m: s.in_month(m, region or None, typ or None) for m in range(1, 13)}
            meta = Meta(
                "Календарь работ на год"
                + (f": {REGIONS[region]}" if region else "")
                + (f", {TYPES[typ].lower()}" if typ else ""),
                "Работы по месяцам с фильтром по региону и типу работ.",
                None if filtered else s.abs(path),
                not filtered,
                crumbs,
                [self.crumbs_ld(crumbs)],
                "calendar",
            )
            return 200, self.render("calendar.html", meta, grid=grid, region=region, typ=typ, bad=bad), {}
        m = re.fullmatch(r"/kalendar/([a-z]+)/", path)
        if m and s.month_of(m.group(1)):
            mo = s.month_of(m.group(1))
            groups = s.by_region_in_month(mo)
            crumbs = [home, ("Календарь", "/kalendar/"), (MONTHS_RU[mo - 1].capitalize(), path)]
            items = s.in_month(mo)
            meta = Meta(
                f"Работы на даче в {MONTHS_PREP[mo - 1]}: по регионам",
                f"Что делать в саду и огороде в {MONTHS_PREP[mo - 1]} — с регионом каждого срока.",
                s.abs(path) if items else None,
                bool(items),
                crumbs,
                [self.crumbs_ld(crumbs), self.items_ld(items)],
                "month",
            )
            return 200, self.render("month.html", meta, mo=mo, groups=groups, osu=s.osu_by_month.get(mo)), {}
        if path == "/kultury/":
            crumbs = [home, ("Культуры", path)]
            return self.page(
                "crops.html",
                "Культуры: сроки работ по регионам",
                "Чеснок, картофель, томаты, ягодники и яблони.",
                path,
                crumbs,
            )
        m = re.fullmatch(r"/kultura/([a-z]+)/", path)
        if m and m.group(1) in s.crops():
            c = m.group(1)
            crumbs = [home, ("Культуры", "/kultury/"), (CROPS[c], path)]
            return self.page(
                "crop.html",
                f"{CROPS[c]}: когда что делать — по регионам",
                f"Сроки работ с культурой «{CROPS[c].lower()}» по месяцам; у каждого срока — регион источника.",
                path,
                crumbs,
                [self.items_ld(s.for_crop(c))],
                "crop",
                crop=c,
                cgrid=s.crop_grid(c),
            )
        m = re.fullmatch(r"/rabota/([a-z0-9-]+)/", path)
        if m and m.group(1) in s.by_slug:
            w = s.by_slug[m.group(1)]
            crumbs = [
                home,
                (w.crop_label or w.type_label, f"/kultura/{w.crop}/" if w.crop else f"/tip/{w.type}/"),
                (w.title, w.url),
            ]
            return self.page("work.html", w.title, w.summary, w.url, crumbs, [self.howto_ld(w)], "work", w=w)
        if path == "/regiony/":
            crumbs = [home, ("Регионы", path)]
            return self.page(
                "regions.html",
                "Регионы источников: откуда берутся сроки",
                "Каждый срок привязан к региону источника. Здесь — что значит каждый регион.",
                path,
                crumbs,
            )
        m = re.fullmatch(r"/region/([a-z-]+)/", path)
        if m and m.group(1) in REGIONS and s.for_region(m.group(1)):
            r = m.group(1)
            items = s.for_region(r)
            crumbs = [home, ("Регионы", "/regiony/"), (REGIONS[r], path)]
            return self.page(
                "region.html",
                f"{REGIONS[r]}: сезонные работы",
                REGION_NOTE[r],
                path,
                crumbs,
                [self.items_ld(items)],
                "region",
                r=r,
                items=items,
            )
        m = re.fullmatch(r"/tip/([a-z]+)/", path)
        if m and m.group(1) in TYPES and s.for_type(m.group(1)):
            t = m.group(1)
            items = s.for_type(t)
            crumbs = [home, (TYPES[t], path)]
            return self.page(
                "type.html",
                f"{TYPES[t]}: работы по месяцам",
                f"Работы типа «{TYPES[t].lower()}» с регионом каждого срока.",
                path,
                crumbs,
                [self.items_ld(items)],
                "type",
                t=t,
                items=items,
            )
        if path == "/podborki/":
            crumbs = [home, ("Подборки", path)]
            return self.page(
                "collections.html",
                "Подборки сезонных работ",
                "Осень, весна, ягодники и подготовка к зиме.",
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
        if path == "/kak-chitat-sroki/":
            crumbs = [home, ("Как читать сроки", path)]
            return self.page(
                "about.html",
                "Как читать сроки: почему у каждого срока есть регион",
                "Откуда берутся сроки, что значит регион и как перенести их на свой участок.",
                path,
                crumbs,
            )
        if path == "/istochniki/":
            crumbs = [home, ("Источники", path)]
            return self.page(
                "sources.html",
                "Источники сроков: OSU Extension и RHS",
                "Университетский календарь работ и руководства садоводческой организации.",
                path,
                crumbs,
            )
        if path == "/poisk/":
            qq = (q.get("q") or [""])[0].strip()[:120]
            meta = Meta(
                f"Поиск: {qq}" if qq else "Поиск по работам",
                "Поиск по культуре, работе и месяцу.",
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
                json.dumps({"site_id": s.cfg["site_id"], "variant": s.cfg["variant_id"], "works": len(s.works)}),
                {"Content-Type": "application/json"},
            )
        return self.not_found()

    def sitemap_urls(self):
        s = self.site
        urls = ["/", "/kalendar/", "/kultury/", "/regiony/", "/podborki/", "/kak-chitat-sroki/", "/istochniki/"]
        urls += [f"/kalendar/{MONTH_SLUG[m - 1]}/" for m in range(1, 13) if s.in_month(m)]
        urls += [f"/kultura/{c}/" for c in s.crops()]
        urls += [f"/region/{r}/" for r in REGIONS if s.for_region(r)]
        urls += [f"/tip/{t}/" for t in TYPES if s.for_type(t)]
        urls += [f"/podborki/{c}/" for c in s.collections]
        urls += [w.url for w in s.works]
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
        server_version = "garden-season"
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
    print(json.dumps({"listening": f"http://{bind}:{port}/", "works": len(app.site.works)}), flush=True)
    Server((bind, port), make_handler(app)).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
