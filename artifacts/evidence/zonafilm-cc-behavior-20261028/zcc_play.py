"""Одно и два нажатия по плееру: доходит ли состояние до playing (телефон, компьютер). Метрика заблокирована."""
import json, sys, time
from playwright.sync_api import sync_playwright
R = {}
ST = "()=>{const f=document.querySelector('[data-player]');const v=[...document.querySelectorAll('video')].concat(...[...document.querySelectorAll('video-player')].map(x=>x.shadowRoot?[...x.shadowRoot.querySelectorAll('video')]:[]));return {state:f&&f.dataset.state, videos:v.length, playing:v.some(x=>!x.paused&&x.currentTime>0), t:v.map(x=>Math.round(x.currentTime*10)/10)}}"
with sync_playwright() as p:
    b = p.chromium.launch(headless=True, executable_path="/home/claude/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome")
    for dev in ("phone", "desktop"):
        if dev == "phone":
            d = p.devices["iPhone 13"]; ctx = b.new_context(**{**d, "user_agent": d["user_agent"] + " factory-seo-acceptance"}, locale="ru-RU")
        else:
            ctx = b.new_context(viewport={"width": 1440, "height": 900}, user_agent="Mozilla/5.0 (X11; Linux x86_64) Chrome/130 factory-seo-acceptance", locale="ru-RU")
        ctx.route(lambda u: "mc.yandex" in u, lambda r: r.abort())
        for s in ("yarost-na-predele", "prizrak-gilmor-haus"):
            pg = ctx.new_page(); pg.goto(f"https://zonafilm.cc/title/{s}/", wait_until="domcontentloaded", timeout=60000)
            pg.wait_for_timeout(800); pg.locator('a[data-cta="to-player"]').first.click(); pg.wait_for_timeout(4000)
            box = pg.locator("[data-player]").first.bounding_box()
            seq = [("before", pg.evaluate(ST))]
            for n in (1, 2):
                pg.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2) if dev == "desktop" else pg.touchscreen.tap(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                pg.wait_for_timeout(6000); seq.append((f"tap{n}", pg.evaluate(ST)))
            pg.screenshot(path=f"{sys.argv[2]}/zcc-play-{dev}-{s}.png")
            R[f"{dev} {s}"] = seq; print(dev, s, seq, flush=True); pg.close(); time.sleep(1)
        ctx.close()
    b.close()
json.dump(R, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
