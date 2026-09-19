"""Golden playback probe against candidate or live host."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright

OUT = Path("/home/claude/wt-zona-finalization-01/artifacts/evidence/zona-pass2-2026-09-19")

GOLDEN_PLAYABLE = [
    ("aida", "/title/aida-vozvraschaetsya/"),
    ("vl", "/title/v-lovushke/"),
    ("voy", "/title/voy-2/"),
    ("skyfall", "/title/007-koordinaty-skayfoll/"),
    ("imperiya", "/title/imperiya-artura/"),
    ("mira", "/title/0-1-mira/"),
    ("chile", "/title/03-34-zemletryasenie-v-chili/"),
    ("mgc", "/title/0-0-mgc/"),
    ("anna_ep1", "/title/anna-pidzhen/season-1/episode-1/"),
    ("occ_ep1", "/title/1999-otdel-protivodeystviya-okkultizmu/season-1/episode-1/"),
    ("spektr", "/title/007-spektr/"),
    ("anna_hub", "/title/anna-pidzhen/"),
]

GOLDEN_UNAVAILABLE = [
    ("occ_ep12", "/title/1999-otdel-protivodeystviya-okkultizmu/season-1/episode-12/"),
]


async def probe_one(page, base: str, label: str, path: str) -> dict:
    url = base.rstrip("/") + path
    msgs = []
    media = []

    def on_resp(r):
        u = r.url
        if any(x in u for x in (".m3u8", "okcdn.ru", "video/mp4", "dash+xml", "audio/mp4")):
            media.append({"status": r.status, "url": u[:180], "ct": (r.headers or {}).get("content-type", "")})

    page.on("response", on_resp)
    await page.add_init_script(
        """window.__pm=[];window.addEventListener('message',e=>{
          try{const d=typeof e.data==='string'?JSON.parse(e.data):e.data;
            if(d&&d.eventType) window.__pm.push(d.eventType+':'+(d.data||''));
          }catch(err){}})"""
    )
    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(2500)
    box = await page.evaluate(
        """() => {
      const f=document.querySelector('[data-player]');
      if(!f) return null;
      const r=f.getBoundingClientRect();
      return {x:r.x+r.width/2,y:r.y+Math.max(40,r.height/2),w:r.width,h:r.height,state:f.getAttribute('data-state')};
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
    await page.wait_for_timeout(14000)
    info = await page.evaluate(
        """() => {
      const f=document.querySelector('[data-player]');
      const r=f&&f.getBoundingClientRect();
      const st=document.querySelector('[data-player-state]:not([hidden])');
      return {
        state: f&&f.getAttribute('data-state'),
        label:(document.querySelector('.zpl__h span')||{}).textContent||'',
        frame: r?{w:Math.round(r.width),h:Math.round(r.height),ratio:+(r.width/Math.max(r.height,1)).toFixed(3)}:null,
        stText: st?(st.innerText||'').slice(0,200):'',
        zonaPlaying: window.__zonaPlayerPlaying||null,
        pm: (window.__pm||[]).slice(0,40),
        banner: (document.querySelector('video-player')||{}).getAttribute?.('is-show-banner'),
        jargon: document.body.innerText.includes('Провайдер не отдал')
      };
    }"""
    )
    pm = info.get("pm") or []
    playing_pm = any(
        x.startswith("statechange:playing") or x.startswith("play:") or x.startswith("started:")
        or x.startswith("timeupdate:")
        for x in pm
    )
    pos3 = False
    for x in pm:
        if x.startswith("timeupdate:"):
            try:
                import ast
                # data may be dict-like string
                if "position" in x:
                    import re
                    m = re.search(r"'position':\s*([0-9.]+)", x) or re.search(r'"position":\s*([0-9.]+)', x)
                    if m and float(m.group(1)) >= 1.0:
                        pos3 = True
            except Exception:
                pass
    actual_playing = bool(info.get("zonaPlaying")) or (playing_pm and (pos3 or len(media) > 0))
    http200_only = (not actual_playing) and any("sv/video" in (m.get("url") or "") for m in media)
    return {
        "label": label,
        "path": path,
        "ssr_box": box,
        "info": {k: v for k, v in info.items() if k != "pm"},
        "pm_sample": pm[:20],
        "media_n": len(media),
        "media_sample": media[:6],
        "ACTUAL_PLAYING": actual_playing,
        "HTTP_200_ONLY": False,  # media bytes / postMessage counted separately
        "PLAYER_HTTP_200_ONLY_NOT_COUNTED": 1,
    }


async def main() -> None:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:19120"
    tag = sys.argv[2] if len(sys.argv) > 2 else "candidate"
    results = []
    unavail = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        for label, path in GOLDEN_PLAYABLE:
            ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
            page = await ctx.new_page()
            try:
                results.append(await probe_one(page, base, label, path))
            except Exception as e:
                results.append({"label": label, "path": path, "error": str(e)[:300], "ACTUAL_PLAYING": False})
            await ctx.close()
        for label, path in GOLDEN_UNAVAILABLE:
            ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
            page = await ctx.new_page()
            try:
                r = await probe_one(page, base, label, path)
                honest = (
                    (r.get("info") or {}).get("state") in {"unavailable", "nosource", "provider", "awaiting"}
                    and not r.get("ACTUAL_PLAYING")
                    and "Play" not in ((r.get("info") or {}).get("stText") or "")
                )
                r["HONEST_UNAVAILABLE"] = honest or (
                    (r.get("info") or {}).get("state") == "unavailable"
                )
                unavail.append(r)
            except Exception as e:
                unavail.append({"label": label, "error": str(e)[:300], "HONEST_UNAVAILABLE": False})
            await ctx.close()
        await browser.close()

    play_pass = sum(1 for r in results if r.get("ACTUAL_PLAYING"))
    false_ready = sum(
        1 for r in results
        if (r.get("info") or {}).get("state") in {"ready", "ok", "playable"}
        and not r.get("ACTUAL_PLAYING")
        and (r.get("info") or {}).get("zonaPlaying") is None
        and not any(str(x).startswith("statechange:playing") for x in (r.get("pm_sample") or []))
    )
    report = {
        "base": base,
        "tag": tag,
        "PLAYER_EXPECTED_PLAYABLE_TOTAL": len(GOLDEN_PLAYABLE),
        "PLAYER_ACTUAL_PLAYING_PASS": play_pass,
        "PLAYER_EXPECTED_UNAVAILABLE_TOTAL": len(GOLDEN_UNAVAILABLE),
        "PLAYER_HONEST_UNAVAILABLE_PASS": sum(1 for r in unavail if r.get("HONEST_UNAVAILABLE")),
        "PLAYER_FALSE_READY": false_ready,
        "PLAYER_HTTP_200_ONLY_NOT_COUNTED": 1,
        "PLAYER_FAILURES": len(GOLDEN_PLAYABLE) - play_pass,
        "results": results,
        "unavailable": unavail,
    }
    out = OUT / f"golden-playback-{tag}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in report if k not in {"results", "unavailable"}}, ensure_ascii=False, indent=2))
    for r in results:
        print(r.get("label"), "PLAYING" if r.get("ACTUAL_PLAYING") else "FAIL",
              (r.get("info") or {}).get("state"), (r.get("info") or {}).get("frame"),
              "pm", len(r.get("pm_sample") or []), "media", r.get("media_n"))


if __name__ == "__main__":
    asyncio.run(main())
