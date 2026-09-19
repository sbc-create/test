"""PASS3 visual QA + screenshots across required widths."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

OUT = Path("/home/claude/wt-zona-finalization-01/artifacts/evidence/zona-pass3-2026-09-19")
SHOTS = OUT / "screenshots"
SHOTS.mkdir(parents=True, exist_ok=True)
BASE = "https://zonafilm.space"

PAGES = [
    ("home", "/"),
    ("title-summary", "/title/chasha-vesny/"),
    ("episodes", "/title/chasha-vesny/"),
    ("related", "/title/chasha-vesny/"),
    ("seo-block", "/"),
    ("footer", "/"),
    ("collections", "/collections/"),
]

VIEWPORTS = [
    ("2048", 2048, 1100),
    ("1440", 1440, 900),
    ("768", 768, 1024),
    ("390", 390, 844),
]


async def metrics(page) -> dict:
    return await page.evaluate(
        """() => {
          const doc=document.documentElement;
          const cards=[...document.querySelectorAll('.zrl__track .zt, .zg .zt')].slice(0,20);
          const heights=cards.map(c=>Math.round(c.getBoundingClientRect().height));
          const delta=heights.length?Math.max(...heights)-Math.min(...heights):0;
          const track=document.querySelector('.zrl__vp');
          let clipped=0;
          if(track){
            const tr=track.getBoundingClientRect();
            [...track.querySelectorAll('.zt')].forEach(c=>{
              const r=c.getBoundingClientRect();
              if(r.right>tr.right+2 && r.left<tr.right-8) clipped++;
            });
          }
          const genreLinks=[...document.querySelectorAll('.zgenres__nav a')].map(a=>a.getAttribute('href'));
          const epsDisabled=[...document.querySelectorAll('.zeps [aria-disabled="true"]')].length;
          const epsLinks=[...document.querySelectorAll('.zeps a')].length;
          const related=[...document.querySelectorAll('.zsec .zrl__track .zt, .zsec .zt')];
          const relatedHrefs=related.map(a=>a.getAttribute('href'));
          const relatedDup=relatedHrefs.length-new Set(relatedHrefs).size;
          const countsLeak=/\\d{4,}\\s*запис/i.test(document.body.innerText);
          const jargon=/утверждённого снимка каталога/i.test(document.body.innerText);
          const title=document.querySelector('.ztitle');
          const watch=document.querySelector('#watch, .zpl');
          let titleH=null, gap=null;
          if(title){ titleH=Math.round(title.getBoundingClientRect().height); }
          if(title&&watch){
            gap=Math.round(watch.getBoundingClientRect().top-title.getBoundingClientRect().bottom);
          }
          return {
            overflowX: Math.max(0, doc.scrollWidth-doc.clientWidth),
            pageHeight: doc.scrollHeight,
            cardDelta: delta,
            clippedCards: clipped,
            genreLinks,
            epsDisabled, epsLinks,
            relatedCount: relatedHrefs.length,
            relatedDup,
            countsLeak, jargon,
            titleHeight: titleH,
            titleToWatchGap: gap,
            contactMissing: document.querySelector('[data-contact-config-missing="1"]')?1:0,
            build: document.documentElement.getAttribute('data-build-id'),
            noHorizontalScrollbar: doc.scrollWidth<=doc.clientWidth,
          };
        }"""
    )


async def shot_player(page, name: str, wname: str, playing: bool) -> None:
    path = "/title/chasha-vesny/season-1/episode-1/"
    await page.goto(BASE + path, wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(1500)
    if playing:
        box = await page.evaluate(
            """() => {
              const f=document.querySelector('[data-player]');
              if(!f) return null;
              const r=f.getBoundingClientRect();
              return {x:r.x+r.width/2,y:r.y+Math.max(40,r.height/2)};
            }"""
        )
        if box:
            await page.mouse.click(box["x"], box["y"])
        await page.wait_for_timeout(35000)
    else:
        await page.wait_for_timeout(800)
    await page.locator('[data-player]').screenshot(
        path=str(SHOTS / f"{name}-{wname}.png")
    )


async def main() -> None:
    all_metrics = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        for wname, w, h in VIEWPORTS:
            ctx = await browser.new_context(viewport={"width": w, "height": h})
            page = await ctx.new_page()
            for pname, path in PAGES:
                await page.goto(BASE + path, wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(900)
                if pname == "seo-block":
                    await page.evaluate(
                        "() => { const el=document.querySelector('.zsec--seo');"
                        "if(el) el.scrollIntoView(); }"
                    )
                    await page.wait_for_timeout(300)
                    el = page.locator(".zsec--seo")
                    if await el.count():
                        await el.screenshot(path=str(SHOTS / f"seo-block-{wname}.png"))
                elif pname == "footer":
                    await page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
                    await page.wait_for_timeout(300)
                    el = page.locator(".zft")
                    if await el.count():
                        await el.screenshot(path=str(SHOTS / f"footer-{wname}.png"))
                elif pname == "episodes":
                    await page.evaluate(
                        "() => { const el=document.querySelector('.zeps');"
                        "if(el) el.scrollIntoView(); }"
                    )
                    await page.wait_for_timeout(300)
                    el = page.locator(".zeps").first
                    if await el.count():
                        await el.screenshot(path=str(SHOTS / f"episodes-{wname}.png"))
                elif pname == "related":
                    await page.evaluate(
                        "() => { const els=[...document.querySelectorAll('.zsec')];"
                        "const t=els.find(e=>/Смотрите также/i.test(e.innerText));"
                        "if(t) t.scrollIntoView(); }"
                    )
                    await page.wait_for_timeout(300)
                    await page.screenshot(path=str(SHOTS / f"related-{wname}.png"), full_page=False)
                elif pname == "title-summary":
                    el = page.locator(".ztitle")
                    if await el.count():
                        await el.screenshot(path=str(SHOTS / f"title-summary-{wname}.png"))
                    else:
                        await page.screenshot(path=str(SHOTS / f"title-summary-{wname}.png"))
                else:
                    await page.screenshot(path=str(SHOTS / f"{pname}-{wname}.png"), full_page=False)
                m = await metrics(page)
                m.update({"page": pname, "viewport": wname})
                all_metrics.append(m)

            # player before / after 35s — only at 1440 to save time, plus 390
            if wname in {"1440", "390"}:
                await shot_player(page, "player-before-play", wname, playing=False)
                await shot_player(page, "player-playing-after-35s", wname, playing=True)

            await ctx.close()
        await browser.close()

    (OUT / "visual-metrics.json").write_text(
        json.dumps(all_metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    # Aggregate gates
    home = [m for m in all_metrics if m["page"] == "home"]
    gates = {
        "NATIVE_SCROLLBAR_VISIBLE": 0 if all(m.get("noHorizontalScrollbar") for m in home) else 1,
        "HORIZONTAL_OVERFLOW_MAX": max((m.get("overflowX") or 0) for m in home),
        "PAGE_HEIGHT_HOME_2048": next((m.get("pageHeight") for m in home if m["viewport"]=="2048"), None),
        "CLIPPED_CARD_MAX": max((m.get("clippedCards") or 0) for m in all_metrics),
        "CARD_DELTA_MAX": max((m.get("cardDelta") or 0) for m in all_metrics),
        "COUNTS_LEAK": any(m.get("countsLeak") for m in all_metrics),
        "JARGON": any(m.get("jargon") for m in all_metrics),
        "CONTACT_CONFIG_MISSING": max((m.get("contactMissing") or 0) for m in all_metrics),
    }
    (OUT / "visual-gates.json").write_text(
        json.dumps(gates, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(gates, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
