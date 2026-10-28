"""zonafilm.cc: путь /movies/ → карточка и / → карточка; хиты Метрики перехватываются и НЕ отправляются (abort), записываются.

Метка factory-seo-acceptance; по одному запросу. Вывод JSON в argv[1].
"""
import json, sys, time, urllib.parse
from playwright.sync_api import sync_playwright
OUT = sys.argv[1]
R = {}
def run(p, devname, start):
    b = p.chromium.launch(headless=True, executable_path="/home/claude/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome")
    if devname == "phone":
        d = p.devices["iPhone 13"]; ctx = b.new_context(**{**d, "user_agent": d["user_agent"] + " factory-seo-acceptance"}, locale="ru-RU")
    else:
        ctx = b.new_context(viewport={"width": 1440, "height": 900}, user_agent="Mozilla/5.0 (X11; Linux x86_64) Chrome/130 factory-seo-acceptance", locale="ru-RU")
    hits = []
    def h(route):
        u = route.request.url
        q = urllib.parse.parse_qs(urllib.parse.urlparse(u).query)
        br = q.get("browser-info", [""])[0]
        hits.append({"t": round(time.time() - t0, 2), "path": urllib.parse.urlparse(u).path[:40], "page-url": q.get("page-url", [None])[0], "ar": "ar:1" in br, "pv": "pv:1" in br})
        if "/metrika/" in u and u.endswith(".js"): route.continue_()
        else: route.abort()
    ctx.route(lambda u: "mc.yandex" in u, h)
    pg = ctx.new_page(); t0 = time.time()
    pg.goto("https://zonafilm.cc" + start, wait_until="domcontentloaded", timeout=60000); pg.wait_for_timeout(3000)
    info = pg.evaluate("""()=>{const a=[...document.querySelectorAll('main a[href*="/title/"]')];
      const ym=[...document.scripts].some(s=>/mc\\.yandex|ym\\(/.test(s.src+s.textContent));
      const first=a.find(x=>{const r=x.getBoundingClientRect();return r.width>20&&r.height>20});
      return {title_links:a.length, ym_tag:ym, first:first&&first.getAttribute('href'), first_top: first&&Math.round(first.getBoundingClientRect().top), h1:(document.querySelector('h1')||{}).textContent,
       next_data: !!document.getElementById('__NEXT_DATA__')||!!window.next, innerH: innerHeight}}""")
    before = len(hits)
    res = {"start": start, **info, "hits_on_start": hits[:]}
    if info["first"]:
        loc = pg.locator(f'main a[href="{info["first"]}"]').first
        loc.scroll_into_view_if_needed(); t1 = time.time()
        loc.click(no_wait_after=True)
        try: pg.wait_for_url("**/title/**", wait_until="commit", timeout=20000)
        except Exception as e: res["nav_error"] = str(e)[:100]
        pg.wait_for_timeout(4000)
        res["after_url"] = pg.url; res["nav_s"] = round(time.time() - t1, 2)
        res["hits_after_click"] = hits[before:]
        res["card_ym_tag"] = pg.evaluate("()=>[...document.scripts].some(s=>/mc\\.yandex|ym\\(/.test(s.src+s.textContent))")
        pg.wait_for_timeout(3000)
        res["card_player"] = pg.evaluate("()=>({iframes:[...document.querySelectorAll('iframe')].map(f=>(f.src||'').slice(0,60)), video:document.querySelectorAll('video').length, playerlike:[...document.querySelectorAll('[class*=layer],[id*=layer]')].map(e=>e.tagName+'.'+(e.className||e.id)).slice(0,5), h1:(document.querySelector('h1')||{}).textContent})")
        res["hits_after_click"] = hits[before:]
    b.close()
    return res
with sync_playwright() as p:
    for dev in ("phone", "desktop"):
        for start in ("/movies/", "/"):
            R[f"{dev} {start}"] = run(p, dev, start); time.sleep(2)
json.dump(R, open(OUT, "w"), ensure_ascii=False, indent=1)
print(json.dumps(R, ensure_ascii=False, indent=1)[:6000])
