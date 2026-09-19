"""PASS3 golden: chasha-vesny playback overlay must stay hidden for 35s × N."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

OUT = Path("/home/claude/wt-zona-finalization-01/artifacts/evidence/zona-pass3-2026-09-19")
OUT.mkdir(parents=True, exist_ok=True)
BASE = "https://zonafilm.space"
HUB = "/title/chasha-vesny/"
RUNS = 10


async def one_run(page, run: int) -> dict:
    await page.goto(BASE + HUB, wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(1200)
    # Pick first available episode link
    href = await page.evaluate(
        """() => {
          const a=[...document.querySelectorAll('.zeps a[href*="/episode-"]')]
            .find(el => el.getAttribute('aria-disabled')!=='true');
          return a ? a.getAttribute('href') : null;
        }"""
    )
    if not href:
        return {"run": run, "error": "no available episode link"}
    await page.goto(BASE + href, wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(2000)

    box = await page.evaluate(
        """() => {
          const f=document.querySelector('[data-player]');
          if(!f) return null;
          const r=f.getBoundingClientRect();
          return {x:r.x+r.width/2,y:r.y+Math.max(40,r.height/2),w:r.width,h:r.height,
                  state:f.getAttribute('data-state')};
        }"""
    )
    if box and box.get("w", 0) > 40:
        await page.mouse.click(box["x"], box["y"])
        for fr in page.frames:
            if "player.cdnvideohub.com" in (fr.url or ""):
                try:
                    await fr.click("body", timeout=1500, position={"x": 220, "y": 140})
                except Exception:
                    pass

    # Wait until progress >=3s confirmed or 20s elapsed
    for _ in range(20):
        await page.wait_for_timeout(1000)
        early = await page.evaluate("() => window.__zonaPlayerPlaying || null")
        if early and (early.get("pos") or 0) >= 3:
            break

    # Observe for 35s so stale timeout cannot revive overlay
    await page.wait_for_timeout(35000)

    info = await page.evaluate(
        """() => {
          const f=document.querySelector('[data-player]');
          const st=document.querySelector('[data-player-state]');
          const cs=st?getComputedStyle(st):null;
          const zp=window.__zonaPlayerPlaying||null;
          const label=(document.querySelector('.zpl__h span')||{}).textContent||'';
          const players=document.querySelectorAll('video-player').length;
          const iframes=[...document.querySelectorAll('iframe')].filter(i=>{
            try{return (i.src||'').includes('cdnvideohub')||i.closest('[data-player]');}catch(e){return false;}
          }).length;
          const overlayVisible = !!(st && !st.hidden && cs && cs.display!=='none'
            && cs.visibility!=='hidden' && parseFloat(cs.opacity||'1')>0.01);
          const text=(st&&st.innerText||'');
          const unavailText=/временно недоступно/i.test(text);
          const state=f&&f.getAttribute('data-state');
          return {
            build: document.documentElement.getAttribute('data-build-id'),
            state, label, zp,
            stHidden: st?st.hidden:null,
            stDisplay: cs&&cs.display,
            stVisibility: cs&&cs.visibility,
            stOpacity: cs&&cs.opacity,
            stText: text.slice(0,160),
            overlayVisible, unavailText,
            players, iframes,
            ACTUAL_PROGRESS: !!(zp && (zp.pos||0)>=3),
            VISIBLE_UNAVAILABLE_OVERLAY: !!(overlayVisible && unavailText),
            PLAYING_AND_ERROR_SIMULTANEOUS: !!(state==='playing' && overlayVisible && unavailText),
            ACTIVE_PLAYER_COUNT: Math.max(players, iframes?1:0),
          };
        }"""
    )

    # Episode switch round-trip
    await page.goto(BASE + HUB, wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(800)
    href2 = await page.evaluate(
        """() => {
          const links=[...document.querySelectorAll('.zeps a[href*="/episode-"]')];
          const a=links.find(el => /episode-2/.test(el.getAttribute('href')||''))
               || links.find(el => el.getAttribute('aria-disabled')!=='true');
          return a?a.getAttribute('href'):null;
        }"""
    )
    switch_ok = False
    if href2:
        await page.goto(BASE + href2, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(1500)
        await page.goto(BASE + href, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(1500)
        switch_ok = True

    # Hard reload repeat
    await page.reload(wait_until="domcontentloaded")
    await page.wait_for_timeout(2000)
    box2 = await page.evaluate(
        """() => {
          const f=document.querySelector('[data-player]');
          if(!f) return null;
          const r=f.getBoundingClientRect();
          return {x:r.x+r.width/2,y:r.y+Math.max(40,r.height/2),w:r.width,h:r.height};
        }"""
    )
    if box2:
        await page.mouse.click(box2["x"], box2["y"])
    await page.wait_for_timeout(12000)
    after_reload = await page.evaluate(
        """() => {
          const zp=window.__zonaPlayerPlaying||null;
          const st=document.querySelector('[data-player-state]');
          const cs=st?getComputedStyle(st):null;
          const overlayVisible=!!(st&&!st.hidden&&cs&&cs.display!=='none');
          return {
            ACTUAL_PROGRESS: !!(zp && (zp.pos||0)>=3),
            VISIBLE_UNAVAILABLE_OVERLAY: !!(overlayVisible && /временно недоступно/i.test(st&&st.innerText||'')),
            stDisplay: cs&&cs.display,
            stHidden: st&&st.hidden,
            zp,
          };
        }"""
    )

    pass_flags = (
        info.get("ACTUAL_PROGRESS") == True
        and info.get("VISIBLE_UNAVAILABLE_OVERLAY") == False
        and info.get("PLAYING_AND_ERROR_SIMULTANEOUS") == False
        and (info.get("ACTIVE_PLAYER_COUNT") or 0) <= 1
        and info.get("stHidden") is True
        and info.get("stDisplay") == "none"
    )
    return {
        "run": run,
        "href": href,
        "switch_ok": switch_ok,
        "info": info,
        "after_reload": after_reload,
        "PASS": pass_flags,
    }


async def main() -> None:
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        for i in range(1, RUNS + 1):
            ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
            page = await ctx.new_page()
            try:
                r = await one_run(page, i)
            except Exception as exc:
                r = {"run": i, "error": str(exc), "PASS": False}
            results.append(r)
            print(json.dumps({"run": i, "PASS": r.get("PASS"), "err": r.get("error"),
                              "progress": (r.get("info") or {}).get("ACTUAL_PROGRESS"),
                              "overlay": (r.get("info") or {}).get("VISIBLE_UNAVAILABLE_OVERLAY"),
                              "display": (r.get("info") or {}).get("stDisplay")},
                             ensure_ascii=False))
            await ctx.close()
        await browser.close()
    summary = {
        "runs": RUNS,
        "passed": sum(1 for r in results if r.get("PASS")),
        "failed": sum(1 for r in results if not r.get("PASS")),
        "results": results,
    }
    (OUT / "golden-chasha-10x.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("SUMMARY", summary["passed"], "/", RUNS)
    raise SystemExit(0 if summary["passed"] == RUNS else 1)


if __name__ == "__main__":
    asyncio.run(main())
