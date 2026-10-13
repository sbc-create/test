"""SSR-сервер games-rpg (вариант party-planner)."""

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

from quest.site import Entry, Site

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


def section_description(site: Site, gid: str, label: str, n: int) -> str:
    game = site.games[gid]
    ver = f", сверено с {site.version.src['name']}" if site.version else ""
    return f"{label} {game['title']}: {n} {plural(n, 'материал', 'материала', 'материалов')} по {game['wiki']}{ver}."


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

    def items_ld(self, items: list[Entry]):
        return {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "url": self.site.abs(e.url), "name": e.title}
                for i, e in enumerate(items)
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
                "Гайды RPG — персонажи, билды, квесты и механики с версией игры",
                "Справочник по ролевым играм: спутники, основы билдов по классам, квесты и механики — с указанием патча.",
                "/",
                [],
                [{"@context": "https://schema.org", "@type": "WebSite", "name": s.cfg["name"], "url": s.abs("/")}],
                "home",
            )
        m = re.fullmatch(r"/([a-z0-9-]+)/", path)
        if m and m.group(1) in s.games and s.sections(m.group(1)):
            gid = m.group(1)
            crumbs = [home, (s.games[gid]["title"], path)]
            return self.page(
                "game.html",
                f"{s.games[gid]['title']}: персонажи, билды, квесты, механики",
                f"Справочник по {s.games[gid]['title']} с указанием версии игры.",
                path,
                crumbs,
                [],
                "game",
                gid=gid,
            )
        if path == "/otryad/":
            gid = next(iter(s.games))
            slugs = [x for x in q.get("p", []) if x in {e.slug for e in s.characters(gid)}][:4]
            over = len(q.get("p", [])) > 4
            crumbs = [home, ("Отряд", path)]
            meta = Meta(
                "Планировщик отряда",
                "Соберите отряд до 4 спутников и сравните классы и характеристики по данным вики.",
                None if slugs else s.abs(path),
                not slugs,
                crumbs,
                [self.crumbs_ld(crumbs)],
                "party",
            )
            return 200, self.render("party.html", meta, gid=gid, party=s.party(gid, slugs), slugs=slugs, over=over), {}
        m = re.fullmatch(r"/([a-z0-9-]+)/personazhi/", path)
        if m and m.group(1) in s.games and s.characters(m.group(1)):
            gid = m.group(1)
            key = (q.get("sort") or [""])[0]
            key = key if key in ("STR", "DEX", "CON", "INT", "WIS", "CHA") else ""
            crumbs = [home, (s.games[gid]["title"], f"/{gid}/"), ("Персонажи", path)]
            items = s.sort_characters(gid, key)
            meta = Meta(
                f"{s.games[gid]['title']}: персонажи — сравнение характеристик",
                "Таблица спутников с характеристиками по данным вики.",
                None if key else s.abs(path),
                not key,
                crumbs,
                [self.crumbs_ld(crumbs), self.items_ld(items)],
                "chars",
            )
            return 200, self.render("characters.html", meta, gid=gid, items=items, key=key), {}
        m = re.fullmatch(r"/([a-z0-9-]+)/([a-z]+)/", path)
        if m and m.group(1) in s.games and m.group(2) in s.sections(m.group(1)):
            gid, sec = m.group(1), m.group(2)
            label, items = s.sections(gid)[sec]
            crumbs = [home, (s.games[gid]["title"], f"/{gid}/"), (label, path)]
            return self.page(
                "section.html",
                f"{s.games[gid]['title']}: {label.lower()}",
                section_description(s, gid, label, len(items)),
                path,
                crumbs,
                [self.items_ld(items)],
                "section",
                gid=gid,
                sec=sec,
                label=label,
                items=items,
            )
        m = re.fullmatch(r"/([a-z0-9-]+)/([a-z]+)/([a-z0-9-]+)/", path)
        if m and m.group(3) in s.by_slug and s.by_slug[m.group(3)].url == path:
            e = s.by_slug[m.group(3)]
            crumbs = [home, (s.games[e.game]["title"], f"/{e.game}/")]
            if e.type != "version":
                crumbs.append((s.sections(e.game)[e.section][0], f"/{e.game}/{e.section}/"))
            crumbs.append((e.title, e.url))
            return self.page(
                "entry.html",
                f"{e.title} — {s.games[e.game]['title']}",
                snippet(e.summary),
                e.url,
                crumbs,
                [],
                "entry",
                e=e,
            )
        if path == "/kak-my-rabotaem/":
            crumbs = [home, ("Как мы работаем", path)]
            return self.page(
                "about.html",
                "Как мы работаем: версия игры, источники и билды",
                "Почему у материала есть патч и чего мы не пишем.",
                path,
                crumbs,
            )
        if path == "/istochniki/":
            crumbs = [home, ("Источники", path)]
            return self.page(
                "sources.html", "Источники материалов", "Страницы вики, по которым составлены материалы.", path, crumbs
            )
        if path == "/poisk/":
            qq = (q.get("q") or [""])[0].strip()[:120]
            meta = Meta(
                f"Поиск: {qq}" if qq else "Поиск по справочнику",
                "Поиск по персонажам, классам, квестам и механикам.",
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
                json.dumps({"site_id": s.cfg["site_id"], "variant": s.cfg["variant_id"], "entries": len(s.entries)}),
                {"Content-Type": "application/json"},
            )
        return self.not_found()

    def sitemap_urls(self):
        s = self.site
        urls = ["/", "/otryad/", "/kak-my-rabotaem/", "/istochniki/"]
        for gid in s.games:
            secs = s.sections(gid)
            if secs:
                urls.append(f"/{gid}/")
                urls += [f"/{gid}/{sec}/" for sec in secs]
        urls += [e.url for e in s.entries]
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
        server_version = "games-rpg"
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
    print(json.dumps({"listening": f"http://{bind}:{port}/", "entries": len(app.site.entries)}), flush=True)
    Server((bind, port), make_handler(app)).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
