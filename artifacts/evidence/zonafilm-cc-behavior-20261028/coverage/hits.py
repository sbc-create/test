"""Отправка хитов Метрики по шаблонам zonafilm.cc: прямое открытие и переход внутри сайта, телефон и компьютер.

Хиты ОТПРАВЛЯЮТСЯ (контрольные визиты): первая страница визита открывается с utm_source=factory-control,
utm_medium=acceptance, utm_campaign=coverage-20261028 — по метке визиты отделяются от аудитории и подтверждают
получение выгрузкой (control_visits). Ответ mc.yandex фиксируется, но получением в отчёте не считается.
"""
import json, sys, time, urllib.parse
from playwright.sync_api import sync_playwright
S = sys.argv[1]; OUT = S + "/zcc/hits.json"
UTM = "utm_source=factory-control&utm_medium=acceptance&utm_campaign=coverage-20261028"
DIRECT = [("главная", "/"), ("раздел фильмов", "/movies/"), ("пагинация", "/movies/?page=2"), ("фильтр", "/movies/?genre=action"),
          ("раздел сериалов", "/series/"), ("каталог по жанру", "/catalog/?genre=action"), ("поиск", "/search/?q=%D0%BE%D0%B4%D0%B8%D1%81%D1%81%D0%B5%D1%8F"),
          ("список подборок", "/collections/"), ("подборка", None), ("карточка фильма", "/title/yarost-na-predele/"),
          ("карточка сериала", "/title/tyurma-chernyy-ostrov/"), ("сезон", "/title/tyurma-chernyy-ostrov/season-1/"),
          ("серия", "/title/tyurma-chernyy-ostrov/season-1/episode-9/"), ("404", "/no-such-page-factory-check/")]
NAV = [("главная → карточка", "/", 'main a[href^="/title/"]'), ("фильмы → карточка", "/movies/", 'main a[href^="/title/"]'),
       ("поиск → карточка", "/search/?q=%D0%BE%D0%B4%D0%B8%D1%81%D1%81%D0%B5%D1%8F", 'main a[href^="/title/"]'),
       ("подборки → подборка", "/collections/", 'main a[href^="/collection/"]'), ("сериал → серия", "/title/tyurma-chernyy-ostrov/", 'a[href*="/episode-"]')]
def utm(p): return p + ("&" if "?" in p else "?") + UTM
R = []
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, executable_path="/home/claude/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome")
    for dev in ("phone", "desktop"):
        def ctx_new():
            if dev == "phone":
                d = pw.devices["iPhone 13"]; return b.new_context(**{**d, "user_agent": d["user_agent"] + " factory-seo-acceptance"}, locale="ru-RU")
            return b.new_context(viewport={"width": 1440, "height": 900}, user_agent="Mozilla/5.0 (X11; Linux x86_64) Chrome/130 factory-seo-acceptance", locale="ru-RU")
        def run(label, path, sel=None):
            ctx = ctx_new(); pg = ctx.new_page(); hits = []; errs = []
            def on_resp(r):
                u = r.url
                if "mc.yandex" in u and ("/watch/" in u or "tag.js" in u):
                    q = urllib.parse.parse_qs(urllib.parse.urlparse(u).query); bi = q.get("browser-info", [""])[0]
                    hits.append({"kind": "tag" if "tag.js" in u else "watch", "status": r.status, "id": urllib.parse.urlparse(u).path.split("/")[-1],
                                 "page": (q.get("page-url", [""])[0] or "").replace("https://zonafilm.cc", ""), "pv": "pv:1" in bi, "ar": "ar:1" in bi})
            pg.on("response", on_resp); pg.on("requestfailed", lambda r: errs.append(r.url[:80]) if "mc.yandex" in r.url else None)
            pg.goto("https://zonafilm.cc" + utm(path), wait_until="domcontentloaded", timeout=60000); pg.wait_for_timeout(3500)
            step = {"dev": dev, "label": label, "start": path, "start_status": None}
            if sel:
                loc = pg.locator(sel).first
                if loc.count():
                    href = loc.get_attribute("href"); loc.scroll_into_view_if_needed(); loc.click(no_wait_after=True)
                    try: pg.wait_for_url("**" + href.split("?")[0] + "**", wait_until="commit", timeout=20000)
                    except Exception: pass
                    pg.wait_for_timeout(3500); step["to"] = href
                else: step["to"] = None
            step["hits"] = hits; step["mc_failed"] = errs; step["final"] = pg.url.replace("https://zonafilm.cc", "")
            R.append(step); print(json.dumps({k: v for k, v in step.items() if k != "hits"}, ensure_ascii=False), [(h["kind"], h["status"], h["id"], h["page"][:50], h["pv"]) for h in hits if h["kind"] == "watch"], flush=True)
            ctx.close(); time.sleep(1)
        for label, path in DIRECT:
            if path is None: path = "/collection/genre_comedy/"
            run(label, path)
        for label, path, sel in NAV: run(label, path, sel)
    b.close()
json.dump(R, open(OUT, "w"), ensure_ascii=False, indent=1)
