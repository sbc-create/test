"""SSR-сервер games-survival (вариант inventory-first)."""

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

from craft.plan import MAX_N, plan, recipe_inputs, uses
from craft.site import Entry, Site

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
    """Описание для meta: целые предложения до limit символов; если первое длиннее — по слову с «…»."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = max(text.rfind(". ", 0, limit), text.rfind("; ", 0, limit))
    if cut >= limit // 3:
        return text[: cut + 1].rstrip(";") + ("" if text[cut] == "." else ".")
    return text[: text.rfind(" ", 0, limit - 1)].rstrip(",;:—– ") + "…"


def section_description(site: Site, gid: str, label: str, n: int) -> str:
    game = site.games[gid]
    cur = site.version.src.get("java_current") if site.version else None
    ver = f", версия Java Edition {cur}" if cur else ""
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
        self.env.globals.update(
            app=self,
            site=self.site,
            plural=plural,
            asset=lambda rel: f"/static/{rel}?v={h.get(rel, '0')}",
            recipe_inputs=lambda e: recipe_inputs(self.site, e),
            uses=lambda e: uses(self.site, e),
            MAX_N=MAX_N,
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
                "База выживания — планировщик крафта и ресурсы по сетке источника",
                "Выберите, что сделать, и сколько: шаги крафта и базовые ресурсы считаются по сетке крафта источника, с версией игры.",
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
                f"{s.games[gid]['title']}: ресурсы, крафт, биомы",
                f"Справочник по {s.games[gid]['title']}, Java Edition {s.version.src['java_current']}: "
                + ", ".join(f"{label.lower()} — {len(items)}" for label, items in s.sections(gid).values())
                + ". Рецепты и связи «из чего → во что».",
                path,
                crumbs,
                [],
                "game",
                gid=gid,
            )
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
        if path == "/iz-togo-chto-est/":
            return self.inventory(q)
        if path == "/planirovshchik/":
            return self.planner(q)
        if path == "/kak-my-rabotaem/":
            crumbs = [home, ("Как мы работаем", path)]
            return self.page(
                "about.html",
                "Как мы работаем: версия игры, рецепты и связи",
                "Откуда рецепты и как строятся связи между материалами.",
                path,
                crumbs,
            )
        if path == "/istochniki/":
            crumbs = [home, ("Источники", path)]
            return self.page(
                "sources.html",
                "Источники материалов",
                "Страницы вики, по которым составлены материалы, с датой чтения каждой.",
                path,
                crumbs,
            )
        if path == "/poisk/":
            qq = (q.get("q") or [""])[0].strip()[:120]
            meta = Meta(
                f"Поиск: {qq}" if qq else "Поиск по справочнику",
                "Поиск по предметам, ресурсам и биомам.",
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
        urls = ["/", "/iz-togo-chto-est/", "/planirovshchik/", "/kak-my-rabotaem/", "/istochniki/"]
        for gid in s.games:
            secs = s.sections(gid)
            if secs:
                urls.append(f"/{gid}/")
                urls += [f"/{gid}/{sec}/" for sec in secs]
        urls += [e.url for e in s.entries]
        return urls

    def targets(self) -> list[Entry]:
        return [e for e in self.site.entries if e.type in ("item", "building") and recipe_inputs(self.site, e)]

    def planner(self, q: dict):
        """Без параметров — индексируемая страница выбора; с параметрами — расчёт (noindex, без canonical)."""
        slug = (q.get("item") or [""])[0]
        raw = (q.get("n") or [""])[0].strip()
        crumbs = [("Главная", "/"), ("Планировщик", "/planirovshchik/")]
        targets = self.targets()
        if not slug and not raw:
            return self.page(
                "planner.html",
                "Планировщик крафта: сколько нужно ресурсов",
                "Выберите предмет и количество — получите шаги крафта и базовые ресурсы по сетке источника.",
                "/planirovshchik/",
                crumbs,
                kind="planner",
                targets=targets,
                p=None,
                error=None,
                slug="",
                n=1,
            )
        e = self.site.by_slug.get(slug)
        error = None
        if e not in targets:
            error = "Выберите предмет из списка."
        n = int(raw) if raw.isdigit() else 0
        if not error and not 1 <= n <= MAX_N:
            error = f"Количество — целое число от 1 до {MAX_N}."
        p = plan(self.site, e, n) if not error else None
        title = f"План: {e.title.split(':')[0]} × {n}" if p else "Планировщик: проверьте ввод"
        meta = Meta(title, "Расчёт по сетке источника.", None, False, crumbs, [], "planner")
        body = self.render(
            "planner.html", meta, targets=targets, p=p, error=error, slug=slug, n=n if p else (raw[:4] or 1)
        )
        return (200 if p else 400), body, {}

    def inventory_options(self):
        from craft.inventory import options

        return options(self.site)

    def inventory(self, q: dict):
        """Без выбора — индексируемая форма; с выбором — noindex без canonical; только неизвестные материалы — 400."""
        from craft.inventory import craftable, options

        s = self.site
        raw = [x for x in q.get("est", []) if x][:60]
        opts = options(s)
        known = {e.slug for e in opts}
        have = [x for x in dict.fromkeys(raw) if x in known]
        crumbs = [("Главная", "/"), ("Из того, что есть", "/iz-togo-chto-est/")]
        error = "Таких материалов на сайте нет — отметьте из списка." if raw and not have else None
        now, almost = craftable(s, set(have)) if have else ([], [])
        meta = Meta(
            f"Из того, что есть: {len(have)} {plural(len(have), 'материал', 'материала', 'материалов')}"
            if have
            else "Что сделать из того, что есть",
            "Отметьте, что есть в инвентаре, — покажем, что можно сделать сейчас и чего не хватает, по сетке крафта источника.",
            None if raw else s.abs("/iz-togo-chto-est/"),
            not raw,
            crumbs,
            [self.crumbs_ld(crumbs)],
            "inventory",
        )
        body = self.render(
            "inventory.html", meta, opts=opts, have=have, now=now, almost=almost, error=error, asked=bool(raw)
        )
        return (400 if error else 200), body, {}

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
        server_version = "games-survival"
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
