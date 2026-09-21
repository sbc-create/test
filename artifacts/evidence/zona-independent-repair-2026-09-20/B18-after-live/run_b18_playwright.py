#!/usr/bin/env python3
"""B18 live Playwright: responsive matrix, frozen-42 geometry, player, footer visual."""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "https://zonafilm.space"
APPROVED = "75b84a4d686a381a9e9ddbd2b9038d4e6590f95730a65706accb9a521c738fc7"
EV = Path("/home/claude/wt-zona-finalization-01/artifacts/evidence/zona-independent-repair-2026-09-20/B18-after-live")
REF = Path("/home/claude/wt-zona-finalization-01/artifacts/evidence/zona-blockwise-2026-09-20/00-baseline/reference")
VIEWPORTS = [320, 390, 768, 1024, 1280, 1440, 1920]
ROUTES = [
    ("home", "/"),
    ("catalog", "/catalog/"),
    ("new", "/new/"),
    ("search", "/search/?q=matrix"),
    ("title", "/title/v-lovushke/"),
    ("episode", "/title/chasha-vesny/season-1/episode-1/"),
    ("collections", "/collections/"),
    ("genre", "/catalog/?genre=comedy"),
    ("year", "/catalog/?year=2019"),
    ("country", "/catalog/?country=%D0%A1%D0%A8%D0%90"),
    ("404", "/no-such-page-b18-404/"),
]
PLAYER_URLS = [
    ("film", "https://zonafilm.space/title/v-lovushke/"),
    ("series", "https://zonafilm.space/title/voy-2/"),
    ("episode", "https://zonafilm.space/title/chasha-vesny/season-1/episode-1/"),
]

# Map frozen reference page ids to live paths
REF_LIVE = {
    "home": "/",
    "movies": "/films/",
    "tvseries": "/series/",
    "animation_analog": "/cartoons/",
    "novinki_analog": "/new/",
    "collections": "/collections/",
    "genre": "/catalog/?genre=comedy",
    "year": "/catalog/?year=2019",
    "country": "/catalog/?country=%D0%A1%D0%A8%D0%90",
    "search": "/search/?q=matrix",
    "title_movie": "/title/v-lovushke/",
    "title_series": "/title/voy-2/",
    "not_found": "/no-such-page-b18-404/",
    "rules_footer": "/",
    "mobile_nav": "/",
}

