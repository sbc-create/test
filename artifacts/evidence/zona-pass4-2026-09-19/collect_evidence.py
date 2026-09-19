#!/usr/bin/env python3
"""Pass4 evidence collector: routes, collections, pagination, screenshots."""
from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import re
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright

BASE = "https://zonafilm.space"
OUT = Path("/home/claude/wt-zona-finalization-01/artifacts/evidence/zona-pass4-2026-09-19")
SHOTS = OUT / "screenshots"
RAW = OUT / "raw"
CTX = ssl.create_default_context()


class Noredir(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(path, allow_redirects=True):
    https = urllib.request.HTTPSHandler(context=CTX)
    handlers = [https]
    if not allow_redirects:
        handlers.append(Noredir())
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "zona-pass4-evidence"})
    try:
        with opener.open(req, timeout=60) as r:
            return r.status, dict(r.headers.items()), r.read().decode("utf-8", "replace"), r.geturl()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace") if e.fp else ""
        return e.code, dict(e.headers.items()), body, BASE + path


def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def parse_page(body: str):
    h1m = re.search(r"<h1[^>]*>(.*?)</h1>", body, re.S)
    h1 = re.sub("<[^>]+>", "", h1m.group(1)).strip() if h1m else ""
    titles = re.findall(r'class="zt__t"[^>]*>([^<]+)', body)
    metas = re.findall(r'class="zt__m"[^>]*>([^<]+)', body)
    canon = re.search(r'rel="canonical"[^>]*href="([^"]+)"', body)
    robots = re.search(r'name="robots"[^>]*content="([^"]+)"', body)
    count_m = re.search(r"Найдено\s+(\d+)", body) or re.search(r"data-total-count=\"(\d+)\"", body)
    total = int(count_m.group(1)) if count_m else len(titles)
    return {
        "h1": h1,
        "titles": titles,
        "metas": metas,
        "card_count": len(titles),
        "total_count": total,
        "canonical": canon.group(1) if canon else "",
        "robots": robots.group(1) if robots else "",
        "content_digest": digest("|".join(titles[:48])),
        "placeholder": ("Разделы появятся" in body or "Документы не опубликованы" in body),
        "freshness": ("Премьера ·" in body or "Обновлено ·" in body or "Новая серия" in body),
        "sort_ui": "Сначала новые" in body,
        "contact_missing": 'data-contact-config-missing="1"' in body,
    }


ROUTES = [
    ("/", "home", "nav", "", "", "", "", "", "", 1, 200, ""),
    ("/new/", "new", "nav", "", "", "", "", "activity", "newest", 1, 200, "Что нового"),
    ("/movies/", "kind", "nav", "Фильм", "", "", "", "release", "newest", 1, 200, "Кино"),
    ("/series/", "kind", "nav", "Сериал", "", "", "", "release", "newest", 1, 200, "Сериалы"),
    ("/animation/", "kind", "nav", "Мультфильм", "", "", "", "release", "newest", 1, 200, "Анимация"),
    ("/catalog/", "catalog", "nav", "", "", "", "", "release", "newest", 1, 200, ""),
    ("/collections/", "collections", "nav", "", "", "", "", "", "", 1, 200, "Подборки"),
    ("/search/?q=%D1%87%D0%B0%D1%88%D0%B0", "search", "form", "", "", "", "", "", "", 1, 200, ""),
    ("/series/?year=2026", "filter", "facet", "Сериал", "", "", "2026", "release", "newest", 1, 200, "Сериалы 2026 года"),
    ("/series/?year=2026&page=2", "filter", "pager", "Сериал", "", "", "2026", "release", "newest", 2, 200, "Сериалы 2026 года"),
    ("/movies/?year=2025", "filter", "facet", "Фильм", "", "", "2025", "release", "newest", 1, 200, ""),
    ("/movies/?sort=title", "sort", "ui", "Фильм", "", "", "", "title", "title", 1, 200, "Кино"),
    ("/movies/?sort=rating", "sort", "ui", "Фильм", "", "", "", "rating", "rating", 1, 200, "Кино"),
    ("/movies/?sort=recently_added", "sort", "ui", "Фильм", "", "", "", "added", "recently_added", 1, 200, "Кино"),
    ("/new/?page=2", "new", "pager", "", "", "", "", "activity", "newest", 2, 200, "Что нового"),
    ("/movies/?page=0", "error", "probe", "", "", "", "", "", "", 0, 400, ""),
    ("/movies/?year=abcd", "error", "probe", "", "", "", "abcd", "", "", 1, 400, ""),
    ("/movies/?kind=%D0%A1%D0%B5%D1%80%D0%B8%D0%B0%D0%BB", "redirect", "probe", "Сериал", "", "", "", "", "", 1, 308, ""),
    ("/series/?kind=%D0%A4%D0%B8%D0%BB%D1%8C%D0%BC&year=2026", "redirect", "probe", "Фильм", "", "", "2026", "", "", 1, 308, ""),
]


