"""Closed noindex snapshot publication for animedia.icu / animedia.space."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any

from factory.ratings.prod_db import SRV_RATINGS_DIR
from factory.ratings.snapshot import atomic_publish_candidate, validate_snapshot

CLOSED_DOMAINS = ("animedia.icu", "animedia.space")
ATTRIBUTION = "Источник: AMD.online"


def snapshot_live_path(domain: str) -> Path:
    return SRV_RATINGS_DIR / "snapshots" / domain / "ratings_snapshot_v1.json"


def publish_closed_snapshots(
    body: dict[str, Any],
    *,
    evidence_dir: Path,
) -> dict[str, Any]:
    errors = validate_snapshot(body)
    if errors:
        raise ValueError(f"snapshot invalid: {errors}")

    results: dict[str, Any] = {"domains": {}, "public_indexed": False}
    for domain in CLOSED_DOMAINS:
        live = snapshot_live_path(domain)
        live.parent.mkdir(parents=True, exist_ok=True)
        pub_live = atomic_publish_candidate(body, live)
        ev = evidence_dir / "closed-noindex" / domain / "ratings_snapshot_v1.json"
        pub_ev = atomic_publish_candidate(body, ev)
        meta = {
            "domain": domain,
            "indexing": "noindex",
            "publication_mode": "CLOSED_NOINDEX",
            "public_indexed": False,
            "live_path": str(live),
            "evidence_path": str(ev),
            "live": pub_live,
            "evidence": pub_ev,
            "attribution_required": ATTRIBUTION,
            "robots_policy": "noindex, nofollow (closed nova)",
        }
        (evidence_dir / "closed-noindex" / domain / "PUBLICATION.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        results["domains"][domain] = meta
    return results


def verify_noindex_http(domains: tuple[str, ...] = CLOSED_DOMAINS) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for domain in domains:
        url = f"https://{domain}/"
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "site-factory-ratings/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
                headers = {k.lower(): v for k, v in resp.headers.items()}
                status = resp.status
        except Exception as exc:  # noqa: BLE001
            out[domain] = {"ok": False, "error": str(exc)}
            continue
        xrobots = headers.get("x-robots-tag", "")
        noindex = "noindex" in xrobots.lower()
        # robots.txt
        robots_txt = ""
        try:
            rreq = urllib.request.Request(
                f"https://{domain}/robots.txt",
                headers={"User-Agent": "site-factory-ratings/1.0"},
            )
            with urllib.request.urlopen(rreq, timeout=15) as rresp:  # noqa: S310
                robots_txt = rresp.read().decode("utf-8", errors="replace")[:2000]
        except Exception as exc:  # noqa: BLE001
            robots_txt = f"error:{exc}"
        disallow_all = "Disallow: /" in robots_txt
        out[domain] = {
            "ok": noindex and disallow_all,
            "http_status": status,
            "x_robots_tag": xrobots,
            "robots_disallow_all": disallow_all,
            "robots_excerpt": robots_txt[:300],
            "sitemap_new_urls_from_ratings": 0,
        }
    return out