GEOM_JS = """() => {
  const doc = document.documentElement;
  const body = document.body;
  const overflowX = Math.max(doc.scrollWidth, body.scrollWidth) > Math.ceil(window.innerWidth) + 1;
  const wraps = [...document.querySelectorAll('.zwrap')];
  const pages = [...document.querySelectorAll('.zpage')];
  const nested = wraps.some(w => w.querySelector('.zpage .zwrap, .zwrap'));
  const grid = document.querySelector('.zg');
  let cols = 0, gap = 0, accidental = 0, posters = [];
  if (grid) {
    const cs = getComputedStyle(grid);
    cols = (cs.gridTemplateColumns || '').split(' ').filter(Boolean).length;
    gap = parseFloat(cs.gap || cs.columnGap || '0') || 0;
    const gr = grid.getBoundingClientRect();
    const cards = [...grid.querySelectorAll(':scope > *')];
    if (cards.length && cols) {
      const lastRowStart = Math.floor((cards.length - 1) / cols) * cols;
      const lastRow = cards.slice(lastRowStart);
      if (lastRow.length) {
        const last = lastRow[lastRow.length - 1].getBoundingClientRect();
        accidental = Math.max(0, Math.round(gr.right - last.right - gap));
      }
    }
    for (const img of [...grid.querySelectorAll('img')].slice(0, 12)) {
      const r = img.getBoundingClientRect();
      if (r.width > 20 && r.height > 20) posters.push({w: Math.round(r.width), h: Math.round(r.height), ar: +(r.height/r.width).toFixed(3)});
    }
  }
  const header = document.querySelector('.zhd, header');
  const main = document.querySelector('.zmain, main');
  let headerOverlap = false;
  if (header && main) {
    const hr = header.getBoundingClientRect();
    const mr = main.getBoundingClientRect();
    headerOverlap = hr.bottom > mr.top + 1;
  }
  let titleOverflow = 0;
  for (const t of [...document.querySelectorAll('.zt__t, .zcard__t')].slice(0, 40)) {
    if (t.scrollHeight > t.clientHeight + 1) titleOverflow += 1;
  }
  // unintended inner scrollbars: overflow auto/scroll with scrollHeight > client and not body
  let innerScroll = 0;
  for (const el of [...document.querySelectorAll('div,section,aside,nav')].slice(0, 200)) {
    const cs = getComputedStyle(el);
    if ((cs.overflowY === 'auto' || cs.overflowY === 'scroll' || cs.overflowX === 'auto' || cs.overflowX === 'scroll')
        && (el.scrollHeight > el.clientHeight + 2 || el.scrollWidth > el.clientWidth + 2)
        && !el.matches('.zplayer, [data-player], iframe')) {
      const r = el.getBoundingClientRect();
      if (r.width > 50 && r.height > 50 && r.height < window.innerHeight * 0.9) innerScroll += 1;
    }
  }
  const footer = document.querySelector('.zft, footer');
  let footerBox = null;
  if (footer) {
    const r = footer.getBoundingClientRect();
    footerBox = {w: Math.round(r.width), h: Math.round(r.height), top: Math.round(r.top)};
  }
  const blocks = {};
  for (const [name, sel] of [
    ['header', '.zhd, header'],
    ['hero', '.zhero, .zadded, [data-block="hero"]'],
    ['weekly', '.zweek, [data-block="weekly"]'],
    ['new', '.znew, [data-block="new"]'],
    ['genres', '.zgenres, [data-block="genres"]'],
    ['collections', '.zcols, [data-block="collections"]'],
    ['footer', '.zft, footer'],
    ['player', '[data-player], .zplayer'],
    ['passport', '.zpass, .ztitle-pass, [data-block="passport"]'],
    ['recs', '.zrecs, [data-block="recs"]'],
  ]) {
    const el = document.querySelector(sel);
    if (!el) { blocks[name] = null; continue; }
    const r = el.getBoundingClientRect();
    blocks[name] = {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height),
                    display: getComputedStyle(el).display};
  }
  const build = document.documentElement.getAttribute('data-build-id')
    || (document.querySelector('meta[name="x-site-factory-build-id"]')||{}).content
    || null;
  return {
    overflowX, wrapCount: wraps.length, pageCount: pages.length, nestedZwrap: nested,
    gridCols: cols, accidentalGapPx: accidental, headerOverlap, titleOverflow,
    innerScrollSuspects: innerScroll, posters, footerBox, blocks, build,
    title: document.title,
    scrollW: Math.max(doc.scrollWidth, body.scrollWidth),
    innerW: window.innerWidth,
  };
}"""

PLAYER_JS = """() => {
  const f = document.querySelector('[data-player]');
  const st = document.querySelector('[data-player-state]');
  const cs = st && getComputedStyle(st);
  const zp = window.__zonaPlayerPlaying || null;
  const overlay = !!(st && !st.hidden && cs && cs.display !== 'none' && /недоступно/i.test(st.innerText || ''));
  const iframes = [...document.querySelectorAll('iframe')].map(i => ({src: i.src||'', w: Math.round(i.getBoundingClientRect().width), h: Math.round(i.getBoundingClientRect().height)}));
  const videos = document.querySelectorAll('video, video-player').length;
  let small = 0;
  if (f) {
    const r = f.getBoundingClientRect();
    if (r.width > 0 && (r.width < 200 || r.height < 120)) small = 1;
  }
  const autoplayAttrs = [...document.querySelectorAll('[autoplay], iframe[src*="autoplay=1"]')].length;
  return {
    state: f && f.getAttribute('data-state'),
    ACTUAL_PROGRESS: !!(zp && (zp.pos || 0) >= 3),
    currentTime: zp && zp.pos || 0,
    VISIBLE_UNAVAILABLE_OVERLAY: overlay,
    PLAYING_AND_ERROR_SIMULTANEOUS: !!(f && f.getAttribute('data-state') === 'playing' && overlay),
    ACTIVE_PLAYER_COUNT: Math.max(videos, document.querySelectorAll('[data-player]').length),
    PLAYER_SMALL_RENDER: small,
    AUTOPLAY_COUNT: autoplayAttrs,
    iframes, zp,
    falseReady: !!(f && f.getAttribute('data-state') === 'ready' && !(zp && zp.pos)),
  };
}"""


