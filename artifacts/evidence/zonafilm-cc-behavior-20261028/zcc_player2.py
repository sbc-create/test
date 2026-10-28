"""Телефон: карточка → прокрутка к плееру (как «К плееру») → состояния 20 с; видимый текст плеера. Метрика заблокирована."""
import json, sys, time
from playwright.sync_api import sync_playwright
SL = ["yarost-na-predele", "vozvraschenie-k-strahu", "prizrak-gilmor-haus", "chelovek-pauk-novyy-den", "taynyy-dnevnik-veriti", "golye-i-napugannye-na-neobitaemom-ostrove", "odisseya"]
R = {}
JS = """()=>{const f=document.querySelector('[data-player]');const s=f&&f.querySelector('.zpl__s');const vp=f&&f.querySelector('video-player');
return {state:f&&f.dataset.state, msg_visible: !!(s&&!s.hidden&&getComputedStyle(s).display!='none'), msg: s&&s.innerText.slice(0,80),
 vp_children: vp? (vp.shadowRoot? 'shadow:'+vp.shadowRoot.childElementCount : vp.childElementCount):null, iframe: !!(f&&f.querySelector('iframe')), head:(document.querySelector('.zpl__h span')||{}).innerText}}"""
with sync_playwright() as p:
    b = p.chromium.launch(headless=True, executable_path="/home/claude/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome")
    d = p.devices["iPhone 13"]; ctx = b.new_context(**{**d, "user_agent": d["user_agent"] + " factory-seo-acceptance"}, locale="ru-RU")
    ctx.route(lambda u: "mc.yandex" in u, lambda r: r.abort())
    for s in SL:
        pg = ctx.new_page()
        pg.goto(f"https://zonafilm.cc/title/{s}/", wait_until="domcontentloaded", timeout=60000); pg.wait_for_timeout(800)
        cta = pg.locator('a[data-cta="to-player"]').first
        cta_box = cta.bounding_box() if cta.count() else None
        if cta.count(): cta.click()
        seq = []
        for i in range(20):
            pg.wait_for_timeout(1000); r = pg.evaluate(JS)
            if not seq or seq[-1][1] != r["state"]: seq.append((i + 1, r["state"]))
        last = pg.evaluate(JS)
        R[s] = {"cta_top": cta_box and round(cta_box["y"]), "states": seq, "final": last}
        print(s, R[s], flush=True); pg.close(); time.sleep(1)
    b.close()
json.dump(R, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
