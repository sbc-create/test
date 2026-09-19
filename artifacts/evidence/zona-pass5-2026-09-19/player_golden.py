#!/usr/bin/env python3
import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

OUT = Path("/home/claude/wt-zona-finalization-01/artifacts/evidence/zona-pass5-2026-09-19")
URLS = [
    "https://zonafilm.space/title/chasha-vesny/season-1/episode-1/",
    "https://zonafilm.space/title/v-lovushke/",
    "https://zonafilm.space/title/voy-2/",
]


async def one(page, url):
    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(1500)
    box = await page.evaluate(
        """()=>{const f=document.querySelector('[data-player]');if(!f)return null;
        const r=f.getBoundingClientRect();
        return{x:r.x+r.width/2,y:r.y+Math.max(40,r.height/2)};}"""
    )
    if box:
        await page.mouse.click(box["x"], box["y"])
    for fr in page.frames:
        if "player.cdnvideohub.com" in (fr.url or ""):
            try:
                await fr.click("body", timeout=1200, position={"x": 200, "y": 140})
            except Exception:
                pass
    await page.wait_for_timeout(12000)
    return await page.evaluate(
        """()=>{
    const f=document.querySelector('[data-player]');
    const st=document.querySelector('[data-player-state]');
    const cs=st&&getComputedStyle(st);
    const zp=window.__zonaPlayerPlaying||null;
    const overlay=!!(st&&!st.hidden&&cs&&cs.display!=='none'&&/недоступно/i.test(st.innerText||''));
    return {build:document.documentElement.getAttribute('data-build-id'),
      state:f&&f.getAttribute('data-state'),
      ACTUAL_PROGRESS:!!(zp&&(zp.pos||0)>=3),
      VISIBLE_UNAVAILABLE_OVERLAY:overlay,
      PLAYING_AND_ERROR_SIMULTANEOUS:!!(f&&f.getAttribute('data-state')==='playing'&&overlay),
      ACTIVE_PLAYER_COUNT:document.querySelectorAll('video-player').length,
      zp, stDisplay:cs&&cs.display, stHidden:st&&st.hidden};
  }"""
    )


async def main():
    results = []
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        for i in range(10):
            url = URLS[i % len(URLS)]
            ctx = await b.new_context(
                viewport={"width": 1440 if i % 2 == 0 else 390, "height": 900}
            )
            page = await ctx.new_page()
            try:
                info = await one(page, url)
                ok = (
                    info["ACTUAL_PROGRESS"]
                    and not info["VISIBLE_UNAVAILABLE_OVERLAY"]
                    and not info["PLAYING_AND_ERROR_SIMULTANEOUS"]
                    and info["ACTIVE_PLAYER_COUNT"] <= 1
                )
                results.append({"run": i + 1, "url": url, "PASS": ok, **info})
                print(i + 1, ok, info.get("build"), info.get("ACTUAL_PROGRESS"))
            except Exception as e:
                results.append({"run": i + 1, "url": url, "PASS": False, "error": str(e)})
                print(i + 1, "ERR", e)
            await ctx.close()
        await b.close()
    summary = {
        "passed": sum(1 for r in results if r.get("PASS")),
        "runs": len(results),
        "results": results,
    }
    (OUT / "PLAYER_GOLDEN.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("SUMMARY", summary["passed"], "/", summary["runs"])


if __name__ == "__main__":
    asyncio.run(main())