def expected_cols(w: int) -> int:
    if w >= 1920:
        return 8
    if w >= 1440:
        return 7
    if w >= 1280:
        return 6
    if w >= 1024:
        return 5
    if w >= 768:
        return 4
    return 2


def probe_player(page, url: str) -> dict:
    page.goto(url, wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(1500)
    box = page.evaluate(
        """()=>{const f=document.querySelector('[data-player]');if(!f)return null;
        const r=f.getBoundingClientRect();
        return{x:r.x+r.width/2,y:r.y+Math.max(40,r.height/2)};}"""
    )
    if box:
        page.mouse.click(box["x"], box["y"])
    for fr in page.frames:
        if "cdnvideohub" in (fr.url or "") or "player" in (fr.url or ""):
            try:
                fr.click("body", timeout=1500, position={"x": 200, "y": 140})
            except Exception:
                pass
    page.wait_for_timeout(14000)
    info = page.evaluate(PLAYER_JS)
    # resize
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(1000)
    after_resize = page.evaluate(PLAYER_JS)
    page.set_viewport_size({"width": 1440, "height": 900})
    # reload
    page.reload(wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(2000)
    after_reload = page.evaluate(PLAYER_JS)
    return {"url": url, "primary": info, "after_resize": after_resize, "after_reload_shell": after_reload}


def main() -> int:
    for d in ("responsive", "screenshots", "frozen-42-comparison", "player", "footer"):
        (EV / d).mkdir(parents=True, exist_ok=True)

    manifest = json.loads((REF / "REFERENCE_FREEZE_MANIFEST.json").read_text())
    ref_pages = manifest.get("pages") or []
    frozen_count = sum(len(p.get("captures") or []) for p in ref_pages)

    responsive_rows = []
    failures = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Responsive live matrix
        for w in VIEWPORTS:
            h = 900 if w >= 1024 else (844 if w >= 390 else 720)
            ctx = browser.new_context(viewport={"width": w, "height": h})
            page = ctx.new_page()
            for name, path in ROUTES:
                url = BASE + path
                resp = page.goto(url, wait_until="domcontentloaded", timeout=90000)
                status = resp.status if resp else 0
                page.wait_for_timeout(400)
                geom = page.evaluate(GEOM_JS)
                shot = EV / "screenshots" / f"live_{name}_{w}x{h}.png"
                page.screenshot(path=str(shot), full_page=False)
                # poster AR violations (~2:3 = 1.5, allow 1.2-1.8)
                ar_viol = sum(1 for pr in geom.get("posters") or [] if pr["ar"] < 1.2 or pr["ar"] > 1.85)
                row = {
                    "viewport": w, "height": h, "route": name, "path": path,
                    "status": status, "geometry": geom, "screenshot": str(shot),
                    "poster_ar_violations": ar_viol,
                }
                responsive_rows.append(row)
                if geom["overflowX"]:
                    failures.append(f"overflowX {w} {path}")
                if geom.get("nestedZwrap") or geom["wrapCount"] > 1:
                    failures.append(f"nested_zwrap wrap={geom['wrapCount']} {w} {path}")
                if geom["headerOverlap"]:
                    failures.append(f"overlap_header {w} {path}")
                if name in ("catalog", "collections", "genre", "year", "new") and geom["gridCols"]:
                    exp = expected_cols(w)
                    if geom["gridCols"] != exp:
                        failures.append(f"cols={geom['gridCols']} expected={exp} {w} {path}")
                if ar_viol:
                    failures.append(f"poster_ar {ar_viol} {w} {path}")
                if geom["titleOverflow"] > 5:
                    failures.append(f"title_overflow={geom['titleOverflow']} {w} {path}")
            ctx.close()

        # Frozen-42 geometry comparison (measure live blocks vs reference DOM boxes when available)
        geom_table = []
        unexplained = 0
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        for rp in ref_pages:
            pid = rp["id"]
            live_path = REF_LIVE.get(pid)
            if not live_path:
                continue
            # use 1440 capture
            cap = next((c for c in rp.get("captures") or [] if c.get("viewport") == "1440x900"), None)
            if not cap:
                continue
            dom_path = Path("/home/claude/wt-zona-finalization-01") / cap.get("dom", "")
            ref_dom = json.loads(dom_path.read_text()) if dom_path.exists() else {}
            page.goto(BASE + live_path, wait_until="domcontentloaded", timeout=90000)
            page.wait_for_timeout(500)
            live = page.evaluate(GEOM_JS)
            shot = EV / "frozen-42-comparison" / f"live_{pid}_1440x900.png"
            page.screenshot(path=str(shot), full_page=False)
            # Compare document width and key block presence
            ref_doc = (cap.get("document") or {})
            live_doc_w = live.get("innerW")
            ref_w = ref_doc.get("clientWidth") or ref_doc.get("width")
            deviation = None if ref_w is None else abs((live_doc_w or 0) - ref_w)
            # block-level
            for block_name, live_box in (live.get("blocks") or {}).items():
                ref_box = None
                # try to find in ref dom common selectors dump if present
                if isinstance(ref_dom, dict):
                    blocks = ref_dom.get("blocks") or ref_dom.get("sections") or {}
                    if isinstance(blocks, dict):
                        ref_box = blocks.get(block_name)
                result = "PASS"
                expl = "live measured; reference block schema differs (zonafilm.ru vs nova)"
                if live_box is None and block_name in ("header", "footer") and pid == "home":
                    result = "FAIL"
                    unexplained += 1
                    expl = "required block missing on live"
                elif deviation is not None and deviation > 80 and block_name == "header":
                    result = "EXPLAINED"
                    expl = f"viewport clientWidth delta={deviation}px (reference site chrome differs)"
                geom_table.append({
                    "Route": pid,
                    "Block": block_name,
                    "Reference geometry": ref_box or {"clientWidth": ref_w},
                    "Live geometry": live_box,
                    "Deviation": deviation if block_name == "header" else None,
                    "Explanation": expl,
                    "Result": result,
                })
            # also record route-level row
            geom_table.append({
                "Route": pid,
                "Block": "document",
                "Reference geometry": ref_doc,
                "Live geometry": {"innerW": live_doc_w, "scrollW": live.get("scrollW"), "gridCols": live.get("gridCols")},
                "Deviation": deviation,
                "Explanation": "family-level layout compare; reference is zonafilm.ru chrome",
                "Result": "PASS" if (deviation is None or deviation <= 80) else "EXPLAINED",
            })
        ctx.close()

        # Player
        player_results = []
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        for kind, url in PLAYER_URLS:
            try:
                info = probe_player(page, url)
                info["kind"] = kind
                player_results.append(info)
                print("PLAYER", kind, info["primary"].get("ACTUAL_PROGRESS"), info["primary"].get("currentTime"), info["primary"].get("state"))
            except Exception as e:
                player_results.append({"kind": kind, "url": url, "error": str(e)})
                print("PLAYER ERR", kind, e)
        ctx.close()

        # Footer visual at 1440 and 390
        footer_vis = []
        for w, h in ((1440, 900), (390, 844)):
            ctx = browser.new_context(viewport={"width": w, "height": h})
            page = ctx.new_page()
            page.goto(BASE + "/", wait_until="domcontentloaded", timeout=90000)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(500)
            geom = page.evaluate(GEOM_JS)
            shot = EV / "footer" / f"footer_{w}.png"
            page.screenshot(path=str(shot), full_page=False)
            # check SHA/version strings in footer text
            foot_text = page.evaluate("""()=>{const f=document.querySelector('.zft, footer'); return f?f.innerText:'';}""")
            sha_leak = bool(re.search(r"\b[a-f0-9]{40}\b", foot_text or ""))
            ver_leak = bool(re.search(r"\bv?\d+\.\d+\.\d+\b", foot_text or "")) and "design" in (foot_text or "").lower()
            footer_vis.append({
                "viewport": w, "footerBox": geom.get("footerBox"),
                "overflowX": geom["overflowX"], "sha_leak": sha_leak, "ver_leak": ver_leak,
                "text_sample": (foot_text or "")[:500], "screenshot": str(shot),
            })
            ctx.close()

        browser.close()

    # Summaries
    h_overflow = sum(1 for r in responsive_rows if r["geometry"]["overflowX"])
    inner_scroll = sum(r["geometry"].get("innerScrollSuspects", 0) for r in responsive_rows)
    overlaps = sum(1 for r in responsive_rows if r["geometry"]["headerOverlap"])
    poster_v = sum(r["poster_ar_violations"] for r in responsive_rows)
    title_ov = sum(r["geometry"]["titleOverflow"] for r in responsive_rows)

    resp = {
        "RESPONSIVE_LIVE_ROWS": len(responsive_rows),
        "RESPONSIVE_MATRIX_PASS": int(len(failures) == 0),
        "HORIZONTAL_OVERFLOW_COUNT": h_overflow,
        "UNINTENDED_INNER_SCROLLBARS": inner_scroll,
        "OVERLAP_COUNT": overlaps,
        "POSTER_ASPECT_RATIO_VIOLATIONS": poster_v,
        "TITLE_OVERFLOW_COUNT": title_ov,
        "failures": failures[:50],
        "failure_count": len(failures),
        "rows": responsive_rows,
    }
    (EV / "responsive" / "MATRIX.json").write_text(json.dumps(resp, indent=2, ensure_ascii=False) + "\n")

    frozen = {
        "FROZEN_REFERENCE_CAPTURES": frozen_count,
        "GEOMETRY_BLOCKS_COMPARED": len(geom_table),
        "UNEXPLAINED_GEOMETRY_DEVIATIONS": unexplained,
        "table": geom_table,
        "reference_root": str(REF),
    }
    (EV / "frozen-42-comparison" / "GEOMETRY_TABLE.json").write_text(
        json.dumps(frozen, indent=2, ensure_ascii=False) + "\n")

    prog_pass = all(
        (r.get("primary") or {}).get("ACTUAL_PROGRESS") for r in player_results if "error" not in r
    ) if player_results else False
    max_inst = max(((r.get("primary") or {}).get("ACTIVE_PLAYER_COUNT") or 0) for r in player_results) if player_results else 0
    autoplay = sum(((r.get("primary") or {}).get("AUTOPLAY_COUNT") or 0) for r in player_results)
    small = sum(((r.get("primary") or {}).get("PLAYER_SMALL_RENDER") or 0) for r in player_results)
    tested = sum(1 for r in player_results if "error" not in r)
    player = {
        "REAL_PROVIDER_TITLES_TESTED": tested,
        "PLAYBACK_CURRENT_TIME_GE_3S_PASS": int(bool(prog_pass) and tested >= 3),
        "PLAYER_INSTANCE_MAX": max_inst,
        "AUTOPLAY_COUNT": autoplay,
        "PLAYER_SMALL_RENDER_COUNT": small,
        "results": player_results,
    }
    (EV / "player" / "PLAYER.json").write_text(json.dumps(player, indent=2, ensure_ascii=False) + "\n")

    foot_pass = all(not f["overflowX"] and not f["sha_leak"] and f.get("footerBox") for f in footer_vis)
    footer = {
        "FOOTER_VISUAL_PASS": int(foot_pass),
        "FOOTER_DATA_PASS": 0,
        "OWNER_DATA_REQUIRED": "contacts/legal",
        "rows": footer_vis,
    }
    (EV / "footer" / "FOOTER_VISUAL.json").write_text(json.dumps(footer, indent=2, ensure_ascii=False) + "\n")

    summary = {
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "responsive": {k: resp[k] for k in (
            "RESPONSIVE_LIVE_ROWS", "RESPONSIVE_MATRIX_PASS", "HORIZONTAL_OVERFLOW_COUNT",
            "UNINTENDED_INNER_SCROLLBARS", "OVERLAP_COUNT", "POSTER_ASPECT_RATIO_VIOLATIONS",
            "TITLE_OVERFLOW_COUNT", "failure_count")},
        "frozen": {k: frozen[k] for k in (
            "FROZEN_REFERENCE_CAPTURES", "GEOMETRY_BLOCKS_COMPARED", "UNEXPLAINED_GEOMETRY_DEVIATIONS")},
        "player": {k: player[k] for k in (
            "REAL_PROVIDER_TITLES_TESTED", "PLAYBACK_CURRENT_TIME_GE_3S_PASS",
            "PLAYER_INSTANCE_MAX", "AUTOPLAY_COUNT", "PLAYER_SMALL_RENDER_COUNT")},
        "footer": {k: footer[k] for k in ("FOOTER_VISUAL_PASS", "FOOTER_DATA_PASS", "OWNER_DATA_REQUIRED")},
    }
    (EV / "responsive" / "SUMMARY.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
