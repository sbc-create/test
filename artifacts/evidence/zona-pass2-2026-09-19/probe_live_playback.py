"""Probe live Zona playback for PASS2 root-cause evidence."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

URLS = [
    ("vl", "https://zonafilm.space/title/v-lovushke/"),
    ("voy", "https://zonafilm.space/title/voy-2/"),
    ("aida", "https://zonafilm.space/title/aida-vozvraschaetsya/"),
]


async def probe(page, url: str, label: str) -> dict:
    net = []

    def on_resp(r):
        u = r.url
        if any(x in u for x in ("sv/video", "plapi", "/api/v1/player", "video-player")):
            net.append(
                {
                    "status": r.status,
                    "url": u[:200],
                    "ct": (r.headers or {}).get("content-type", ""),
                }
            )

    page.on("response", on_resp)
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)[:220]))
    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(2500)
    # click center of player frame
    box = await page.evaluate(
        """() => {
      const f=document.querySelector('[data-player]');
      if(!f) return null;
      const r=f.getBoundingClientRect();
      return {x:r.x+r.width/2,y:r.y+r.height/2,w:r.width,h:r.height};
    }"""
    )
    if box and box.get("w", 0) > 40:
        await page.mouse.click(box["x"], box["y"])
    await page.wait_for_timeout(14000)
    info = await page.evaluate(
        """() => {
      const f=document.querySelector('[data-player]');
      const vp=document.querySelector('video-player');
      let shadow={};
      if(vp && vp.shadowRoot){
        const v=vp.shadowRoot.querySelector('video');
        const img=vp.shadowRoot.querySelector('img');
        shadow={
          hasVideo:!!v, hasImg:!!img,
          video: v ? {paused:v.paused,t:v.currentTime,rs:v.readyState,w:v.videoWidth,h:v.videoHeight} : null,
          img: img ? {w:img.naturalWidth,h:img.naturalHeight,src:(img.src||'').slice(0,140)} : null
        };
      }
      const r=f?f.getBoundingClientRect():null;
      const st=document.querySelector('[data-player-state]:not([hidden])');
      return {
        state: f && f.getAttribute('data-state'),
        label: (document.querySelector('.zpl__h span')||{}).textContent || '',
        frame: r ? {w:Math.round(r.width),h:Math.round(r.height),ratio:+(r.width/Math.max(r.height,1)).toFixed(3)} : null,
        agg: vp && vp.getAttribute('data-aggregator'),
        tid: vp && vp.getAttribute('data-title-id'),
        banner: vp && vp.getAttribute('is-show-banner'),
        stText: st ? (st.innerText||'').slice(0,240) : '',
        shadow,
        zonaPlaying: window.__zonaPlayerPlaying || null
      };
    }"""
    )
    return {"label": label, "info": info, "vid_reqs": net[:20], "errs": errs[:8]}


async def main() -> None:
    out = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        for label, url in URLS:
            ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
            page = await ctx.new_page()
            try:
                out.append(await probe(page, url, label))
            except Exception as e:
                out.append({"label": label, "error": str(e)[:300]})
            await ctx.close()
        await browser.close()
    path = Path("/home/claude/wt-zona-finalization-01/artifacts/evidence/zona-pass2-2026-09-19")
    path.mkdir(parents=True, exist_ok=True)
    (path / "before-live-playback-probe.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps([{k: (v if k != "vid_reqs" else v[:5]) for k, v in row.items()} for row in out], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
