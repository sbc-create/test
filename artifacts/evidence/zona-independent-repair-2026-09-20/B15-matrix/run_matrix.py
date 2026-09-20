#!/usr/bin/env python3
"""B15 local headed predeploy geometry matrix (fixture storefront)."""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "automation/host/lords-frontend.py"
OUT = ROOT / "artifacts/evidence/zona-independent-repair-2026-09-20/B15-matrix"
OUT.mkdir(parents=True, exist_ok=True)

VIEWPORTS = [
    (1440, 900), (1363, 936), (1024, 768), (820, 1180), (768, 1024),
    (430, 932), (390, 844), (360, 800), (320, 720),
]
PAGES = [
    "/", "/catalog/", "/catalog/?year=1902&genre=comedy", "/new/",
    "/search/?q=Dusty%20Bluffs", "/search/?q=zzznothing",
    "/collections/", "/collection/recently_added/",
    "/title/t-0001/", "/title/seriya-matrix/",
    "/title/seriya-matrix/season-1/episode-1/", "/no-such-page-404/",
]


def build_fixture(tmp: Path):
    items = []
    for i in range(80):
        kind = "Фильм" if i % 3 == 0 else ("Сериал" if i % 3 == 1 else "Мультфильм")
        items.append({
            "slug": f"t-{i:04d}", "title": f"Название {i:04d} длинное для clamp",
            "kind": kind, "year": 2000 + (i % 20),
            "poster": f"https://poster.example/{i}.webp",
            "url": f"/title/t-{i:04d}/",
            "published_at": f"2026-08-{(i % 28) + 1:02d}T00:00:00Z",
            "original_name": "Dusty Bluffs" if i == 1 else "",
        })
    items.append({
        "slug": "seriya-matrix", "title": "Сериал Матрица", "kind": "Сериал",
        "year": 2022, "poster": "https://poster.example/s.webp",
        "url": "/title/seriya-matrix/", "published_at": "2026-09-01T00:00:00Z",
        "original_name": "The Series Matrix",
    })
    cat = {
        "version": 2, "count": len(items), "items": items, "site": "zona-01",
        "schema": "nova-catalog/2.0.0", "revision": "b15",
        "builtAt": "2026-09-20T00:00:00Z",
    }
    details = {
        "schema": "nova-details/1.0.0", "site": "zona-01",
        "details_total": 0, "source": "test", "items_total": 0, "details": {},
    }
    for i, it in enumerate(items):
        d = {
            "id": f"id-{it['slug']}",
            "description": ("Описание " + "слово " * 80) if i < 3 else "Коротко",
            "genres": ["комедия" if i % 2 == 0 else "драма"],
            "genre_codes": ["comedy" if i % 2 == 0 else "drama"],
            "countries": ["Великобритания" if i % 3 == 0 else "США"],
            "original_name": it.get("original_name") or "",
            "premiere_date": f"2020-{(i % 12) + 1:02d}-15",
            "kinopoisk_rating": 7.605 if i % 4 == 0 else None,
            "imdb_rating": 8 if i % 5 == 0 else (7.3 if i % 3 == 0 else None),
            "sources": [{"provider": "kp", "source_id": str(i),
                         "availability_status": "available"}],
            "external_ids": {"kp": str(i)}, "playable": i % 4 != 0,
        }
        if it["slug"] == "seriya-matrix":
            d["seasons"] = [{"n": 1, "eps": 5, "avail": 5}]
        details["details"][it["slug"]] = d
    details["details_total"] = len(details["details"])
    details["items_total"] = len(details["details"])
    root = tmp / "zona-01"
    root.mkdir()
    (root / "zona-01-catalog.json").write_text(
        json.dumps(cat, ensure_ascii=False), encoding="utf-8")
    (root / "zona-01-details.json").write_text(
        json.dumps(details, ensure_ascii=False), encoding="utf-8")
    (root / "player-zona-01.json").write_text(
        json.dumps({"publisher_id": "10238", "source_mode": "provider-id"}),
        encoding="utf-8")
    man = root / "manifest.json"
    man.write_text(json.dumps({
        "schema_version": 1, "template_family": "zona",
        "design_version": "1.2.0", "source_commit": "0" * 40,
        "build_id": "B15-LOCAL", "artifact_sha256": "0" * 64,
        "profile": "zona-test", "built_at": "2026-09-20T00:00:00Z",
    }), encoding="utf-8")
    return root, man


