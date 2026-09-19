"""Check postMessage, iframe size fill, and HLS media requests."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

OUT = Path("/home/claude/wt-zona-finalization-01/artifacts/evidence/zona-pass2-2026-09-19")
URL = "https://zonafilm.space/title/aida-vozvraschaetsya/"


async def main() -> None:
    msgs = []
    media = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await ctx.new_page()
        page.on(
            "console",
            lambda m: msgs.append({"type": "console", "text": m.text[:200]})
            if m.type in ("log", "error", "warning")
            else None,
        )

        async def on_resp(r):
            u = r.url
            if any(x in u for x in (".m3u8", ".mp4", "okcdn.ru", "video.m3u8", "/video.")):
                media.append({"status": r.status, "url": u[:220], "ct": (r.headers or {}).get("content-type", "")})

        page.on("response", on_resp)
        await page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        await page.add_init_script(
            """window.__pm=[]; window.addEventListener('message', e => {
              window.__pm.push({origin:e.origin, data: typeof e.data==='string'?e.data.slice(0,300):JSON.stringify(e.data).slice(0,300)});
            });"""
        )
        # reload so init script applies
        await page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(4000)
        # click iframe center via frame locator if possible
        dims = await page.evaluate(
            """() => {
          const f=document.querySelector('[data-player]');
          const vp=document.querySelector('video-player');
          const host=document.querySelector('[data-player-host]');
          const r=f&&f.getBoundingClientRect();
          const vr=vp&&vp.getBoundingClientRect();
          const hr=host&&host.getBoundingClientRect();
          let iframe=null;
          if(vp&&vp.shadowRoot){
            const i=vp.shadowRoot.querySelector('iframe');
            if(i){const ir=i.getBoundingClientRect(); iframe={w:Math.round(ir.width),h:Math.round(ir.height),src:i.src};}
          }
          return {
            state:f&&f.getAttribute('data-state'),
            frame:r&&{w:Math.round(r.width),h:Math.round(r.height)},
            host:hr&&{w:Math.round(hr.width),h:Math.round(hr.height)},
            vp:vr&&{w:Math.round(vr.width),h:Math.round(vr.height)},
            iframe,
            cs: vp ? getComputedStyle(vp).cssText.slice(0,300) : null
          };
        }"""
        )
        if dims.get("frame"):
            await page.mouse.click(
                dims["frame"]["w"] / 2 + 40,
                dims["frame"]["h"] / 2 + 200,
            )
        # try frame click
        for fr in page.frames:
            if "player.cdnvideohub.com" in (fr.url or ""):
                try:
                    await fr.click("body", timeout=2000, position={"x": 200, "y": 120})
                except Exception as e:
                    msgs.append({"type": "frame_click_err", "text": str(e)[:200]})
        await page.wait_for_timeout(12000)
        pm = await page.evaluate("window.__pm || []")
        final = await page.evaluate(
            """() => {
          const f=document.querySelector('[data-player]');
          const vp=document.querySelector('video-player');
          let iframe=null, open=null;
          if(vp&&vp.shadowRoot){
            const i=vp.shadowRoot.querySelector('iframe');
            const d=vp.shadowRoot.querySelector('dialog');
            if(i){const ir=i.getBoundingClientRect(); iframe={w:Math.round(ir.width),h:Math.round(ir.height)};}
            if(d) open=d.open;
          }
          const r=f&&f.getBoundingClientRect();
          return {state:f&&f.getAttribute('data-state'),
            frame:r&&{w:Math.round(r.width),h:Math.round(r.height),ratio:+(r.width/Math.max(r.height,1)).toFixed(3)},
            iframe, dialogOpen:open, st:(document.querySelector('[data-player-state]:not([hidden])')||{}).innerText};
        }"""
        )
        await browser.close()
    report = {
        "early_dims": dims,
        "final": final,
        "postMessages": pm[:30],
        "media_reqs": media[:30],
        "notes": msgs[:20],
    }
    (OUT / "aida-iframe-hls.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2)[:4000])


if __name__ == "__main__":
    asyncio.run(main())
