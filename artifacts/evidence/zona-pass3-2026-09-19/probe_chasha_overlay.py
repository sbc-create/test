"""Probe live chasha-vesny player overlay bug."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

OUT = Path("/home/claude/wt-zona-finalization-01/artifacts/evidence/zona-pass3-2026-09-19")
OUT.mkdir(parents=True, exist_ok=True)
URL = "https://zonafilm.space/title/chasha-vesny/"


async def main() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        await page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(2000)
        # click first available episode if on hub, else player
        ep = page.locator('a[href*="/season-"][href*="/episode-"]').first
        if await ep.count():
            href = await ep.get_attribute("href")
            await page.goto("https://zonafilm.space" + href, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)
        box = await page.evaluate(
            """() => {
              const f=document.querySelector('[data-player]');
              if(!f) return null;
              const r=f.getBoundingClientRect();
              return {x:r.x+r.width/2,y:r.y+r.height/2,w:r.width,h:r.height,state:f.getAttribute('data-state')};
            }"""
        )
        if box:
            await page.mouse.click(box["x"], box["y"])
        await page.wait_for_timeout(8000)
        info = await page.evaluate(
            """() => {
              const st=document.querySelector('[data-player-state]');
              const f=document.querySelector('[data-player]');
              const cs=st?getComputedStyle(st):null;
              return {
                build: document.documentElement.getAttribute('data-build-id'),
                state: f&&f.getAttribute('data-state'),
                label: (document.querySelector('.zpl__h span')||{}).textContent,
                stHidden: st?st.hidden:null,
                stAttr: st?st.getAttribute('hidden'):null,
                stDisplay: cs&&cs.display,
                stVisibility: cs&&cs.visibility,
                stText: st?(st.innerText||'').slice(0,200):'',
                stClass: st&&st.className,
                zonaPlaying: window.__zonaPlayerPlaying||null,
                iframeCount: document.querySelectorAll('iframe').length
              };
            }"""
        )
        (OUT / "before-chasha-overlay.json").write_text(
            json.dumps({"box": box, "info": info}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(info, ensure_ascii=False, indent=2))
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
