#!/usr/bin/env python3
"""Pass5 dual live QA + screenshots + smoke."""
from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import re
import ssl
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright

BASE = "https://zonafilm.space"
OUT = Path("/home/claude/wt-zona-finalization-01/artifacts/evidence/zona-pass5-2026-09-19")
CTX = ssl.create_default_context()
SUSPICIOUS = (2003, 2010, 2013, 2018, 2019, 2026)


def fetch(path: str):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "zona-pass5-qa"})
    with urllib.request.urlopen(req, timeout=60, context=CTX) as r:
        return r.status, dict(r.headers.items()), r.read().decode("utf-8", "replace")


def digest(titles):
    return hashlib.sha256("|".join(titles).encode()).hexdigest()[:16]


def page_metrics(path: str) -> dict:
    st, h, b = fetch(path)
    titles = re.findall(r'class="zt__t"[^>]*>([^<]+)', b)
    total_m = re.search(r"Результаты:\s*(\d+)", b)
    h1m = re.search(r"<h1[^>]*>(.*?)</h1>", b, re.S)
    h1 = re.sub("<[^>]+>", "", h1m.group(1)).strip() if h1m else ""
    years_in_select = re.findall(r'<option[^>]*>\s*(\d{4})\s*\(', b)
    return {
        "path": path,
        "status": st,
        "build": h.get("X-Site-Factory-Build-Id"),
        "artifact": h.get("X-Site-Factory-Artifact-Sha256"),
        "h1": h1,
        "total": int(total_m.group(1)) if total_m else None,
        "cards": len(titles),
        "titles_digest": digest(titles),
        "has_year_select": "zona-year-facet" in b,
        "year_options_sample": years_in_select[:5] + years_in_select[-3:],
        "year_option_count": len(years_in_select),
        "placeholder": ("Разделы появятся" in b or "Документы не опубликованы" in b),
        "contact_missing": 'data-contact-config-missing="1"' in b,
        "footer_link_cols": b.count("zft__col--links"),
        "has_facts": 'data-testid="title-facts"' in b,
        "noindex": "noindex" in (h.get("X-Robots-Tag") or "") or 'content="noindex' in b,
        "kp_label": "КП" in b,
        "old_year_1990s": bool(re.search(r"199[0-9]|198[0-9]", b)),
    }


