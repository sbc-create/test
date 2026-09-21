#!/usr/bin/env python3
"""Start the COMMUNITY-RATINGS-08 observation window — only if it is real.

COMMUNITY-RATINGS-07 ran a 15.5 hour window that measured nothing, because the
widget was never on the page. A clock alone is not an observation. This script
refuses to record a start time unless every condition below holds at once:

  1. the widget loader is present on a live title page;
  2. its JS and CSS assets are served 200;
  3. the rollout is exactly 1% and writes are enabled and unkilled;
  4. the durable metrics store is reachable;
  5. the store has recorded at least one eligible cohort impression AND at
     least one widget-rendered beacon — i.e. a real visitor in the 1% cohort
     has actually been shown the widget;
  6. yummyani.site is still OPEN to indexing.

It changes no flag and enables nothing. It only reads, judges, and — when the
answer is yes — writes the start marker into evidence.
"""

from __future__ import annotations

import json
import re
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/home/claude/wt-ratings-ingestion-01")

from factory.community import metrics_store  # noqa: E402

EVIDENCE = Path(
    "/home/claude/wt-ratings-ingestion-01/artifacts/evidence/community-ratings-08/06-observation"
)
MARKER = EVIDENCE / "OBSERVATION_WINDOW.json"
FLAGS = Path("/srv/site-factory/repo/var/ratings/community_rollout_flags.json")

SITE = "https://yummyani.site"
TITLE_PATHS = (
    "/anime/padshiy-master",
    "/anime/chernyy-fakel",
    "/anime/neprevzoydennyy",
    "/anime/istoriya-o-perekure-za-supermarketom",
)
ASSETS = (
    "/assets/community/community_rating.js",
    "/assets/community/community_rating.css",
)

CTX = ssl.create_default_context()


def fetch(url: str, timeout: int = 25):
    req = urllib.request.Request(url, headers={"User-Agent": "cr08-observation/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as fh:
            return fh.status, fh.read().decode("utf-8", "replace"), dict(fh.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, "", dict(exc.headers or {})
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}", {}


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    checks: dict = {"checked_at": now}

    pages = {}
    for path in TITLE_PATHS:
        status, body, _ = fetch(SITE + path)
        pages[path] = {
            "status": status,
            "loader_nodes": body.count('id="cr-widget-loader"'),
            "aggregate_rating": "aggregateRating" in body,
        }
    checks["title_pages"] = pages
    checks["C1_widget_on_live_pages"] = any(p["loader_nodes"] == 1 for p in pages.values())
    checks["no_structured_aggregate_rating"] = not any(p["aggregate_rating"] for p in pages.values())

    assets = {}
    for path in ASSETS:
        status, _, headers = fetch(SITE + path)
        assets[path] = {"status": status, "content_type": headers.get("Content-Type")}
    checks["assets"] = assets
    checks["C2_assets_served"] = all(a["status"] == 200 for a in assets.values())

    try:
        flags = json.loads(FLAGS.read_text(encoding="utf-8"))
    except Exception as exc:
        flags = {}
        checks["flags_error"] = str(exc)
    checks["flags"] = {
        k: flags.get(k)
        for k in (
            "PUBLIC_WRITE_ENABLED",
            "PUBLIC_WRITE_ROLLOUT_PERCENT",
            "PUBLIC_WRITE_MAX_PERCENT",
            "KILL_SWITCH",
            "READ_ONLY",
        )
    }
    checks["C3_rollout_exactly_1pct_and_live"] = (
        flags.get("PUBLIC_WRITE_ROLLOUT_PERCENT") == 1
        and int(flags.get("PUBLIC_WRITE_ENABLED") or 0) == 1
        and int(flags.get("KILL_SWITCH") or 0) == 0
        and int(flags.get("READ_ONLY") or 0) == 0
    )

    metrics_store.reset_cache()
    snap = metrics_store.snapshot(
        kill_switch_state=int(flags.get("KILL_SWITCH") or 0),
        rollout_percent=int(flags.get("PUBLIC_WRITE_ROLLOUT_PERCENT") or 0),
    )
    checks["C4_metrics_store_reachable"] = snap["store_reachable"]
    checks["metrics_store_path"] = snap["store_path"]
    checks["metrics"] = snap["metrics"]
    checks["unmeasured"] = snap["unmeasured"]

    impressions = snap["metrics"].get("eligible_cohort_impressions")
    rendered = snap["metrics"].get("widget_rendered")
    exposed = snap["metrics"].get("exposed_visitors")
    checks["C5_real_exposure_recorded"] = (
        isinstance(impressions, int) and impressions > 0
        and isinstance(rendered, int) and rendered > 0
        and isinstance(exposed, int) and exposed > 0
    )
    checks["exposure"] = {
        "eligible_cohort_impressions": impressions,
        "widget_rendered": rendered,
        "exposed_visitors": exposed,
    }

    status, body, headers = fetch(SITE + "/")
    robots_status, robots_body, _ = fetch(SITE + "/robots.txt")
    meta = re.search(r'<meta[^>]*name=["\']robots["\'][^>]*content=["\']([^"\']*)', body, re.I)
    xr = (headers.get("X-Robots-Tag") or "").lower()
    checks["indexability"] = {
        "root_status": status,
        "x_robots": headers.get("X-Robots-Tag"),
        "meta_robots": meta.group(1) if meta else None,
        "robots_disallow_all": bool(re.search(r"^\s*Disallow:\s*/\s*$", robots_body, re.I | re.M)),
    }
    checks["C6_indexability_open"] = (
        "noindex" not in xr
        and not checks["indexability"]["robots_disallow_all"]
        and (meta is None or "noindex" not in meta.group(1).lower())
    )

    conditions = {k: v for k, v in checks.items() if k.startswith("C")}
    ready = all(conditions.values())
    checks["ALL_CONDITIONS"] = conditions
    checks["READY_TO_START"] = ready

    if MARKER.exists():
        existing = json.loads(MARKER.read_text(encoding="utf-8"))
        if existing.get("OBSERVATION_STARTED_AT"):
            checks["ALREADY_STARTED_AT"] = existing["OBSERVATION_STARTED_AT"]
            checks["ACTION"] = "none — window already open"
            print(json.dumps(checks, indent=2, ensure_ascii=False))
            return 0

    if ready:
        checks["OBSERVATION_STARTED_AT"] = now
        checks["MIN_24H_COMPLETE_AT"] = (
            datetime.strptime(now, "%Y-%m-%dT%H:%M:%SZ")
            .replace(tzinfo=timezone.utc)
            .replace(microsecond=0)
        ).isoformat().replace("+00:00", "Z")
        checks["ACTION"] = "window opened"
        checks["PREVIOUS_WINDOW_DISCARDED"] = (
            "COMMUNITY-RATINGS-07: 15.544h with 0 eligible impressions — no exposure, not counted"
        )
    else:
        checks["ACTION"] = "not started — conditions not met"
        checks["FAILED_CONDITIONS"] = [k for k, v in conditions.items() if not v]

    EVIDENCE.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(json.dumps(checks, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(checks, indent=2, ensure_ascii=False))
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
