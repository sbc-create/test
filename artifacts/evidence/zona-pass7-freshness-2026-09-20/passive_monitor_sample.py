#!/usr/bin/env python3
"""Passive Zona-only freshness telemetry sample (no paid external services).

Writes a daily JSON report under artifacts/ or a configured directory.
Does not mutate production catalogs. Safe to run read-only against live headers
and authorized snapshot files.
"""
from __future__ import annotations

import hashlib
import json
import ssl
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

CAT = Path("/srv/lords/.frontend/zona-01-catalog.json")
DET = Path("/srv/lords/.frontend/zona-01-details.json")
DOMAIN = "https://zonafilm.space"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    cat = json.loads(CAT.read_text(encoding="utf-8"))
    det = json.loads(DET.read_text(encoding="utf-8"))
    items = cat.get("items") or []
    newest = max((i.get("published_at") or "" for i in items), default="")
    ctx = ssl.create_default_context()
    req = urllib.request.Request(
        DOMAIN + "/", headers={"User-Agent": "zona-freshness-monitor", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=45, context=ctx) as r:
        headers = dict(r.headers.items())
        body = r.read().decode("utf-8", "replace")
    report = {
        "at_utc": datetime.now(timezone.utc).isoformat(),
        "catalog_revision": cat.get("revision"),
        "catalog_sha256": sha(CAT),
        "details_sha256": sha(DET),
        "catalog_count": len(items),
        "details_count": len(det.get("details") or {}),
        "catalog_built_at": cat.get("builtAt"),
        "latest_catalog_published_at": newest,
        "live_build": headers.get("X-Site-Factory-Build-Id"),
        "live_catalog_revision": headers.get("X-Catalog-Revision"),
        "cache_control": headers.get("Cache-Control"),
        "robots": headers.get("X-Robots-Tag"),
        "honest_labels_present": (
            "Высокий рейтинг среди недавних" in body
            and "Недавно добавленные сериалы" in body
        ),
        "stale_sixth_shelf": "Недавно в каталоге" in body,
        "episode_timestamps_available": False,
        "note": "SOURCE_TO_LIVE remains INCONCLUSIVE without upstream event timestamps",
    }
    out = Path("artifacts/evidence/zona-pass7-freshness-2026-09-20/DAILY_REPORT_LIVE_SAMPLE.json")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
