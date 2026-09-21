#!/usr/bin/env python3
"""Live smoke for COMMUNITY-RATINGS-08 on yummyani.site.

Read-only. Run it twice: once before the owner deploys, to record the baseline
and prove the change is what flipped the result, and again after.
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

SITE = "https://yummyani.site"
TITLES = (
    "/anime/padshiy-master",
    "/anime/chernyy-fakel",
    "/anime/neprevzoydennyy",
    "/anime/istoriya-o-perekure-za-supermarketom",
)
ASSETS = (
    "/assets/community/community_rating.js",
    "/assets/community/community_rating.css",
)
API = (
    "/api/community/ratings/flags",
    "/api/community/ratings/session",
)
OTHER_DOMAINS = ("animedia.icu", "animedia.space")

CTX = ssl.create_default_context()
UA_DESKTOP = "Mozilla/5.0 (X11; Linux x86_64) cr08-smoke/1.0"
UA_MOBILE = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) cr08-smoke/1.0"


def fetch(url: str, ua: str = UA_DESKTOP, timeout: int = 25):
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as fh:
            return fh.status, fh.read().decode("utf-8", "replace"), dict(fh.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, "", dict(exc.headers or {})
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}", {}


def indexability(host: str) -> dict:
    status, body, headers = fetch(f"https://{host}/")
    _, robots, _ = fetch(f"https://{host}/robots.txt")
    meta = re.search(r'<meta[^>]*name=["\']robots["\'][^>]*content=["\']([^"\']*)', body, re.I)
    xr = (headers.get("X-Robots-Tag") or "").lower()
    disallow_all = bool(re.search(r"^\s*Disallow:\s*/\s*$", robots, re.I | re.M))
    closed = "noindex" in xr or disallow_all or (meta and "noindex" in meta.group(1).lower())
    return {
        "status": status,
        "x_robots": headers.get("X-Robots-Tag"),
        "meta_robots": meta.group(1) if meta else None,
        "robots_disallow_all": disallow_all,
        "verdict": "CLOSED_NOINDEX" if closed else "OPEN",
    }


def main() -> int:
    label = sys.argv[1] if len(sys.argv) > 1 else "run"
    out: dict = {
        "label": label,
        "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "site": SITE,
    }

    status, home, _ = fetch(SITE + "/")
    out["home"] = {"status": status, "bytes": len(home), "loader_nodes": home.count("cr-widget-loader")}

    pages = {}
    for path in TITLES:
        for device, ua in (("desktop", UA_DESKTOP), ("mobile", UA_MOBILE)):
            st, body, headers = fetch(SITE + path, ua)
            pages[f"{path}::{device}"] = {
                "status": st,
                "bytes": len(body),
                "loader_nodes": body.count('id="cr-widget-loader"'),
                "loader_before_body_end": bool(
                    re.search(r'<script id="cr-widget-loader".*?</script>\s*</body>', body, re.S)
                ),
                "subject_attr": (
                    re.search(r'data-subject="([^"]+)"', body).group(1)
                    if 'data-subject="' in body else None
                ),
                "aggregate_rating": "aggregateRating" in body,
                "shikimori_mentioned": "shikimori" in body.lower(),
                "html_closed": body.rstrip().endswith("</html>"),
                "content_length_header": headers.get("Content-Length"),
                "content_length_matches": (
                    headers.get("Content-Length") is None
                    or int(headers["Content-Length"]) == len(body.encode("utf-8", "replace"))
                ),
            }
    out["title_pages"] = pages
    out["WIDGET_MARKUP_PRESENT"] = any(p["loader_nodes"] == 1 for p in pages.values())

    assets = {}
    for path in ASSETS:
        st, body, headers = fetch(SITE + path)
        assets[path] = {
            "status": st,
            "bytes": len(body),
            "content_type": headers.get("Content-Type"),
            "nosniff": headers.get("X-Content-Type-Options"),
        }
    out["assets"] = assets
    out["ASSETS_HTTP_200"] = all(a["status"] == 200 for a in assets.values())

    api = {}
    for path in API:
        st, body, _ = fetch(SITE + path)
        parsed = {}
        try:
            parsed = json.loads(body)
        except Exception:
            pass
        api[path] = {
            "status": st,
            "cohort": parsed.get("cohort"),
            "flags": parsed.get("flags"),
            "has_csrf": bool(parsed.get("csrf_token")),
        }
    out["api"] = api
    flags = (api.get("/api/community/ratings/flags") or {}).get("flags") or {}
    out["ROLLOUT_PERCENT"] = flags.get("PUBLIC_WRITE_ROLLOUT_PERCENT")
    out["KILL_SWITCH"] = flags.get("KILL_SWITCH")
    out["STRUCTURED_AGGREGATE_RATING_ENABLED"] = flags.get("STRUCTURED_AGGREGATE_RATING_ENABLED")

    session = api.get("/api/community/ratings/session") or {}
    cohort = session.get("cohort") or {}
    out["THIS_VISITOR_ELIGIBLE"] = cohort.get("eligible")
    out["COHORT_GATING_OBSERVED"] = (
        "a fresh visitor is almost always outside a 1% cohort; eligible="
        f"{cohort.get('eligible')} for this probe"
    )

    out["indexability"] = {"yummyani.site": indexability("yummyani.site")}
    for host in OTHER_DOMAINS:
        out["indexability"][host] = indexability(host)
    out["YUMMY_INDEXABILITY"] = out["indexability"]["yummyani.site"]["verdict"]
    out["ANIMEDIA_UNCHANGED"] = all(
        out["indexability"][h]["verdict"] == "CLOSED_NOINDEX" for h in OTHER_DOMAINS
    )

    out["NO_AGGREGATE_RATING_ON_PAGES"] = not any(p["aggregate_rating"] for p in pages.values())
    out["NO_SHIKIMORI_ON_PAGES"] = not any(p["shikimori_mentioned"] for p in pages.values())
    out["ALL_TITLE_PAGES_200"] = all(p["status"] == 200 for p in pages.values())
    out["ALL_HTML_CLOSED"] = all(p["html_closed"] for p in pages.values())
    out["ALL_CONTENT_LENGTH_CONSISTENT"] = all(p["content_length_matches"] for p in pages.values())

    dest = Path(__file__).resolve().parent / f"SMOKE_{label}.json"
    dest.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary = {
        k: v for k, v in out.items()
        if k.isupper() or k in ("label", "checked_at")
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