def load_module(root: Path, man: Path):
    env = dict(os.environ)
    os.environ.update({
        "LORDS_TEMPLATE_MANIFEST": str(man),
        "LORDS_CATALOG": str(root / "zona-01-catalog.json"),
        "LORDS_DETAILS": str(root / "zona-01-details.json"),
        "LORDS_PLAYER_CONFIG": str(root / "player-zona-01.json"),
        "LORDS_SITE_NAME": "Zona B15",
        "LORDS_CLOCK_ISO": "2026-09-20T12:00:00Z",
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    name = "nova_zona_b15_matrix"
    spec = importlib.util.spec_from_file_location(name, SRC)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        os.environ.clear()
        os.environ.update(env)
    mod.Обработчик.данные = mod.Данные(str(root / "zona-01-catalog.json"))
    mod.Обработчик.подробности = mod.Подробности(str(root / "zona-01-details.json"))
    mod.Обработчик.индекс = mod.построить_индекс(
        mod.Обработчик.данные, mod.Обработчик.подробности)
    return mod


GEOM_JS = """() => {
  const doc = document.documentElement;
  const body = document.body;
  const overflowX = Math.max(doc.scrollWidth, body.scrollWidth) > Math.ceil(window.innerWidth) + 1;
  const wraps = [...document.querySelectorAll('.zwrap')].map(el => {
    const r = el.getBoundingClientRect();
    return {w: Math.round(r.width), left: Math.round(r.left), right: Math.round(r.right)};
  });
  const pages = [...document.querySelectorAll('.zpage')].length;
  const grid = document.querySelector('.zg');
  let cols = 0, gap = 0, accidental = 0;
  if (grid) {
    const cs = getComputedStyle(grid);
    cols = (cs.gridTemplateColumns || '').split(' ').filter(Boolean).length;
    gap = parseFloat(cs.gap || cs.columnGap || '0') || 0;
    const gr = grid.getBoundingClientRect();
    const cards = [...grid.querySelectorAll(':scope > *')].slice(0, cols || 12);
    if (cards.length) {
      const last = cards[cards.length - 1].getBoundingClientRect();
      accidental = Math.max(0, Math.round(gr.right - last.right - gap));
    }
  }
  const header = document.querySelector('.zhd');
  const main = document.querySelector('.zmain, main');
  let headerOverlap = false;
  if (header && main) {
    const hr = header.getBoundingClientRect();
    const mr = main.getBoundingClientRect();
    headerOverlap = hr.bottom > mr.top + 1;
  }
  const cards = [...document.querySelectorAll('[data-testid="title-card"], a.zt')].slice(0, 24);
  let textOverflow = 0;
  for (const c of cards) {
    const t = c.querySelector('.zt__t');
    if (t && t.scrollHeight > t.clientHeight + 1) textOverflow += 1;
  }
  const blankRatings = [...document.querySelectorAll('.zt__r-empty')].length;
  return {
    overflowX, wrapCount: wraps.length, pageCount: pages, wraps,
    gridCols: cols, accidentalGapPx: accidental, headerOverlap,
    textOverflowSample: textOverflow, blankRatingRows: blankRatings,
    title: document.title, h1: (document.querySelector('h1')||{}).textContent || '',
  };
}"""


def main():
    results = []
    failures = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        root, man = build_fixture(tmp)
        mod = load_module(root, man)
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), mod.Обработчик)
        port = httpd.server_address[1]
        th = threading.Thread(target=httpd.serve_forever, daemon=True)
        th.start()
        base = f"http://127.0.0.1:{port}"
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                for w, h in VIEWPORTS:
                    context = browser.new_context(viewport={"width": w, "height": h})
                    page = context.new_page()
                    for path in PAGES:
                        url = base + path
                        resp = page.goto(url, wait_until="domcontentloaded", timeout=20000)
                        status = resp.status if resp else 0
                        geom = page.evaluate(GEOM_JS)
                        shot = OUT / f"vp{w}x{h}_{re.sub(r'[^a-z0-9]+', '_', path.strip('/') or 'home')}.png"
                        page.screenshot(path=str(shot), full_page=False)
                        row = {
                            "viewport": [w, h], "path": path, "status": status,
                            "geometry": geom, "screenshot": str(shot.relative_to(ROOT)),
                        }
                        results.append(row)
                        # Gates
                        if geom["overflowX"]:
                            failures.append(f"overflowX {w}x{h} {path}")
                        if geom["wrapCount"] > 1:
                            failures.append(f"nested_zwrap={geom['wrapCount']} {w}x{h} {path}")
                        if geom["headerOverlap"]:
                            failures.append(f"header_overlap {w}x{h} {path}")
                        if path.rstrip("/") in ("/catalog", "/collections") or path.startswith("/collection/"):
                            # expected columns by viewport width
                            expected = 2
                            if w >= 1920:
                                expected = 8
                            elif w >= 1440:
                                expected = 7
                            elif w >= 1280:
                                expected = 6
                            elif w >= 1024:
                                expected = 5
                            elif w >= 768:
                                expected = 4
                            if geom["gridCols"] and geom["gridCols"] != expected:
                                failures.append(
                                    f"grid_cols={geom['gridCols']} expected={expected} {w}x{h} {path}")
                            if geom["accidentalGapPx"] > 200:
                                failures.append(
                                    f"accidental_gap={geom['accidentalGapPx']} {w}x{h} {path}")
                    context.close()
                browser.close()
        finally:
            httpd.shutdown()

    summary = {
        "block": "B15",
        "mode": "local_headed_fixture",
        "viewports": VIEWPORTS,
        "pages": PAGES,
        "rows": len(results),
        "failures": failures,
        "RESPONSIVE_MATRIX_PASS": 0 if failures else 1,
        "HORIZONTAL_OVERFLOW": sum(1 for r in results if r["geometry"]["overflowX"]),
        "NESTED_ZWRAP_VIOLATIONS": sum(1 for r in results if r["geometry"]["wrapCount"] > 1),
        "HEADER_MAIN_OVERLAPS": sum(1 for r in results if r["geometry"]["headerOverlap"]),
    }
    (OUT / "MATRIX.json").write_text(
        json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    (OUT / "PASSPORT.json").write_text(json.dumps({
        "block": "B15",
        "status": "PASS_LOCAL" if not failures else "FAIL_LOCAL",
        "RESPONSIVE_MATRIX_PASS": summary["RESPONSIVE_MATRIX_PASS"],
        "failure_count": len(failures),
        "failures_sample": failures[:20],
        "artifact": "MATRIX.json",
        "note": "Local fixture headed matrix; not live after-deploy proof.",
        "updated_at": "2026-09-20T18:00:00Z",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
