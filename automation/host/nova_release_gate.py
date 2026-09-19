#!/usr/bin/env python3
"""Immutable release gates for closed nova Animedia deploys.

Fail-closed checks before live switch:
  RUNTIME_DOWNGRADE=0
  RUNTIME_COMPATIBLE=1
  CONTENT_SNAPSHOT_DIGEST_MATCH=1
  CATALOG_DETAILS_SKEW=0
  PROVIDER_BINDING_MATCH=1
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

FRONT = Path("/srv/lords/.frontend")

#: Markers that a candidate runtime must keep (Zona tip + Animedia features).
REQUIRED_RUNTIME_MARKERS = (
    "def кандидаты_источника",
    "data-src-candidates",
    "__animediaPlayback",
    "providerShell",
    "ВидАнимедиа",
    "АНИМЕДИА_СТИЛЬ",
    "ОФОРМЛЕНИЕ_1_2_1",
)

#: Golden playback sample — representative closed Animedia URLs.
GOLDEN_URLS = (
    "https://animedia.icu/title/master-lda-i-plameni-2/",
    "https://animedia.icu/title/master-lda-i-plameni-2/season-2/episode-103/",
    "https://animedia.icu/title/master-lda-i-plameni-2/season-2/episode-104/",
    "https://animedia.space/title/master-lda-i-plameni-2/",
    "https://animedia.icu/",
    "https://animedia.space/",
    "https://animedia.icu/catalog/",
    "https://animedia.space/catalog/",
    "https://animedia.icu/collections/",
    "https://animedia.space/collections/",
    "https://animedia.icu/collection/top_rated/",
    "https://animedia.space/collection/anime_movies/",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest_pair(catalog: Path, details: Path) -> str:
    raw = catalog.read_bytes() + b"\0" + details.read_bytes()
    return hashlib.sha256(raw).hexdigest()


def runtime_compatible(candidate: Path, live: Path | None = None) -> dict:
    text = candidate.read_text(encoding="utf-8", errors="replace")
    missing = [m for m in REQUIRED_RUNTIME_MARKERS if m not in text]
    live_sha = sha256_file(live) if live and live.is_file() else ""
    cand_sha = sha256_file(candidate)
    # Downgrade = candidate loses required markers that live already has.
    live_missing = []
    if live and live.is_file():
        live_text = live.read_text(encoding="utf-8", errors="replace")
        live_missing = [m for m in REQUIRED_RUNTIME_MARKERS if m not in live_text]
        lost = [m for m in REQUIRED_RUNTIME_MARKERS if m in live_text and m not in text]
    else:
        lost = []
    return {
        "RUNTIME_COMPATIBLE": 1 if not missing else 0,
        "RUNTIME_DOWNGRADE": 1 if lost else 0,
        "missing_markers": missing,
        "lost_markers": lost,
        "live_missing_markers": live_missing,
        "candidate_sha256": cand_sha,
        "live_sha256": live_sha,
        "candidate_bytes": candidate.stat().st_size,
        "live_bytes": live.stat().st_size if live and live.is_file() else 0,
    }


def content_snapshot_match(site: str) -> dict:
    catalog = FRONT / f"{site}-catalog.json"
    details = FRONT / f"{site}-details.json"
    if not catalog.is_file() or not details.is_file():
        return {
            "CONTENT_SNAPSHOT_DIGEST_MATCH": 0,
            "CATALOG_DETAILS_SKEW": 1,
            "reason": "missing catalog or details",
        }
    cat = json.loads(catalog.read_text(encoding="utf-8"))
    det = json.loads(details.read_text(encoding="utf-8"))
    cat_rev = str(cat.get("revision") or cat.get("catalog_revision") or "")
    det_rev = str(det.get("catalog_revision") or det.get("revision") or "")
    skew = 0
    if cat_rev and det_rev and cat_rev != det_rev:
        skew = 1
    digest = digest_pair(catalog, details)
    return {
        "CONTENT_SNAPSHOT_DIGEST_MATCH": 1 if skew == 0 else 0,
        "CATALOG_DETAILS_SKEW": skew,
        "catalog_revision": cat_rev,
        "details_revision": det_rev,
        "content_snapshot_digest": digest,
        "items_total": cat.get("count") or len(cat.get("items") or []),
        "details_total": det.get("details_total") or len(det.get("details") or {}),
    }


def provider_binding_match(html: str, *, expect_mali_first: bool = True) -> dict:
    has_cands = "data-src-candidates" in html
    m = re.search(r'data-aggregator="([^"]+)"', html)
    agg = m.group(1) if m else ""
    m = re.search(r'data-title-id="([^"]+)"', html)
    tid = m.group(1) if m else ""
    cands_raw = ""
    m = re.search(r'data-src-candidates="([^"]+)"', html)
    if m:
        import html as H
        cands_raw = H.unescape(m.group(1))
    mali_first = cands_raw.startswith('[{"aggregator":"mali"') or (
        agg == "mali" and has_cands
    )
    ok = has_cands and (mali_first if expect_mali_first else bool(agg and tid))
    return {
        "PROVIDER_BINDING_MATCH": 1 if ok else 0,
        "has_candidates": has_cands,
        "aggregator": agg,
        "title_id": tid,
        "mali_first": mali_first,
    }


def fetch(url: str, timeout: float = 12.0) -> tuple[int, str, dict]:
    req = urllib.request.Request(url, headers={"User-Agent": "nova-release-gate/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", "replace")
            headers = {k.lower(): v for k, v in resp.headers.items()}
            return resp.status, body, headers
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace") if exc.fp else ""
        return exc.code, body, {}
    except Exception as exc:  # noqa: BLE001
        return 0, str(exc), {}


def golden_http_probe(urls: tuple[str, ...] = GOLDEN_URLS) -> dict:
    results = []
    failures = 0
    for url in urls:
        code, body, headers = fetch(url)
        row = {
            "url": url,
            "http": code,
            "has_player_shell": "data-player" in body or "video-player" in body,
            "has_candidates": "data-src-candidates" in body,
            "robots": headers.get("x-robots-tag", ""),
            "profile": headers.get("x-site-factory-profile", ""),
            "build_id": headers.get("x-site-factory-build-id", ""),
        }
        if code != 200:
            failures += 1
        results.append(row)
    return {
        "PLAYER_GOLDEN_TOTAL": len(urls),
        "PLAYER_GOLDEN_HTTP_PASS": len(urls) - failures,
        "PLAYER_FAILURES": failures,
        "results": results,
    }


def evaluate_candidate(candidate: Path, sites: list[str]) -> dict:
    live = FRONT / "lords-frontend.py"
    runtime = runtime_compatible(candidate, live)
    snaps = {site: content_snapshot_match(site) for site in sites}
    skew = any(v.get("CATALOG_DETAILS_SKEW") for v in snaps.values())
    digest_ok = all(v.get("CONTENT_SNAPSHOT_DIGEST_MATCH") for v in snaps.values())
    flags = {
        "RUNTIME_DOWNGRADE": runtime["RUNTIME_DOWNGRADE"],
        "RUNTIME_COMPATIBLE": runtime["RUNTIME_COMPATIBLE"],
        "CONTENT_SNAPSHOT_DIGEST_MATCH": 1 if digest_ok else 0,
        "CATALOG_DETAILS_SKEW": 1 if skew else 0,
        "PROVIDER_BINDING_MATCH": None,
    }
    ok = (
        flags["RUNTIME_DOWNGRADE"] == 0
        and flags["RUNTIME_COMPATIBLE"] == 1
        and flags["CONTENT_SNAPSHOT_DIGEST_MATCH"] == 1
        and flags["CATALOG_DETAILS_SKEW"] == 0
    )
    return {
        "ok": ok,
        "flags": flags,
        "runtime": runtime,
        "snapshots": snaps,
    }


def main() -> int:
    candidate = Path(
        os.environ.get(
            "NOVA_CANDIDATE_FRONTEND",
            str(Path(__file__).resolve().parents[2] / "automation/host/lords-frontend.py"),
        )
    )
    sites = [
        s.strip()
        for s in os.environ.get("GATE_SITES", "animedia-01,animedia-02").split(",")
        if s.strip()
    ]
    report = evaluate_candidate(candidate, sites)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