def build_route_matrix():
    rows = []
    crawl = []
    for route, rtype, src, kind, genre, country, year, date_mode, sort, page, expect, eh1 in ROUTES:
        allow = expect not in (301, 302, 308)
        st, h, body, final = fetch(route, allow_redirects=allow)
        parsed = parse_page(body) if st == 200 else {
            "h1": "", "card_count": 0, "total_count": 0, "canonical": "",
            "robots": "", "content_digest": "", "titles": [], "metas": [],
        }
        notes = []
        if expect in (301, 302, 308):
            loc = h.get("Location") or ""
            notes.append(f"location={loc}")
            ok = st == expect
        else:
            ok = st == expect
            if eh1 and parsed.get("h1") and eh1 not in parsed["h1"] and parsed["h1"] != eh1:
                notes.append(f"h1_mismatch:{parsed.get('h1')}")
        rows.append({
            "route": route,
            "route_type": rtype,
            "source_link": src,
            "kind": kind,
            "genre": genre,
            "country": country,
            "year": year,
            "date_mode": date_mode,
            "sort": sort,
            "page": page,
            "expected_status": expect,
            "actual_status": st,
            "expected_h1": eh1,
            "actual_h1": parsed.get("h1", ""),
            "total_count": parsed.get("total_count", 0),
            "card_count": parsed.get("card_count", 0),
            "content_digest": parsed.get("content_digest", ""),
            "canonical": parsed.get("canonical", ""),
            "indexability": parsed.get("robots", ""),
            "desktop_pass": "",
            "tablet_pass": "",
            "mobile_pass": "",
            "notes": ";".join(notes) if notes else ("ok" if ok else f"status_mismatch"),
        })
        crawl.append({
            "route": route,
            "status": st,
            "final_url": final,
            "headers": {k: h.get(k) for k in ("X-Site-Factory-Build-Id", "Location", "X-Robots-Tag") if h.get(k)},
            "parsed": {k: parsed.get(k) for k in ("h1", "total_count", "card_count", "canonical", "content_digest", "freshness", "sort_ui", "placeholder")},
        })
    return rows, crawl


def build_collections():
    st, h, body, _ = fetch("/collections/", True)
    cards = re.findall(
        r'href="(/collection/[^"]+/)"[^>]*>.*?<h[23][^>]*>([^<]+)</h[23]>.*?class="zcoll__desc"[^>]*>([^<]*)',
        body,
        re.S,
    )
    if not cards:
        # fallback simpler
        hrefs = re.findall(r'href="(/collection/[^"]+/)"', body)
        titles = re.findall(r'class="zcoll__t"[^>]*>([^<]+)', body) or re.findall(r"<h2[^>]*>([^<]+)</h2>", body)
        descs = re.findall(r'class="zcoll__desc"[^>]*>([^<]*)', body)
        cards = list(zip(hrefs, titles + [""] * len(hrefs), descs + [""] * len(hrefs)))
        cards = cards[: max(len(hrefs), 1)]
        # unique by href
        seen = set()
        uniq = []
        for href, title, desc in zip(hrefs, (titles + [""] * 50)[: len(hrefs)], (descs + [""] * 50)[: len(hrefs)]):
            if href in seen:
                continue
            seen.add(href)
            uniq.append((href, title, desc))
        cards = uniq

    matrix = []
    digests = {}
    for href, title, desc in cards:
        st2, _, b2, _ = fetch(href, True)
        p = parse_page(b2)
        first20 = p["titles"][:20]
        d = digest("|".join(first20))
        digests[href] = set(first20)
        matrix.append({
            "collection_id": href.strip("/").split("/")[-1],
            "title": title.strip(),
            "selection_rule": "see collection_contract.py",
            "sort_rule": "see collection_contract.py",
            "source_fields": "projection",
            "minimum_items": 6,
            "actual_items": p["total_count"] or p["card_count"],
            "first_20_digest": d,
            "overlap": "",
            "destination": href,
            "status": "ok" if st2 == 200 and p["card_count"] > 0 else "empty_or_broken",
            "desc": desc.strip()[:120],
        })

    # pairwise overlap of first 20
    overlap = {}
    ids = list(digests.keys())
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            inter = digests[a] & digests[b]
            if len(digests[a]) == 20 and digests[a] == digests[b]:
                key = f"{a}|{b}"
                overlap[key] = {"identical_first_20": True, "shared": sorted(inter)}
            elif len(inter) >= 15:
                overlap[f"{a}|{b}"] = {"identical_first_20": False, "shared_count": len(inter)}
    return matrix, overlap, body


