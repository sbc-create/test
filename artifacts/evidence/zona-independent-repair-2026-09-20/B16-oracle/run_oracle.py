#!/usr/bin/env python3
"""B16 local route/oracle/performance samples on fixture storefront."""
from __future__ import annotations

import importlib.util
import json
import os
import statistics
import sys
import tempfile
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "artifacts/evidence/zona-independent-repair-2026-09-20/B15-matrix"))
import run_matrix as rm  # noqa: E402

OUT = ROOT / "artifacts/evidence/zona-independent-repair-2026-09-20/B16-oracle"
OUT.mkdir(parents=True, exist_ok=True)

ROUTES = ["/", "/catalog/", "/new/", "/search/?q=Dusty%20Bluffs",
          "/collection/recently_added/", "/title/t-0001/",
          "/title/seriya-matrix/season-1/episode-1/"]


def timed_get(url: str) -> tuple[int, float, dict]:
    t0 = time.perf_counter()
    req = Request(url, headers={"Connection": "close"})
    with urlopen(req, timeout=30) as r:
        body = r.read()
        headers = {k.lower(): v for k, v in r.headers.items()}
        status = r.status
    return status, (time.perf_counter() - t0) * 1000.0, headers


def main():
    with tempfile.TemporaryDirectory() as td:
        root, man = rm.build_fixture(Path(td))
        mod = rm.load_module(root, man)
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), mod.Обработчик)
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{port}"
        samples = {}
        try:
            for path in ROUTES:
                cold = []
                warm = []
                headers_last = {}
                for i in range(5):
                    st, ms, hdr = timed_get(base + path)
                    assert st == 200, (path, st)
                    (cold if i == 0 else warm).append(ms)
                    headers_last = hdr
                samples[path] = {
                    "cold_ms": cold[0],
                    "warm_p50_ms": statistics.median(warm),
                    "warm_p95_ms": sorted(warm)[max(0, int(len(warm) * 0.95) - 1)],
                    "cache_control": headers_last.get("cache-control"),
                    "etag": headers_last.get("etag"),
                }
            # Pagination oracle on catalog
            page1 = urlopen(base + "/catalog/").read().decode()
            page2 = urlopen(base + "/catalog/?page=2").read().decode()
            import re
            s1 = set(re.findall(r'href="(/title/[^"]+/)"', page1))
            s2 = set(re.findall(r'href="(/title/[^"]+/)"', page2))
            # invalid page
            st404 = urlopen(Request(base + "/catalog/?page=9999")).getcode() if False else None
            from urllib.error import HTTPError
            try:
                urlopen(base + "/catalog/?page=9999")
                inv = 200
            except HTTPError as e:
                inv = e.code
            pagination = {
                "page1_cards": len(s1),
                "page2_cards": len(s2),
                "cross_page_dupes": len(s1 & s2),
                "invalid_page_status": inv,
            }
            from urllib.parse import quote
            search = {}
            for q, _expect in [("Dusty Bluffs", "t-0001"),
                               ("zzznothingxyz", None)]:
                html = urlopen(base + "/search/?q=" + quote(q)).read().decode()
                search[q] = {
                    "has_t0001": "/title/t-0001/" in html,
                    "empty": "Ничего не найдено" in html or "ничего не найдено" in html.lower(),
                }
        finally:
            httpd.shutdown()

    # Local target: no sampled HTML TTFB > 2500ms without exception
    over = {p: v for p, v in samples.items()
            if v["cold_ms"] > 2500 or v["warm_p95_ms"] > 2500}
    report = {
        "block": "B16",
        "mode": "local_fixture",
        "samples": samples,
        "pagination": pagination,
        "search_smoke": search,
        "TTFB_OVER_2_5S": over,
        "LOCAL_TTFB_GATE_PASS": 0 if over else 1,
        "PAGINATION_CROSS_PAGE_DUPES": pagination["cross_page_dupes"],
        "INVALID_PAGE_404": 1 if pagination["invalid_page_status"] == 404 else 0,
        "note": "Local fixture timings are not live TTFB. Live p95 still required after deploy.",
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT / "ORACLE.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                                     encoding="utf-8")
    (OUT / "PASSPORT.json").write_text(json.dumps({
        "block": "B16",
        "status": "PASS_LOCAL_PARTIAL" if report["LOCAL_TTFB_GATE_PASS"] and report["INVALID_PAGE_404"] else "FAIL_LOCAL",
        "LOCAL_TTFB_GATE_PASS": report["LOCAL_TTFB_GATE_PASS"],
        "INVALID_PAGE_404": report["INVALID_PAGE_404"],
        "PAGINATION_CROSS_PAGE_DUPES": report["PAGINATION_CROSS_PAGE_DUPES"],
        "residuals": ["live TTFB p50/p95", "full-catalog oracle", "cache policy coherence on live"],
        "updated_at": report["updated_at"],
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in (
        "LOCAL_TTFB_GATE_PASS", "INVALID_PAGE_404", "PAGINATION_CROSS_PAGE_DUPES",
        "TTFB_OVER_2_5S")}, indent=2))
    return 0 if report["LOCAL_TTFB_GATE_PASS"] and report["INVALID_PAGE_404"] and pagination["cross_page_dupes"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
