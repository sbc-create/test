"""Inspect plapi playlist/video payloads and player shadow DOM."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

URL = "https://zonafilm.space/title/aida-vozvraschaetsya/"
OUT = Path("/home/claude/wt-zona-finalization-01/artifacts/evidence/zona-pass2-2026-09-19")


async def main() -> None:
    payloads = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await ctx.new_page()

        async def on_resp(r):
            u = r.url
            if "/sv/playlist" in u or "/sv/video/" in u:
                try:
                    body = await r.text()
                except Exception as e:
                    body = f"<err {e}>"
                payloads.append(
                    {
                        "status": r.status,
                        "url": u[:220],
                        "ct": (r.headers or {}).get("content-type", ""),
                        "body_head": (body or "")[:1200],
                        "body_len": len(body or ""),
                    }
                )

        page.on("response", on_resp)
        await page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)
        # Force a generous player size before click
        await page.evaluate(
            """() => {
          const f=document.querySelector('[data-player]');
          if(f){ f.style.minHeight='640px'; f.style.aspectRatio='16/9'; }
        }"""
        )
        box = await page.evaluate(
            """() => {
          const f=document.querySelector('[data-player]');
          if(!f) return null;
          const r=f.getBoundingClientRect();
          return {x:r.x+r.width/2,y:r.y+Math.min(r.height,400)/2,w:r.width,h:r.height};
        }"""
        )
        if box:
            await page.mouse.click(box["x"], box["y"])
        await page.wait_for_timeout(10000)
        deep = await page.evaluate(
            """() => {
          function walk(root, depth){
            if(!root || depth>5) return [];
            const out=[];
            const nodes=root.querySelectorAll ? root.querySelectorAll('*') : [];
            for(const n of nodes){
              const tag=n.tagName;
              if(['VIDEO','IFRAME','IMG','BUTTON','VIDEO-PLAYER'].includes(tag)){
                const r=n.getBoundingClientRect();
                out.push({tag, cls:n.className&&String(n.className).slice(0,80),
                  w:Math.round(r.width),h:Math.round(r.height),
                  src:(n.src||n.getAttribute('src')||'').slice(0,160),
                  text:(n.innerText||'').slice(0,120)});
              }
              if(n.shadowRoot) out.push(...walk(n.shadowRoot, depth+1));
            }
            return out;
          }
          const vp=document.querySelector('video-player');
          return {
            state: document.querySelector('[data-player]')?.getAttribute('data-state'),
            frame: (()=>{const r=document.querySelector('[data-player]')?.getBoundingClientRect();
              return r?{w:Math.round(r.width),h:Math.round(r.height)}:null;})(),
            nodes: walk(document, 0).slice(0,40),
            shadowHTML: vp && vp.shadowRoot ? vp.shadowRoot.innerHTML.slice(0,2500) : null
          };
        }"""
        )
        await browser.close()
    report = {"payloads": payloads, "deep": deep}
    (OUT / "aida-payload-shadow.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "n_payloads": len(payloads),
        "payload_urls": [p["url"] for p in payloads],
        "body_heads": [p["body_head"][:400] for p in payloads],
        "state": deep.get("state"),
        "frame": deep.get("frame"),
        "nodes": deep.get("nodes"),
        "shadow_head": (deep.get("shadowHTML") or "")[:600],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
