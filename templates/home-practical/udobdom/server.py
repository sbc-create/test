"""SSR-сервер home-practical (вариант rooms-cards)."""

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

from udobdom.content import ROOMS, TAGS, TASKS
from udobdom.site import ROOM_LEDE, SOURCE_KIND, Material, Site

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"
HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; "
    "frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
}


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
            ROOMS=ROOMS,
            TASKS=TASKS,
            TAGS=TAGS,
            ROOM_LEDE=ROOM_LEDE,
            SOURCE_KIND=SOURCE_KIND,
            asset=lambda rel: f"/static/{rel}?v={h.get(rel, '0')}",
            plural=plural,
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

    def items_ld(self, items: list[Material]):
        return {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "url": self.site.abs(m.url), "name": m.title}
                for i, m in enumerate(items)
            ],
        }

    def howto_ld(self, m: Material):
        """HowTo строго по видимому: название, описание, что потребуется, шаги. Без автора, рейтинга, цены, времени."""
        return {
            "@context": "https://schema.org",
            "@type": "HowTo",
            "name": m.title,
            "description": m.summary,
            "supply": [{"@type": "HowToSupply", "name": x["text"]} for x in m.need],
            "step": [
                {
                    "@type": "HowToStep",
                    "position": i + 1,
                    "text": x["text"],
                    "url": self.site.abs(f"{m.url}#shag-{i + 1}"),
                }
                for i, x in enumerate(m.steps)
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
                "Удобный дом — хранение, мебель и небольшие улучшения по комнатам",
                "Пошаговые инструкции по хранению и мебели для кухни, прихожей, спальни, гостиной, ванной и рабочего места "
                "с размерами и требованиями производителей.",
                "/",
                [],
                [{"@context": "https://schema.org", "@type": "WebSite", "name": s.cfg["name"], "url": s.abs("/")}],
                "home",
            )
        if path == "/obhod/plan/":
            return self.audit_plan(q)
        m = re.fullmatch(r"/obhod/([a-z-]+)/", path)
        if m and m.group(1) in self.audit_rooms():
            return self.audit_room(m.group(1), q)
        if path == "/pomeshcheniya/":
            crumbs = [home, ("Помещения", path)]
            return self.page(
                "rooms.html",
                "Помещения: что улучшить в каждой комнате",
                "Выберите помещение — кухню, прихожую, спальню, гостиную, ванную или рабочее место.",
                path,
                crumbs,
            )
        m = re.fullmatch(r"/pomeshcheniya/([a-z-]+)/", path)
        if m and m.group(1) in ROOMS and s.in_room(m.group(1)):
            r = m.group(1)
            items = s.in_room(r)
            crumbs = [home, ("Помещения", "/pomeshcheniya/"), (ROOMS[r], path)]
            return self.page(
                "room.html",
                f"{ROOMS[r]}: хранение, мебель и улучшения",
                f"{ROOM_LEDE[r]} Инструкции с размерами и требованиями производителей.",
                path,
                crumbs,
                [self.items_ld(items)],
                "room",
                room=r,
                items=items,
            )
        if path == "/zadachi/":
            room = (q.get("pomeshchenie") or [""])[0]
            task = (q.get("zadacha") or [""])[0]
            bad = [x for x, reg in ((room, ROOMS), (task, TASKS)) if x and x not in reg]
            room = room if room in ROOMS else ""
            task = task if task in TASKS else ""
            items = s.filter(room or None, task or None)
            crumbs = [home, ("Каталог задач", path)]
            filtered = bool(room or task or bad)
            meta = Meta(
                "Каталог задач по дому"
                + (f": {ROOMS[room].lower()}" if room else "")
                + (f", {TASKS[task].lower()}" if task else ""),
                with_examples(
                    f"Все {len(s.materials)} инструкций с фильтром по помещению и задаче",
                    [v.lower() for k, v in TASKS.items() if s.for_task(k)],
                ),
                None if filtered else s.abs(path),
                not filtered,
                crumbs,
                [self.crumbs_ld(crumbs), self.items_ld(items)],
                "catalog",
            )
            return 200, self.render("catalog.html", meta, items=items, room=room, task=task, bad=bad), {}
        m = re.fullmatch(r"/zadachi/([a-z-]+)/", path)
        if m and m.group(1) in TASKS and s.for_task(m.group(1)):
            t = m.group(1)
            items = s.for_task(t)
            crumbs = [home, ("Каталог задач", "/zadachi/"), (TASKS[t], path)]
            return self.page(
                "task.html",
                f"{TASKS[t]}: инструкции для всех помещений",
                with_examples(
                    f"{TASKS[t]} — {len(items)} {plural(len(items), 'инструкция', 'инструкции', 'инструкций')}",
                    [m.title for m in items],
                ),
                path,
                crumbs,
                [self.items_ld(items)],
                "task",
                task=t,
                items=items,
            )
        m = re.fullmatch(r"/instrukciya/([a-z0-9-]+)/", path)
        if m and m.group(1) in s.by_slug:
            mt = s.by_slug[m.group(1)]
            crumbs = [home, (mt.room_label, f"/pomeshcheniya/{mt.room}/"), (mt.title, mt.url)]
            return self.page(
                "material.html", mt.title, snippet(mt.summary), mt.url, crumbs, [self.howto_ld(mt)], "material", mt=mt
            )
        if path == "/problemy/":  # перенесено из варианта B
            crumbs = [home, ("Что мешает дома", path)]
            return self.page(
                "problems.html",
                "Что мешает дома: выберите проблему",
                "Начните с того, что не так, — и получите инструкции по порядку с чек-листами.",
                path,
                crumbs,
                kind="problems",
            )
        m = re.fullmatch(r"/problemy/([a-z0-9-]+)/", path)
        if m and m.group(1) in s.problems:
            pr = s.problems[m.group(1)]
            crumbs = [home, ("Что мешает дома", "/problemy/"), (pr["title"], path)]
            return self.page(
                "problem.html",
                pr["title"],
                pr["symptom"] + " Инструкции по порядку с чек-листами.",
                path,
                crumbs,
                [self.items_ld(pr["items"])],
                "problem",
                pr=pr,
            )
        if path == "/podborki/":
            crumbs = [home, ("Подборки", path)]
            return self.page(
                "collections.html",
                "Подборки: крепление, ящики, обувь, без дрели",
                with_examples("Инструкции, собранные по общей задаче", [c["title"] for c in s.collections.values()]),
                path,
                crumbs,
            )
        m = re.fullmatch(r"/podborki/([a-z0-9-]+)/", path)
        if m and m.group(1) in s.collections:
            c = s.collections[m.group(1)]
            crumbs = [home, ("Подборки", "/podborki/"), (c["title"], path)]
            return self.page(
                "collection.html",
                c["title"],
                c["lede"]
                if len(c["lede"]) >= 50
                else with_examples(c["lede"].rstrip("."), [m.title for m in c["items"]]),
                path,
                crumbs,
                [self.items_ld(c["items"])],
                "collection",
                c=c,
            )
        m = re.fullmatch(r"/teg/([a-z0-9-]+)/", path)
        if m and m.group(1) in s.tags():
            t = m.group(1)
            items = s.tags()[t]
            crumbs = [home, (f"Тег: {TAGS[t]}", path)]
            return self.page(
                "tag.html",
                f"{TAGS[t]} — инструкции",
                with_examples(
                    f"«{TAGS[t]}» — {len(items)} {plural(len(items), 'инструкция', 'инструкции', 'инструкций')}",
                    [m.title for m in items],
                ),
                path,
                crumbs,
                [self.items_ld(items)],
                "tag",
                tag=t,
                items=items,
            )
        if path == "/istochniki/":
            crumbs = [home, ("Источники", path)]
            return self.page(
                "sources.html",
                "Источники: производители и профильные организации",
                "Откуда взяты размеры, нагрузки и требования в инструкциях.",
                path,
                crumbs,
            )
        if path == "/kak-my-proveryaem/":
            crumbs = [home, ("Как мы проверяем", path)]
            return self.page(
                "about.html",
                "Как мы проверяем инструкции",
                "Чем требование производителя отличается от редакционного совета и откуда берутся числа.",
                path,
                crumbs,
            )
        if path == "/poisk/":
            qq = (q.get("q") or [""])[0].strip()[:120]
            meta = Meta(
                f"Поиск: {qq}" if qq else "Поиск по инструкциям",
                "Поиск по помещению, задаче и предмету.",
                None,
                False,
                kind="search",
            )
            return 200, self.render("search.html", meta, q=qq, items=s.search(qq) if qq else []), {}
        if path == "/sohranennoe/":
            meta = Meta(
                "Сохранённые инструкции",
                "Инструкции, которые вы сохранили на этом устройстве.",
                None,
                False,
                kind="saved",
            )
            return 200, self.render("saved.html", meta), {}
        if path == "/robots.txt":
            body = (
                "User-agent: *\nDisallow: /\n"
                if not s.indexable
                else f"User-agent: *\nDisallow: /poisk/\nDisallow: /sohranennoe/\nDisallow: /*?\nSitemap: {s.abs('/sitemap.xml')}\n"
            )
            return 200, body, {"Content-Type": "text/plain; charset=utf-8"}
        if path == "/sitemap.xml":
            return 200, self.sitemap(), {"Content-Type": "application/xml; charset=utf-8"}
        if path == "/healthz":
            return (
                200,
                json.dumps(
                    {"site_id": s.cfg["site_id"], "variant": s.cfg["variant_id"], "materials": len(s.materials)}
                ),
                {"Content-Type": "application/json"},
            )
        return self.not_found()

    # --- вариант C: обход квартиры ------------------------------------------------
    def audit_rooms(self) -> list[str]:
        return [r for r in ROOMS if self.site.in_room(r)]

    def picked(self, q: dict) -> list[str]:
        """Отмеченные инструкции из адреса; неизвестные слаги отбрасываются, порядок — как в каталоге."""
        want = set((q.get("m") or [])[:60])
        return [m.slug for m in self.site.materials if m.slug in want]

    def audit_room(self, room: str, q: dict):
        rooms = self.audit_rooms()
        i = rooms.index(room)
        picked = self.picked(q)
        crumbs = [("Главная", "/"), ("Обход квартиры", f"/obhod/{rooms[0]}/"), (ROOMS[room], f"/obhod/{room}/")]
        meta = Meta(
            f"Обход квартиры: {ROOMS[room].lower()} ({i + 1} из {len(rooms)})",
            f"Отметьте, что из этого про ваш дом: {ROOM_LEDE[room]}",
            None if picked else self.site.abs(f"/obhod/{room}/"),
            not picked,
            crumbs,
            [self.crumbs_ld(crumbs)],
            "audit",
        )
        nxt = rooms[i + 1] if i + 1 < len(rooms) else None
        body = self.render(
            "audit_room.html",
            meta,
            room=room,
            n=i + 1,
            total=len(rooms),
            rooms=rooms,
            items=self.site.in_room(room),
            picked=picked,
            nxt=nxt,
            prev=rooms[i - 1] if i else None,
        )
        return 200, body, {}

    def audit_plan(self, q: dict):
        picked = self.picked(q)
        mats = [self.site.by_slug[s] for s in picked]
        crumbs = [("Главная", "/"), ("Мой план", "/obhod/plan/")]
        meta = Meta(
            f"Мой план: {len(mats)} {plural(len(mats), 'инструкция', 'инструкции', 'инструкций')}"
            if mats
            else "Мой план",
            "План по итогам обхода квартиры: инструкции по комнатам и общий список того, что понадобится.",
            None if mats else self.site.abs("/obhod/plan/"),
            not mats,
            crumbs,
            [self.crumbs_ld(crumbs)],
            "plan",
        )
        need: dict[str, list] = {}
        for m in mats:
            for x in m.need:
                need.setdefault(x["text"], []).append(m)
        by_room = [(r, [m for m in mats if m.room == r]) for r in self.audit_rooms()]
        body = self.render(
            "audit_plan.html", meta, mats=mats, by_room=[x for x in by_room if x[1]], need=need, picked=picked
        )
        return 200, body, {}

    def sitemap_urls(self):
        s = self.site
        urls = [
            "/",
            "/obhod/plan/",
            "/problemy/",
            "/pomeshcheniya/",
            "/zadachi/",
            "/podborki/",
            "/istochniki/",
            "/kak-my-proveryaem/",
        ]
        urls += [f"/obhod/{r}/" for r in self.audit_rooms()]
        urls += [f"/problemy/{p}/" for p in s.problems]
        urls += [f"/pomeshcheniya/{r}/" for r in ROOMS if s.in_room(r)]
        urls += [f"/zadachi/{t}/" for t in TASKS if s.for_task(t)]
        urls += [f"/podborki/{c}/" for c in s.collections]
        urls += [f"/teg/{t}/" for t in s.tags()]
        urls += [m.url for m in s.materials]
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


def plural(n: int, one: str, few: str, many: str) -> str:
    n = abs(n) % 100
    if 11 <= n <= 14:
        return many
    return one if n % 10 == 1 else few if 2 <= n % 10 <= 4 else many


def make_handler(app: App):
    class H(http_server.BaseHTTPRequestHandler):
        server_version = "home-practical"
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
    ap = argparse.ArgumentParser(prog="home-practical serve")
    ap.add_argument("--port", type=int, help="другой локальный порт (чистая копия рядом с действующим превью)")
    port = ap.parse_args(argv).port or port
    if bind != "127.0.0.1":
        raise SystemExit("preview слушает только петлю")
    print(json.dumps({"listening": f"http://{bind}:{port}/", "materials": len(app.site.materials)}), flush=True)
    Server((bind, port), make_handler(app)).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