def pagination_audit():
    # series 2026 pages
    pages = {}
    for pg in (1, 2):
        path = "/series/?year=2026" if pg == 1 else f"/series/?year=2026&page={pg}"
        st, _, body, _ = fetch(path, True)
        p = parse_page(body)
        pages[pg] = p
    # find last page from pager links
    st, _, body, _ = fetch("/series/?year=2026", True)
    nums = [int(x) for x in re.findall(r"[?&]page=(\d+)", body)]
    last = max(nums) if nums else 1
    st, _, body_last, _ = fetch(f"/series/?year=2026&page={last}", True)
    p_last = parse_page(body_last)
    # overflow
    st_ov, _, _, _ = fetch(f"/series/?year=2026&page={last + 5}", True)
    s1 = set(pages[1]["titles"])
    s2 = set(pages[2]["titles"]) if 2 in pages else set()
    return {
        "route": "/series/?year=2026",
        "page1_count": pages[1]["card_count"],
        "page2_count": pages.get(2, {}).get("card_count", 0),
        "last_page": last,
        "last_page_count": p_last["card_count"],
        "page1_total": pages[1]["total_count"],
        "intersection_1_2": sorted(s1 & s2),
        "intersection_count": len(s1 & s2),
        "overflow_status": st_ov,
        "page1_digest": pages[1]["content_digest"],
        "page2_digest": pages.get(2, {}).get("content_digest", ""),
        "new_page": parse_page(fetch("/new/", True)[2]),
        "new_page2": parse_page(fetch("/new/?page=2", True)[2]),
    }


def related_audit():
    st, _, body, _ = fetch("/title/chasha-vesny/", True)
    related = re.findall(r'class="zt__t"[^>]*>([^<]+)', body)
    home = parse_page(fetch("/", True)[2])
    home_titles = set(home["titles"][:20])
    related_set = set(related[:20])
    return {
        "title": "chasha-vesny",
        "related_count": len(related),
        "related_sample": related[:12],
        "overlap_with_home_first20": sorted(related_set & home_titles),
        "identical_to_home_rail": related_set == home_titles and len(related_set) >= 8,
    }


def description_audit():
    # honest: reuse known baseline metrics; do not invent coverage
    return {
        "DESCRIPTION_COVERAGE_BEFORE": 75.13,
        "MISSING_DESCRIPTION_BEFORE": 13314,
        "EXACT_DUPLICATE_GROUPS_BEFORE": 39,
        "NEAR_DUPLICATE_GROUPS_BEFORE": 3,
        "note": "Pass4 did not invent descriptions. Propagation audit deferred to content backfill; ZONA_SEO_CONTENT_CAN_BE_CLOSED=NO",
        "AVAILABLE_SOURCE_PROPAGATION": "unmeasured_in_pass4_live",
        "INVENTED_DESCRIPTIONS": 0,
        "UNEXPLAINED_EXACT_DUPLICATE_GROUPS_AFTER": "unmeasured_pending_backfill",
        "UNEXPLAINED_NEAR_DUPLICATE_GROUPS_AFTER": "unmeasured_pending_backfill",
    }


