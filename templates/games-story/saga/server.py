"""SSR-сервер games-story (вариант chapter-guides)."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import socketserver
import urllib.parse
from dataclasses import dataclass, field
from http import server as http_server
from pathlib import Path

import jinja2

from saga.site import Guide, Site

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"
HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; "
    "frame-src https://www.youtube-nocookie.com; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
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


SNIPPET_MAX = 160  # длиннее поисковики обрезают посреди фразы


def snippet(text: str, limit: int = SNIPPET_MAX) -> str:
    """Описание для meta: целые предложения до limit символов; иначе — по запятой или тире, в крайнем случае по слову, с «…»."""
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
        self.env.globals.update(site=self.site, plural=plural, asset=lambda rel: f"/static/{rel}?v={h.get(rel, '0')}")

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

    def items_ld(self, items: list[Guide]):
        return {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "url": self.site.abs(g.url), "name": g.title}
                for i, g in enumerate(items)
            ],
        }

    def video_ld(self, v: dict):
        return {
            "@context": "https://schema.org",
            "@type": "VideoObject",
            "name": v["name"],
            "embedUrl": f"https://www.youtube-nocookie.com/embed/{v['video_id']}",
            "url": v["url"],
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
                "Сюжет пройден — гайды по главам, маршруты и коллекционные предметы",
                "Прохождение сюжетных игр по главам: маршрут, новые механики, коллекционные предметы и проверенные видео.",
                "/",
                [],
                [{"@context": "https://schema.org", "@type": "WebSite", "name": s.cfg["name"], "url": s.abs("/")}],
                "home",
            )
        m = re.fullmatch(r"/igra/([a-z0-9-]+)/", path)
        if m and m.group(1) in s.games and s.for_game(m.group(1)):
            gid = m.group(1)
            gs = s.for_game(gid)
            crumbs = [home, (s.games[gid]["title"], path)]
            return self.page(
                "game.html",
                f"{s.games[gid]['title']}: все главы, клубники и стороны",
                f"Гайд по {s.games[gid]['title']}: главы по порядку, участки маршрута, коллекционные предметы.",
                path,
                crumbs,
                [self.items_ld(gs)],
                "game",
                gid=gid,
                gs=gs,
            )
        m = re.fullmatch(r"/igra/([a-z0-9-]+)/(personazhi|mehaniki|gde-ya)/", path)
        if m and m.group(1) in s.games and s.for_game(m.group(1)):
            gid, kind = m.group(1), m.group(2)
            title = s.games[gid]["title"]
            label = {"personazhi": "Персонажи", "mehaniki": "Механики по главам", "gde-ya": "Где я? Чекпоинты"}[kind]
            crumbs = [home, (title, f"/igra/{gid}/"), (label, path)]
            q1 = (q.get("q") or [""])[0].strip()[:60]
            rows = s.checkpoints(gid)
            if kind == "gde-ya" and q1:
                ql = q1.lower()
                rows = [r for r in rows if ql in r["name"].lower() or ql in r["guide"].name.lower()]
            meta = Meta(
                f"{title}: {label.lower()}" + (f" — «{q1}»" if q1 else ""),
                {
                    "personazhi": "В каких главах появляется каждый персонаж — по инфобоксам вики.",
                    "mehaniki": (
                        f"Какая механика в какой главе {title} появляется: "
                        f"{len({m for m, _ in s.mechanics_index(gid)})} "
                        f"{plural(len({m for m, _ in s.mechanics_index(gid)}), 'механика', 'механики', 'механик')}"
                        " по страницам вики."
                    ),
                    "gde-ya": (
                        f"{len(s.checkpoints(gid))} {plural(len(s.checkpoints(gid)), 'чекпоинт', 'чекпоинта', 'чекпоинтов')}"
                        f" {title} по порядку глав: найдите свой — глава, номер и что дальше."
                    ),
                }[kind],
                None if q1 else s.abs(path),
                not q1,
                crumbs,
                [self.crumbs_ld(crumbs)],
                kind,
            )
            return 200, self.render(f"atlas_{kind.replace('-', '_')}.html", meta, gid=gid, rows=rows, q=q1), {}
        m = re.fullmatch(r"/igra/([a-z0-9-]+)/personazh/([a-z0-9-]+)/", path)
        if m and m.group(1) in s.games and m.group(2) in s.characters(m.group(1)):
            gid, slug = m.group(1), m.group(2)
            ch = s.characters(gid)[slug]
            title = s.games[gid]["title"]
            crumbs = [home, (title, f"/igra/{gid}/"), ("Персонажи", f"/igra/{gid}/personazhi/"), (ch["name"], path)]
            return self.page(
                "atlas_character.html",
                f"{ch['name']} в {title}: главы",
                f"Главы {title}, где появляется {ch['name']}, — по инфобоксам вики.",
                path,
                crumbs,
                [],
                "character",
                gid=gid,
                ch=ch,
            )
        m = re.fullmatch(r"/igra/([a-z0-9-]+)/kollekcii/", path)
        if m and m.group(1) in s.games:
            gid = m.group(1)
            crumbs = [home, (s.games[gid]["title"], f"/igra/{gid}/"), ("Коллекционные предметы", path)]
            return self.page(
                "collectibles.html",
                f"{s.games[gid]['title']}: коллекционные предметы по главам",
                "Сколько клубник в каждой главе и что открывают кристальные сердца.",
                path,
                crumbs,
                [],
                "collectibles",
                gid=gid,
            )
        m = re.fullmatch(r"/igra/([a-z0-9-]+)/([a-z0-9-]+)/", path)
        if m and m.group(2) in s.by_slug and s.by_slug[m.group(2)].game == m.group(1):
            g = s.by_slug[m.group(2)]
            crumbs = [home, (s.games[g.game]["title"], f"/igra/{g.game}/"), (g.title, g.url)]
            return self.page(
                "guide.html",
                f"{g.title} — гайд по {s.games[g.game]['title']}",
                snippet(g.summary),
                g.url,
                crumbs,
                [self.video_ld(v) for v in g.videos],
                "guide",
                g=g,
            )
        if path == "/video/":
            crumbs = [home, ("Видео", path)]
            return self.page(
                "videos.html",
                "Проверенные видео об играх",
                "Видео, проверенные через oEmbed: существуют, канал известен, встраивание разрешено.",
                path,
                crumbs,
                [self.video_ld(v) for v in s.videos],
                "videos",
            )
        if path == "/kak-my-rabotaem/":
            crumbs = [home, ("Как мы работаем", path)]
            return self.page(
                "about.html",
                "Как мы работаем: источники, версии игр и видео",
                "Откуда факты, как проверяются видео и кому принадлежит игра в сети.",
                path,
                crumbs,
            )
        if path == "/istochniki/":
            crumbs = [home, ("Источники", path)]
            return self.page(
                "sources.html",
                "Источники гайдов",
                "Страницы вики и проверенные видео, по которым составлены гайды, с датой чтения каждой страницы.",
                path,
                crumbs,
            )
        if path == "/poisk/":
            qq = (q.get("q") or [""])[0].strip()[:120]
            meta = Meta(
                f"Поиск: {qq}" if qq else "Поиск по гайдам",
                "Поиск по главам, механикам, участкам и персонажам.",
                None,
                False,
                kind="search",
            )
            return 200, self.render("search.html", meta, q=qq, items=s.search(qq) if qq else []), {}
        if path == "/robots.txt":
            body = (
                "User-agent: *\nDisallow: /\n"
                if not s.indexable
                else f"User-agent: *\nDisallow: /poisk/\nSitemap: {s.abs('/sitemap.xml')}\n"
            )
            return 200, body, {"Content-Type": "text/plain; charset=utf-8"}
        if path == "/sitemap.xml":
            return 200, self.sitemap(), {"Content-Type": "application/xml; charset=utf-8"}
        if path == "/healthz":
            return (
                200,
                json.dumps({"site_id": s.cfg["site_id"], "variant": s.cfg["variant_id"], "guides": len(s.guides)}),
                {"Content-Type": "application/json"},
            )
        return self.not_found()

    def sitemap_urls(self):
        s = self.site
        urls = ["/", "/video/", "/kak-my-rabotaem/", "/istochniki/"]
        for gid in s.games:
            if s.for_game(gid):
                urls += [f"/igra/{gid}/", f"/igra/{gid}/kollekcii/"]
                urls += [f"/igra/{gid}/{k}/" for k in ("personazhi", "mehaniki", "gde-ya")]
                urls += [f"/igra/{gid}/personazh/{c}/" for c in s.characters(gid)]
        urls += [g.url for g in s.guides]
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
        server_version = "games-story"
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


def main(argv=None) -> int:
    app = App()
    bind, port = app.site.cfg["server"]["bind"], app.site.cfg["server"]["port"]
    ap = argparse.ArgumentParser(prog="games-story serve")
    ap.add_argument("--port", type=int, help="другой локальный порт (чистая копия рядом с действующим превью)")
    port = ap.parse_args(argv).port or port
    if bind != "127.0.0.1":
        raise SystemExit("preview слушает только петлю")
    print(json.dumps({"listening": f"http://{bind}:{port}/", "guides": len(app.site.guides)}), flush=True)
    Server((bind, port), make_handler(app)).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
