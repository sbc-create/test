"""Visual + layout metrics for Zona PASS2."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

OUT = Path("/home/claude/wt-zona-finalization-01/artifacts/evidence/zona-pass2-2026-09-19/screenshots")
OUT.mkdir(parents=True, exist_ok=True)
BASE = "https://zonafilm.space"

PAGES = [
    ("home", "/"),
    ("search", "/search/?q=%D0%B7%D0%B2%D0%B5%D0%B7%D0%B4%D0%BD%D1%8B%D0%B5%20%D0%B2%D0%BE%D0%B9%D0%BD%D1%8B"),
    ("vl", "/title/v-lovushke/"),
    ("voy", "/title/voy-2/"),
    ("aida", "/title/aida-vozvraschaetsya/"),
    ("unavail", "/title/1999-otdel-protivodeystviya-okkultizmu/season-1/episode-12/"),
    ("catalog", "/catalog/"),
]

VIEWPORTS = [("1440", 1440, 900), ("768", 768, 1024), ("390", 390, 844)]


async def main() -> None:
    metrics = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        for vp_name, w, h in VIEWPORTS:
            ctx = await browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=1)
            page = await ctx.new_page()
            for pname, path in PAGES:
                await page.goto(BASE + path, wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(900)
                shot = OUT / f"{pname}-{vp_name}.png"
                await page.screenshot(path=str(shot), full_page=False)
                m = await page.evaluate(
                    """() => {
                      const doc = document.documentElement;
                      const body = document.body;
                      const hd = document.querySelector('.zhd');
                      const main = document.querySelector('.zmain, main');
                      const pl = document.querySelector('[data-player]');
                      const host = document.querySelector('[data-player-host], video-player');
                      const footer = document.querySelector('.zft');
                      const title = document.querySelector('.ztitle');
                      const dl = document.querySelector('.ztitle__dl');
                      function rect(el){ if(!el) return null; const r=el.getBoundingClientRect();
                        return {t:Math.round(r.top),l:Math.round(r.left),w:Math.round(r.width),h:Math.round(r.height)}; }
                      const hdr = rect(hd);
                      const mainR = rect(main);
                      let stickyOverlap = 0;
                      if(hdr && title){
                        const tr = title.getBoundingClientRect();
                        stickyOverlap = Math.max(0, Math.round(hdr.bottom - tr.top));
                      }
                      // label/value overlaps in dl
                      let overlaps = 0;
                      if(dl){
                        const rows = dl.querySelectorAll('div');
                        rows.forEach(row => {
                          const dt=row.querySelector('dt'); const dd=row.querySelector('dd');
                          if(!dt||!dd) return;
                          const a=dt.getBoundingClientRect(), b=dd.getBoundingClientRect();
                          if(a.right > b.left + 1 && a.bottom > b.top + 1 && b.bottom > a.top + 1) overlaps++;
                        });
                      }
                      const pr = rect(pl); const hr = rect(host);
                      let coverage = null, ratio = null;
                      if(pr && hr && pr.w && pr.h){
                        coverage = Math.round(100 * (hr.w*hr.h) / (pr.w*pr.h));
                        ratio = +(pr.w / Math.max(pr.h,1)).toFixed(3);
                      }
                      // card row heights
                      const cards = [...document.querySelectorAll('.zg .zt')].slice(0,14);
                      const heights = cards.map(c => Math.round(c.getBoundingClientRect().height));
                      let delta = 0;
                      if(heights.length){ delta = Math.max(...heights)-Math.min(...heights); }
                      const descDup = (document.body.innerText.match(/О чём это/g)||[]).length;
                      return {
                        overflowX: Math.max(0, doc.scrollWidth - doc.clientWidth),
                        stickyOverlap,
                        metadataOverlaps: overlaps,
                        player: pr, host: hr, coverage, ratio,
                        footer: rect(footer),
                        cardDelta: delta,
                        samePageDescSections: descDup,
                        state: pl && pl.getAttribute('data-state'),
                      };
                    }"""
                )
                # search ranking sample
                ranking = None
                if pname == "search":
                    ranking = await page.evaluate(
                        """() => [...document.querySelectorAll('.zt__t')].slice(0,12).map(e=>e.textContent.trim())"""
                    )
                metrics.append({
                    "page": pname, "viewport": vp_name, "path": path,
                    "shot": str(shot), **m, "search_top": ranking,
                })
            await ctx.close()
        await browser.close()
    summary = {
        "STICKY_HEADER_OVERLAP_PX": max(x.get("stickyOverlap") or 0 for x in metrics),
        "METADATA_LABEL_VALUE_OVERLAPS": max(x.get("metadataOverlaps") or 0 for x in metrics),
        "HORIZONTAL_OVERFLOW_PX": max(x.get("overflowX") or 0 for x in metrics),
        "CARD_ROW_MAX_HEIGHT_DELTA_PX": max(x.get("cardDelta") or 0 for x in metrics),
        "PLAYER_STAGE_RATIO": next((x.get("ratio") for x in metrics if x["page"]=="aida" and x["viewport"]=="1440"), None),
        "PLAYER_CHILD_COVERAGE": next((x.get("coverage") for x in metrics if x["page"]=="aida" and x["viewport"]=="1440"), None),
        "SEARCH_TOP_1440": next((x.get("search_top") for x in metrics if x["page"]=="search" and x["viewport"]=="1440"), None),
        "items": metrics,
    }
    Path(OUT.parent / "visual-metrics.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: summary[k] for k in summary if k != "items"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