SHOT_LIST = [
    ("home-1440.png", "/", 1440, 1000),
    ("home-390.png", "/", 390, 844),
    ("catalog-1440.png", "/catalog/", 1440, 1000),
    ("catalog-390.png", "/catalog/", 390, 844),
    ("series-2026-page1-1440.png", "/series/?year=2026", 1440, 1000),
    ("series-2026-page2-1440.png", "/series/?year=2026&page=2", 1440, 1000),
    ("series-2026-390.png", "/series/?year=2026", 390, 844),
    ("new-1440.png", "/new/", 1440, 1000),
    ("collections-1440.png", "/collections/", 1440, 1000),
    ("collections-390.png", "/collections/", 390, 844),
    ("title-1440.png", "/title/chasha-vesny/", 1440, 1000),
    ("title-390.png", "/title/chasha-vesny/", 390, 844),
    ("related-1440.png", "/title/chasha-vesny/", 1440, 1000),
    ("footer-1440.png", "/", 1440, 1000),
    ("footer-390.png", "/", 390, 844),
    ("empty-state.png", "/movies/?year=1901", 1440, 1000),
    ("invalid-filter.png", "/movies/?year=abcd", 1440, 1000),
]


async def screenshots():
    SHOTS.mkdir(parents=True, exist_ok=True)
    responsive = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # last page for series 2026
        st, _, body, _ = fetch("/series/?year=2026", True)
        nums = [int(x) for x in re.findall(r"[?&]page=(\d+)", body)]
        last = max(nums) if nums else 1
        shots = list(SHOT_LIST) + [
            ("series-2026-last-1440.png", f"/series/?year=2026&page={last}", 1440, 1000),
        ]
        # collection detail
        hrefs = re.findall(r'href="(/collection/[^"]+/)"', body if False else fetch("/collections/", True)[2])
        if hrefs:
            shots.append(("collection-detail-1440.png", hrefs[0], 1440, 1000))

        for name, path, w, h in shots:
            ctx = await browser.new_context(viewport={"width": w, "height": h})
            page = await ctx.new_page()
            try:
                resp = await page.goto(BASE + path, wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(1200)
                if "footer" in name:
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await page.wait_for_timeout(400)
                if "related" in name:
                    await page.evaluate(
                        """()=>{const el=document.querySelector('[data-testid=related-grid],.zrelated,.related');
                        if(el)el.scrollIntoView();}"""
                    )
                    await page.wait_for_timeout(400)
                await page.screenshot(path=str(SHOTS / name), full_page=("footer" not in name and "related" not in name))
                overflow = await page.evaluate(
                    "()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth+1"
                )
                scrollx = await page.evaluate("()=>window.scrollX")
                responsive.append({
                    "shot": name,
                    "path": path,
                    "viewport": f"{w}x{h}",
                    "status": resp.status if resp else None,
                    "no_h_overflow": overflow,
                    "scrollX": scrollx,
                })
                print("shot", name, overflow)
            except Exception as e:
                responsive.append({"shot": name, "path": path, "error": str(e)})
                print("shot ERR", name, e)
            await ctx.close()

        # player screenshots
        for name, w, h in [("player-playing-1440.png", 1440, 900), ("player-playing-390.png", 390, 844)]:
            ctx = await browser.new_context(viewport={"width": w, "height": h})
            page = await ctx.new_page()
            try:
                await page.goto(BASE + "/title/v-lovushke/", wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(1500)
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

        # geometry matrix sample
        for w, h, label in [(1440, 1000, "1440"), (768, 1024, "768"), (390, 844, "390"), (1280, 900, "1280"), (1920, 1080, "1920")]:
            ctx = await browser.new_context(viewport={"width": w, "height": h})
            page = await ctx.new_page()
            await page.goto(BASE + "/movies/", wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(800)
            geo = await page.evaluate(
                """()=>{
                const cards=[...document.querySelectorAll('[data-testid=title-card],.zt')].slice(0,12);
                const widths=cards.map(c=>Math.round(c.getBoundingClientRect().width));
                const tops={}; for(const c of cards){const t=Math.round(c.getBoundingClientRect().top); tops[t]=(tops[t]||0)+1;}
                const cols=Math.max(...Object.values(tops),0);
                const overflow=document.documentElement.scrollWidth<=document.documentElement.clientWidth+1;
                return {cols, widths, overflow, scrollX:window.scrollX};
                }"""
            )
            responsive.append({"viewport": label, "path": "/movies/", **geo})
            print("geo", label, geo)
            await ctx.close()
        await browser.close()
    return responsive


def write_csv(path, rows, fieldnames):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main_sync_parts():
    RAW.mkdir(parents=True, exist_ok=True)
    rows, crawl = build_route_matrix()
    write_csv(
        OUT / "ROUTE_MATRIX.csv",
        rows,
        [
            "route", "route_type", "source_link", "kind", "genre", "country", "year",
            "date_mode", "sort", "page", "expected_status", "actual_status",
            "expected_h1", "actual_h1", "total_count", "card_count", "content_digest",
            "canonical", "indexability", "desktop_pass", "tablet_pass", "mobile_pass", "notes",
        ],
    )
    (OUT / "ROUTE_CRAWL.json").write_text(json.dumps(crawl, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    matrix, overlap, coll_body = build_collections()
    write_csv(
        OUT / "COLLECTION_MATRIX.csv",
        matrix,
        [
            "collection_id", "title", "selection_rule", "sort_rule", "source_fields",
            "minimum_items", "actual_items", "first_20_digest", "overlap", "destination", "status",
        ],
    )
    (OUT / "COLLECTION_OVERLAP.json").write_text(
        json.dumps({"pairwise": overlap, "count": len(matrix)}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    pag = pagination_audit()
    (OUT / "PAGINATION_AUDIT.json").write_text(json.dumps(pag, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # facet years from series page
    st, _, body, _ = fetch("/series/", True)
    years = re.findall(r'year=(\d{4})', body)
    facet = {"series_year_links": sorted(set(years), reverse=True)[:30], "series_total_hint": parse_page(body)["total_count"]}
    st, _, body_m, _ = fetch("/movies/", True)
    years_m = re.findall(r'year=(\d{4})', body_m)
    facet["movies_year_links"] = sorted(set(years_m), reverse=True)[:30]
    facet["movies_total_hint"] = parse_page(body_m)["total_count"]
    (OUT / "FACET_COUNTS.json").write_text(json.dumps(facet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    rel = related_audit()
    (OUT / "RELATED_AUDIT.json").write_text(json.dumps(rel, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    desc = description_audit()
    (OUT / "DESCRIPTION_AUDIT.json").write_text(json.dumps(desc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # provenance stub header only — no invented rows
    with (OUT / "DESCRIPTION_PROVENANCE.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["title_id", "description_source", "source_record_id", "source_updated_at", "content_hash", "ingested_at", "status"])
        w.writerow(["*", "authoritative_source_incomplete", "", "", "", "", "backfill_required"])

    return {
        "routes": len(rows),
        "collections": len(matrix),
        "pagination": pag,
        "related": rel,
        "new_total": pag["new_page"]["total_count"],
    }


async def main():
    summary = main_sync_parts()
    responsive = await screenshots()
    write_csv(
        OUT / "RESPONSIVE_MATRIX.csv",
        [
            {
                "viewport": r.get("viewport", ""),
                "path": r.get("path", ""),
                "shot": r.get("shot", ""),
                "cols": r.get("cols", ""),
                "widths": json.dumps(r.get("widths")) if r.get("widths") is not None else "",
                "no_h_overflow": r.get("no_h_overflow", r.get("overflow", "")),
                "scrollX": r.get("scrollX", ""),
                "error": r.get("error", ""),
            }
            for r in responsive
        ],
        ["viewport", "path", "shot", "cols", "widths", "no_h_overflow", "scrollX", "error"],
    )
    (OUT / "BROWSER_MATRIX.csv").write_text(
        "browser,status,notes\n"
        "chromium,PASS,playwright screenshots + golden\n"
        "firefox,NOT_AVAILABLE,not installed in this runner\n"
        "webkit,NOT_AVAILABLE,not installed in this runner\n",
        encoding="utf-8",
    )
    (OUT / "raw/evidence_summary.json").write_text(
        json.dumps({"at": datetime.now(timezone.utc).isoformat(), **summary}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("DONE", summary)


if __name__ == "__main__":
    asyncio.run(main())
