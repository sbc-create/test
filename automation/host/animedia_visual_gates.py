#!/usr/bin/env python3
"""Visual + SEO gate screenshots for Animedia (Playwright)."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
EV = ROOT / "artifacts/evidence/animedia-final-repair-2026-09-19b"
EV.mkdir(parents=True, exist_ok=True)

VIEWPORTS = [
    ("1440x900", 1440, 900),
    ("1920x1080", 1920, 1080),
    ("2048x1152", 2048, 1152),
    ("768x1024", 768, 1024),
    ("390x844", 390, 844),
]

PAGES = [
    ("home", "/"),
    ("catalog", "/catalog/"),
    ("search", "/search/?q=%D0%BC%D0%B0%D1%81%D1%82%D0%B5%D1%80"),
    ("title", "/title/master-lda-i-plameni-2/"),
    ("episode", "/title/master-lda-i-plameni-2/season-2/episode-104/"),
]


def measure(page) -> dict:
    return page.evaluate(
        """() => {
      const wrap=document.querySelector('.zwrap');
      const hero=document.querySelector('.ahero');
      const heroCard=document.querySelector('.ahero .zt');
      const heroPoster=document.querySelector('.ahero .zt__p');
      const shelf=document.querySelector('.zsec:not(.zsec--eps)');
      const epsRow=document.querySelector('.zsec--eps .zr');
      const ad=document.querySelector('.zad-home');
      const grid=document.querySelector('.zg');
      const h1s=document.querySelectorAll('h1');
      const overflow=Math.max(0, document.documentElement.scrollWidth - window.innerWidth);
      let cols=0;
      if(grid){
        const st=getComputedStyle(grid).gridTemplateColumns||'';
        cols=st.split(' ').filter(Boolean).length;
      }
      const cardW=heroCard?heroCard.getBoundingClientRect().width:0;
      const poster=heroPoster?heroPoster.getBoundingClientRect():null;
      const aspectErr=poster&&poster.width?
        Math.abs((poster.height/poster.width)-(3/2))/(3/2)*100:0;
      const descCards=[...document.querySelectorAll('.zsec--eps .zr__d')]
        .filter(el=>el.offsetParent!==null && (el.innerText||'').trim().length>80).length;
      return {
        wrapMax: wrap?Math.round(wrap.getBoundingClientRect().width):0,
        heroShellH: hero?Math.round(hero.getBoundingClientRect().height):0,
        heroCardW: Math.round(cardW),
        heroAspectErrPct: Math.round(aspectErr*10)/10,
        shelfH: shelf?Math.round(shelf.getBoundingClientRect().height):0,
        epsRowH: epsRow?Math.round(epsRow.getBoundingClientRect().height):0,
        adH: ad?Math.round(ad.getBoundingClientRect().height):0,
        gridCols: cols,
        h1: h1s.length,
        overflowX: overflow,
        fullDescOnEps: descCards,
        title: document.title,
        h1Text: h1s[0]?h1s[0].innerText.trim().slice(0,120):'',
        seo: (document.querySelector('.zseo p')||{}).innerText||''
      };
    }"""
    )


def main() -> int:
    domains = ["https://animedia.icu", "https://animedia.space"]
    report = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "shots": [], "gates": {}}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for domain in domains:
            host = domain.split("//")[1]
            for vp_name, w, h in VIEWPORTS:
                page = browser.new_page(viewport={"width": w, "height": h})
                for key, path in PAGES:
                    url = domain + path
                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=60000)
                        page.wait_for_timeout(1200)
                        m = measure(page)
                        shot = EV / f"{host}_{key}_{vp_name}.png"
                        page.screenshot(path=str(shot), full_page=False)
                        report["shots"].append({"url": url, "viewport": vp_name, "shot": str(shot), **m})
                    except Exception as exc:  # noqa: BLE001
                        report["shots"].append({"url": url, "viewport": vp_name, "error": str(exc)})
                page.close()
        browser.close()

    # Aggregate gates from desktop home shots
    home_desktop = [s for s in report["shots"]
                    if s.get("url", "").endswith("/") and "home" in str(s.get("shot", ""))
                    and s.get("viewport") in {"1440x900", "1920x1080", "2048x1152"}]
    widths = [s.get("wrapMax", 0) for s in home_desktop if s.get("wrapMax")]
    hero_w = [s.get("heroCardW", 0) for s in home_desktop if s.get("heroCardW")]
    report["gates"] = {
        "HOME_MAX_CONTENT_WIDTH_PX": max(widths) if widths else None,
        "HOME_MAX_CONTENT_WIDTH_OK": bool(widths) and max(widths) <= 1280,
        "HERO_CARD_WIDTH_PX_MIN": min(hero_w) if hero_w else None,
        "HERO_CARD_WIDTH_PX_MAX": max(hero_w) if hero_w else None,
        "HERO_CARD_WIDTH_OK": bool(hero_w) and min(hero_w) >= 150 and max(hero_w) <= 158,
        "HORIZONTAL_PAGE_OVERFLOW_PX": max((s.get("overflowX") or 0) for s in report["shots"] if "overflowX" in s) if report["shots"] else None,
        "H1_COUNT_OK": all(s.get("h1") == 1 for s in report["shots"] if "h1" in s),
        "SCREENSHOTS": len([s for s in report["shots"] if s.get("shot")]),
    }
    # Domain SEO uniqueness
    icu_seo = next((s.get("seo") for s in report["shots"] if "animedia.icu" in s.get("url", "") and s.get("seo")), "")
    space_seo = next((s.get("seo") for s in report["shots"] if "animedia.space" in s.get("url", "") and s.get("seo")), "")
    report["gates"]["SAME_SEO_TEXT_BETWEEN_DOMAINS"] = int(bool(icu_seo and space_seo and icu_seo == space_seo))
    report["gates"]["SAME_FIRST_VIEWPORT_H1"] = int(
        next((s.get("h1Text") for s in report["shots"] if "animedia.icu" in s.get("url","") and s.get("viewport")=="1440x900" and "/'" not in s.get("url","") and s.get("url","").rstrip("/").endswith("icu")), "")
        ==
        next((s.get("h1Text") for s in report["shots"] if "animedia.space" in s.get("url","") and s.get("viewport")=="1440x900" and s.get("url","").rstrip("/").endswith("space")), "")
    )
    # Simpler H1 compare
    h1_icu = next((s.get("h1Text") for s in report["shots"]
                   if s.get("url") == "https://animedia.icu/" and s.get("viewport") == "1440x900"), "")
    h1_space = next((s.get("h1Text") for s in report["shots"]
                     if s.get("url") == "https://animedia.space/" and s.get("viewport") == "1440x900"), "")
    report["gates"]["SAME_FIRST_VIEWPORT_CONTENT"] = int(bool(h1_icu and h1_icu == h1_space))
    out = EV / "VISUAL_GATES.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["gates"], ensure_ascii=False, indent=2))
    ok = (
        report["gates"].get("HOME_MAX_CONTENT_WIDTH_OK")
        and report["gates"].get("HERO_CARD_WIDTH_OK")
        and report["gates"].get("HORIZONTAL_PAGE_OVERFLOW_PX") == 0
        and report["gates"].get("H1_COUNT_OK")
        and report["gates"].get("SAME_SEO_TEXT_BETWEEN_DOMAINS") == 0
        and report["gates"].get("SAME_FIRST_VIEWPORT_CONTENT") == 0
        and report["gates"].get("SCREENSHOTS", 0) > 20
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