def run_smoke(run_id: int) -> dict:
    paths = [
        "/", "/movies/", "/series/", "/animation/", "/catalog/", "/new/",
        "/collections/", "/title/chasha-vesny/",
        "/series/?year=2019", "/movies/?year=2019", "/catalog/?year=2019",
        "/catalog/?year=2003", "/catalog/?year=2010", "/catalog/?year=2013",
        "/catalog/?year=2018", "/catalog/?year=2026",
        "/movies/?year=1995",
    ]
    pages = {p: page_metrics(p) for p in paths}
    # pagination union series 2026
    union = []
    st, _, b = fetch("/series/?year=2026")
    total_m = re.search(r"Результаты:\s*(\d+)", b)
    total = int(total_m.group(1)) if total_m else 0
    pages_n = max(1, (total + 28 - 1) // 28) if total else 1
    for pg in (1, 2, max(1, pages_n // 2), pages_n):
        path = "/series/?year=2026" if pg == 1 else f"/series/?year=2026&page={pg}"
        _, _, bb = fetch(path)
        titles = re.findall(r'class="zt__t"[^>]*>([^<]+)', bb)
        union.extend(titles)
    return {
        "run_id": run_id,
        "at": datetime.now(timezone.utc).isoformat(),
        "pages": pages,
        "series_2026_total": total,
        "series_2026_pages": pages_n,
        "series_2026_union_count": len(union),
        "series_2026_union_unique": len(set(union)),
        "build": pages["/"]["build"],
        "artifact": pages["/"]["artifact"],
    }


async def screenshots_and_geometry():
    SHOTS = OUT / "screenshots"
    SHOTS.mkdir(parents=True, exist_ok=True)
    shots = [
        ("home-1920.png", "/", 1920, 1080),
        ("home-1440.png", "/", 1440, 1000),
        ("home-768.png", "/", 768, 1024),
        ("home-390.png", "/", 390, 844),
        ("catalog-1440.png", "/catalog/", 1440, 1000),
        ("catalog-390.png", "/catalog/", 390, 844),
        ("year-2019-1440.png", "/catalog/?year=2019", 1440, 1000),
        ("year-2010-1440.png", "/catalog/?year=2010", 1440, 1000),
        ("year-2003-1440.png", "/catalog/?year=2003", 1440, 1000),
        ("kind-year-1440.png", "/series/?year=2019", 1440, 1000),
        ("title-1440.png", "/title/chasha-vesny/", 1440, 1000),
        ("title-390.png", "/title/chasha-vesny/", 390, 844),
        ("collections-1440.png", "/collections/", 1440, 1000),
        ("footer-1440.png", "/", 1440, 1000),
        ("footer-390.png", "/", 390, 844),
    ]
    geo_rows = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        for name, path, w, h in shots:
            ctx = await browser.new_context(viewport={"width": w, "height": h})
            page = await ctx.new_page()
            try:
                await page.goto(BASE + path, wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(900)
                if "footer" in name:
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await page.wait_for_timeout(300)
                await page.screenshot(path=str(SHOTS / name), full_page=("footer" not in name))
                overflow = await page.evaluate(
                    "()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth+1"
                )
                print("shot", name, overflow)
            except Exception as e:
                print("shot err", name, e)
            await ctx.close()

        for w, h, label in [(1920, 1080, "1920"), (1440, 1000, "1440"),
                            (768, 1024, "768"), (390, 844, "390"), (1280, 900, "1280")]:
            ctx = await browser.new_context(viewport={"width": w, "height": h})
            page = await ctx.new_page()
            await page.goto(BASE + "/movies/", wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(700)
            geo = await page.evaluate(
                """()=>{
                const cards=[...document.querySelectorAll('[data-testid=title-card]')].slice(0,16);
                const widths=cards.map(c=>Math.round(c.getBoundingClientRect().width));
                const heights=cards.map(c=>Math.round(c.getBoundingClientRect().height));
                const posters=cards.map(c=>{const p=c.querySelector('.zt__p');
                  return p?Math.round(p.getBoundingClientRect().height):0});
                const tops={}; for(const c of cards){const t=Math.round(c.getBoundingClientRect().top);
                  tops[t]=(tops[t]||0)+1;}
                const cols=Math.max(...Object.values(tops),0);
                return {cols, widths, heights, posters,
                  overflow:document.documentElement.scrollWidth<=document.documentElement.clientWidth+1,
                  scrollX:window.scrollX};
                }"""
            )
            geo_rows.append({"viewport": label, "path": "/movies/", **geo})
            print("geo", label, geo.get("cols"), geo.get("widths", [])[:3])
            await ctx.close()

        # player shots
        for name, w, h in [("player-playing-1440.png", 1440, 900), ("player-playing-390.png", 390, 844)]:
            ctx = await browser.new_context(viewport={"width": w, "height": h})
            page = await ctx.new_page()
            try:
                await page.goto(BASE + "/title/v-lovushke/", wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(1200)
                box = await page.evaluate(
                    """()=>{const f=document.querySelector('[data-player]');if(!f)return null;
                    const r=f.getBoundingClientRect();return{x:r.x+r.width/2,y:r.y+Math.max(40,r.height/2)};}"""
                )
                if box:
                    await page.mouse.click(box["x"], box["y"])
                for fr in page.frames:
                    if "player.cdnvideohub.com" in (fr.url or ""):
                        try:
                            await fr.click("body", timeout=1200, position={"x": 200, "y": 140})
                        except Exception:
                            pass
                await page.wait_for_timeout(8000)
                await page.screenshot(path=str(SHOTS / name))
                print("shot", name)
            except Exception as e:
                print("player shot err", e)
            await ctx.close()
        await browser.close()
    return geo_rows


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    run1 = run_smoke(1)
    run2 = run_smoke(2)
    stable = (
        run1["build"] == run2["build"]
        and run1["artifact"] == run2["artifact"]
        and run1["series_2026_total"] == run2["series_2026_total"]
        and run1["pages"]["/catalog/?year=2019"]["total"]
        == run2["pages"]["/catalog/?year=2019"]["total"]
        and run1["pages"]["/movies/"]["titles_digest"]
        == run2["pages"]["/movies/"]["titles_digest"]
    )
    (OUT / "LIVE_SMOKE.json").write_text(
        json.dumps({"run1": run1, "run2": run2, "stable": stable},
                   ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    # facet vs oracle
    oracle_years = {}
    with (OUT / "CATALOG_YEAR_COUNTS.csv").open(encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            if row.get("year") and row["year"].isdigit():
                oracle_years[int(row["year"])] = int(row["total"])
    facet = {}
    mismatches = []
    for y in SUSPICIOUS:
        ui = run2["pages"][f"/catalog/?year={y}"]["total"]
        o = oracle_years.get(y)
        facet[str(y)] = {"ui_total": ui, "oracle_total": o, "match": ui == o}
        if ui != o:
            mismatches.append(y)
    (OUT / "FACET_COUNTS.json").write_text(
        json.dumps({"years": facet, "mismatches": mismatches,
                    "year_select_count_movies": run2["pages"]["/movies/"]["year_option_count"]},
                   ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("stable", stable, "build", run2["build"])
    print("2019", facet.get("2019"), "mismatches", mismatches)
    print("year options", run2["pages"]["/movies/"]["year_option_count"])
    geo = asyncio.get_event_loop().run_until_complete(screenshots_and_geometry())
    with (OUT / "CARD_GEOMETRY.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["viewport", "path", "cols", "widths", "heights",
                                          "posters", "overflow", "scrollX"])
        w.writeheader()
        for row in geo:
            w.writerow({
                "viewport": row["viewport"], "path": row["path"], "cols": row.get("cols"),
                "widths": json.dumps(row.get("widths")), "heights": json.dumps(row.get("heights")),
                "posters": json.dumps(row.get("posters")),
                "overflow": row.get("overflow"), "scrollX": row.get("scrollX"),
            })
    print("DONE")


if __name__ == "__main__":
    main()
