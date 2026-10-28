"""Сообщения плеера поставщика родительской странице: последовательность от нажатия до основного видео. Метрика заблокирована."""
import json, sys, time
from playwright.sync_api import sync_playwright
S = sys.argv[1]; R = {}
INIT = """window.__pm=[];window.__t0=Date.now();window.addEventListener('message',e=>{let p=e.data;try{if(typeof p==='string')p=JSON.parse(p)}catch(x){return}
 if(p&&p.eventType){const d=p.data;window.__pm.push([Math.round((Date.now()-window.__t0)/100)/10,p.eventType,typeof d==='object'?JSON.stringify(d).slice(0,60):String(d).slice(0,30)])}});"""
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, executable_path="/home/claude/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome", args=["--autoplay-policy=no-user-gesture-required"])
    for dev in ("desktop", "phone"):
        for slug in ("yarost-na-predele", "tyurma-chernyy-ostrov"):
            if dev == "phone":
                d = pw.devices["iPhone 13"]; ctx = b.new_context(**{**d, "user_agent": d["user_agent"] + " factory-seo-acceptance"}, locale="ru-RU")
            else:
                ctx = b.new_context(viewport={"width": 1440, "height": 900}, user_agent="Mozilla/5.0 (X11; Linux x86_64) Chrome/130 factory-seo-acceptance", locale="ru-RU")
            ctx.route(lambda u: "mc.yandex" in u, lambda r: r.abort()); ctx.add_init_script(INIT)
            pg = ctx.new_page(); pg.goto(f"https://zonafilm.cc/title/{slug}/", wait_until="domcontentloaded", timeout=60000)
            pg.wait_for_timeout(800); pg.locator('a[data-cta="to-player"]').first.click(); pg.wait_for_timeout(4000)
            box = pg.locator("[data-player]").first.bounding_box(); taps = []
            for k in range(1):
                t = pg.evaluate("Math.round((Date.now()-window.__t0)/100)/10"); taps.append(t)
                (pg.touchscreen.tap if dev == "phone" else pg.mouse.click)(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                pg.wait_for_timeout(75000)
                ev = pg.evaluate("window.__pm.map(x=>x[1])")
                if "timeupdate" in ev and any(x[1] == "timeupdate" and '"position"' in x[2] for x in pg.evaluate("window.__pm")): pass
            pg.wait_for_timeout(15000)
            pm = pg.evaluate("window.__pm")
            types = []
            for x in pm:
                if not types or types[-1][1] != x[1]: types.append([x[0], x[1], x[2], 1])
                else: types[-1][3] += 1
            R[f"{dev} {slug}"] = {"taps_at": taps, "sequence": types[:60], "state": pg.evaluate("(document.querySelector('[data-player]')||{}).dataset?.state")}
            print(dev, slug, "taps", taps, "state", R[f"{dev} {slug}"]["state"]); [print("   ", t) for t in types[:40]]
            ctx.close(); time.sleep(1)
    b.close()
json.dump(R, open(S + "/zcc/pm-onetap.json", "w"), ensure_ascii=False, indent=1)
