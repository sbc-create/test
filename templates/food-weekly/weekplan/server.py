"""SSR-сервер food-weekly: недельная сетка, день, список покупок, замены в адресе."""

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
import yaml

from . import planner

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"
HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; "
    "frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
}
COLLECTIONS = {
    "uzhiny-do-chasa": (
        "Ужины до часа",
        "Вторые блюда и гарниры, которые по данным рецептов готовятся не дольше 60 минут.",
        lambda x: x["category"] in ("vtorye-blyuda", "garniry") and (x["total_minutes"] or 999) <= 60,
    ),
    "supy-dlya-obedov": (
        "Супы для обедов недели",
        "Все супы каталога: можно варить кастрюлю на два дня.",
        lambda x: x["category"] == "supy",
    ),
    "zavtraki-nedeli": (
        "Завтраки на семь дней",
        "Все завтраки каталога для замены в планах.",
        lambda x: x["category"] == "zavtraki",
    ),
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
    def __init__(self, cfg_path: Path | None = None):
        self.cfg = yaml.safe_load((cfg_path or ROOT / "config" / "site.yaml").read_text())
        self.net = yaml.safe_load((ROOT / "config" / "network.yaml").read_text())
        self.catalogs = planner.load_catalogs()
        self.plans = planner.load_plans(self.catalogs)
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
            MEALS=planner.MEALS,
            DAYS=planner.DAYS,
            plural=plural,
            asset=lambda rel: f"/static/{rel}?v={h.get(rel, '0')}",
        )

    # --- адреса -----------------------------------------------------------
    @property
    def indexable(self) -> bool:
        return (
            self.cfg["mode"] == "production"
            and bool(self.cfg["production_authorized"])
            and bool(self.cfg["origin"]["production"])
        )

    def abs(self, path: str) -> str:
        o = self.cfg["origin"][self.cfg["mode"]]
        if not o:
            raise RuntimeError("origin не задан (BLOCKED_INPUT)")
        return o.rstrip("/") + path

    def recipe_url(self, site: str, item: dict) -> str:
        """Адрес материала соседнего сайта по реестру сети; в preview — его закрытый preview."""
        origin = self.net["sites"][site]["origin"][self.cfg["mode"]]
        if not origin:
            raise RuntimeError(f"у сайта {site} нет адреса для режима {self.cfg['mode']}")
        return origin.rstrip("/") + item["path"]

    def site_status(self, site: str) -> str:
        return self.net["sites"][site]["integration_status"]

    def robots(self, meta: Meta) -> str:
        if not self.indexable:
            return "noindex, nofollow"
        return "index, follow" if meta.index else "noindex, follow"

    def render(self, tpl, meta, **ctx):
        return self.env.get_template(tpl).render(meta=meta, robots=self.robots(meta), **ctx)

    def crumbs_ld(self, crumbs):
        return {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "name": n, "item": self.abs(p)}
                for i, (n, p) in enumerate(crumbs)
            ],
        }

    # --- маршруты -----------------------------------------------------------
    def route(self, path: str, q: dict):
        g = lambda k: (q.get(k) or [""])[0]  # noqa: E731
        if path == "/svoya-nedelya/":
            return self.own_week(q)
        if path == "/":
            meta = Meta(
                f"{self.cfg['name']} — готовые планы и список покупок",
                "Готовые планы питания на 7 дней: завтрак, обед и ужин, замена блюд и список покупок, который считается сам.",
                self.abs("/"),
                True,
                kind="home",
            )
            return 200, self.render("home.html", meta), {}
        if path == "/menyu/":
            crumbs = [("Главная", "/"), ("Планы меню", "/menyu/")]
            meta = Meta(
                "Планы меню на неделю",
                "Три готовых плана на 7 дней: на двоих, на семью из четырёх, осенний.",
                self.abs(path),
                True,
                crumbs,
                [self.crumbs_ld(crumbs)],
                "catalog",
            )
            return 200, self.render("plans.html", meta), {}
        m = re.fullmatch(r"/menyu/([a-z0-9-]+)/(?:(den-([1-7])|pokupki)/)?", path)
        if m and m.group(1) in self.plans:
            plan = self.plans[m.group(1)]
            swaps = planner.parse_swaps(g("zamena"))
            swaps.update(planner.parse_swaps(g("s")))  # новая замена из формы поверх уже выбранных
            swaps = {k: v for k, v in swaps.items() if k[0] <= 7}
            days, notes = planner.resolve(plan, self.catalogs, swaps)
            base = f"/menyu/{plan['slug']}/"
            crumbs = [("Главная", "/"), ("Планы меню", "/menyu/"), (plan["title"], base)]
            qs = ("?zamena=" + urllib.parse.quote(planner.encode_swaps(swaps), safe=":,-")) if swaps else ""
            if m.group(3):
                n = int(m.group(3))
                own = f"{base}den-{n}/"
                crumbs.append((planner.DAYS[n - 1], own))
                meta = Meta(
                    f"{plan['title']}: {planner.DAYS[n - 1].lower()}",
                    f"{planner.DAYS[n - 1]} в плане «{plan['title']}»: завтрак, обед и ужин со ссылками на рецепты.",
                    None if swaps else self.abs(own),
                    not swaps,
                    crumbs,
                    [self.crumbs_ld(crumbs)],
                    "day",
                )
                return 200, self.render("day.html", meta, plan=plan, day=days[n - 1], n=n, qs=qs, notes=notes), {}
            if m.group(2) == "pokupki":
                own = f"{base}pokupki/"
                crumbs.append(("Список покупок", own))
                sl = planner.shopping_list(days, plan["people"])
                trips = [  # перенесено из B: две закупки по дням плана
                    ("Закупка 1: понедельник — среда", planner.shopping_list(days[:3], plan["people"]), "1"),
                    ("Закупка 2: четверг — воскресенье", planner.shopping_list(days[3:], plan["people"]), "2"),
                ]
                meta = Meta(
                    f"Список покупок: {plan['title']}",
                    f"Продукты плана «{plan['title']}» на {plan['people']} чел. двумя закупками "
                    "(пн–ср и чт–вс) и одним списком, по единицам измерения.",
                    None if swaps else self.abs(own),
                    not swaps,
                    crumbs,
                    [self.crumbs_ld(crumbs)],
                    "shopping",
                )
                return (
                    200,
                    self.render("shopping.html", meta, plan=plan, sl=sl, trips=trips, qs=qs, swaps=swaps, notes=notes),
                    {},
                )
            meta = Meta(
                plan["title"],
                plan["description"],
                None if swaps else self.abs(base),
                not swaps,
                crumbs,
                [self.crumbs_ld(crumbs)],
                "week",
            )
            return (
                200,
                self.render(
                    "week.html",
                    meta,
                    plan=plan,
                    days=days,
                    swaps=swaps,
                    qs=qs,
                    notes=notes,
                    zcur=planner.encode_swaps(swaps),
                    alts={meal: planner.alternatives(self.catalogs, "food-daily", meal) for meal in planner.MEALS},
                ),
                {},
            )
        if path == "/kak-planirovat/":
            crumbs = [("Главная", "/"), ("Как планировать", path)]
            meta = Meta(
                "Как пользоваться планом меню",
                "Как выбрать план, заменить блюдо, учесть число людей и собрать список покупок.",
                self.abs(path),
                True,
                crumbs,
                [self.crumbs_ld(crumbs)],
                "guide",
            )
            return 200, self.render("guide.html", meta), {}
        m = re.fullmatch(r"/podborki/([a-z0-9-]+)/", path)
        if m and m.group(1) in COLLECTIONS:
            title, desc, pred = COLLECTIONS[m.group(1)]
            items = sorted(
                (x for x in self.catalogs["food-daily"]["items"].values() if pred(x)), key=lambda x: x["title"]
            )
            if len(items) < 3:
                return self.not_found()
            crumbs = [("Главная", "/"), ("Подборки", "/podborki/"), (title, path)]
            meta = Meta(title, desc, self.abs(path), True, crumbs, [self.crumbs_ld(crumbs)], "collection")
            return 200, self.render("collection.html", meta, title=title, desc=desc, items=items), {}
        if path == "/podborki/":
            crumbs = [("Главная", "/"), ("Подборки", path)]
            meta = Meta(
                "Подборки блюд для планов",
                "Наборы блюд для замены в планах недели.",
                self.abs(path),
                True,
                crumbs,
                [self.crumbs_ld(crumbs)],
                "collections",
            )
            live = {
                k: v
                for k, v in COLLECTIONS.items()
                if sum(1 for x in self.catalogs["food-daily"]["items"].values() if v[2](x)) >= 3
            }
            return 200, self.render("collections.html", meta, cols=live), {}
        if path == "/robots.txt":
            body = (
                "User-agent: *\nDisallow: /\n"
                if not self.indexable
                else f"User-agent: *\nDisallow: /*?\nSitemap: {self.abs('/sitemap.xml')}\n"
            )
            return 200, body, {"Content-Type": "text/plain; charset=utf-8"}
        if path == "/sitemap.xml":
            return 200, self.sitemap(), {"Content-Type": "application/xml; charset=utf-8"}
        if path == "/healthz":
            return (
                200,
                json.dumps(
                    {
                        "site_id": self.cfg["site_id"],
                        "plans": len(self.plans),
                        "catalog": {k: v["meta"]["fetched_at"] for k, v in self.catalogs.items()},
                    }
                ),
                {"Content-Type": "application/json"},
            )
        return self.not_found()

    def own_week(self, q: dict):
        """Своя неделя: без выбора — индексируемая форма; с выбором — noindex без canonical; люди вне 1–8 — 400."""
        g = lambda k: (q.get(k) or [""])[0].strip()  # noqa: E731
        picks = {(n, meal): g(f"d{n}-{meal}") for n in range(1, 8) for meal in planner.MEALS if g(f"d{n}-{meal}")}
        raw_people = g("lyudi") or "2"
        error = None
        people = int(raw_people) if raw_people.isdigit() else 0
        if not 1 <= people <= 8:
            error, people = "Число людей — от 1 до 8.", 2
        days, notes = planner.custom_days(self.catalogs, picks)
        chosen = sum(len(day[m]) for day in days for m in planner.MEALS)
        sl = planner.shopping_list(days, people) if chosen else {"items": [], "to_taste": []}
        asked = bool(picks) or bool(g("lyudi"))
        crumbs = [("Главная", "/"), ("Своя неделя", "/svoya-nedelya/")]
        meta = Meta(
            f"Своя неделя: {chosen} {plural(chosen, 'блюдо', 'блюда', 'блюд')}"
            if chosen
            else "Своя неделя: соберите меню сами",
            "Выберите блюда на каждый день из каталога «Будней на кухне» — список покупок посчитается по рецептам.",
            None if asked else self.abs("/svoya-nedelya/"),
            not asked,
            crumbs,
            [self.crumbs_ld(crumbs)],
            "own",
        )
        alts = {meal: planner.alternatives(self.catalogs, "food-daily", meal) for meal in planner.MEALS}
        seeds = {
            slug: "&".join(
                f"d{n}-{meal}={day[meal][0]['slug']}"
                for n, day in enumerate(p["days"], 1)
                for meal in planner.MEALS
                if day[meal]
            )
            + f"&lyudi={p['people']}"
            for slug, p in self.plans.items()
        }
        body = self.render(
            "own_week.html",
            meta,
            days=days,
            picks=picks,
            people=people,
            alts=alts,
            sl=sl,
            notes=notes,
            chosen=chosen,
            error=error,
            seeds=seeds,
        )
        return (400 if error else 200), body, {}

    def sitemap_urls(self):
        urls = ["/", "/svoya-nedelya/", "/menyu/", "/kak-planirovat/", "/podborki/"]
        for slug in self.plans:
            urls += [f"/menyu/{slug}/", f"/menyu/{slug}/pokupki/"] + [f"/menyu/{slug}/den-{n}/" for n in range(1, 8)]
        urls += [
            f"/podborki/{k}/"
            for k, (_, _, pred) in COLLECTIONS.items()
            if sum(1 for x in self.catalogs["food-daily"]["items"].values() if pred(x)) >= 3
        ]
        return urls

    def sitemap(self):
        rows = "\n".join(f"<url><loc>{self.abs(p)}</loc></url>" for p in self.sitemap_urls())
        return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{rows}\n</urlset>\n'

    def not_found(self):
        return (
            404,
            self.render("404.html", Meta("Страница не найдена", "Такой страницы нет.", None, False, kind="404")),
            {},
        )


def make_handler(app: App):
    class H(http_server.BaseHTTPRequestHandler):
        server_version = "food-weekly"
        sys_version = ""

        def log_message(self, *a):
            pass

        def send(self, status, body, headers=None):
            data = body.encode() if isinstance(body, str) else body
            self.send_response(status)
            hh = {"Content-Type": "text/html; charset=utf-8", **HEADERS, **(headers or {})}
            if not app.indexable:
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
    bind, port = app.cfg["server"]["bind"], app.cfg["server"]["port"]
    if bind != "127.0.0.1":
        raise SystemExit("preview слушает только петлю")
    print(json.dumps({"listening": f"http://{bind}:{port}/", "plans": len(app.plans)}), flush=True)
    Server((bind, port), make_handler(app)).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
