"""Zona description coverage / duplicate quality report (no invented text)."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def _norm(text: str) -> str:
    t = unicodedata.normalize("NFKC", (text or "").lower()).replace("ё", "е")
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", t).strip()


def _digest(text: str) -> str:
    return hashlib.sha256(_norm(text).encode("utf-8")).hexdigest()


def _trigrams(text: str) -> set[str]:
    n = _norm(text)
    if len(n) < 12:
        return set()
    return {n[i : i + 3] for i in range(len(n) - 2)}


def analyze_details(details: dict) -> dict:
    """Scan nova-details sidecar: coverage, exact/near duplicates, missing."""
    records = details.get("details") or {}
    by_digest: dict[str, list[str]] = defaultdict(list)
    missing = []
    valid = []
    near_groups = []
    for slug, det in records.items():
        if not isinstance(det, dict):
            continue
        full = (det.get("description") or "").strip()
        short = (det.get("short_description") or "").strip()
        text = full or short
        if not text:
            missing.append({
                "slug": slug,
                "quality_state": "MISSING_DESCRIPTION",
                "canonical_title_id": det.get("id") or slug,
            })
            continue
        dig = _digest(text)
        by_digest[dig].append(slug)
        valid.append({
            "slug": slug,
            "canonical_title_id": det.get("id") or slug,
            "content_digest": dig,
            "language": "ru",
            "quality_state": "HAS_DESCRIPTION",
            "source": det.get("description_source") or "details_sidecar",
            "length": len(text),
            "has_distinct_short": bool(short and short != full),
        })

    exact_dupes = {d: slugs for d, slugs in by_digest.items() if len(slugs) > 1}

    # Near-duplicate: Jaccard of trigrams >= 0.92 and different digests
    sample = valid[:8000]  # bound work on huge catalogs
    used = set()
    for i, a in enumerate(sample):
        if a["slug"] in used:
            continue
        ta = _trigrams(next(
            (records[a["slug"]].get("description")
             or records[a["slug"]].get("short_description") or "")
            for _ in [0]))
        if not ta:
            continue
        group = [a["slug"]]
        for b in sample[i + 1 : i + 400]:
            if b["content_digest"] == a["content_digest"]:
                continue
            tb = _trigrams(records[b["slug"]].get("description")
                           or records[b["slug"]].get("short_description") or "")
            if not tb:
                continue
            j = len(ta & tb) / max(1, len(ta | tb))
            if j >= 0.92:
                group.append(b["slug"])
                used.add(b["slug"])
        if len(group) > 1:
            near_groups.append(group)
            used.add(a["slug"])

    total = len(records)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "titles_total": total,
        "with_description": len(valid),
        "missing_description": len(missing),
        "description_coverage_percent": round(100.0 * len(valid) / total, 2) if total else 0.0,
        "exact_cross_title_duplicate_groups": len(exact_dupes),
        "exact_duplicate_examples": [
            {"digest": d[:16], "slugs": slugs[:8], "count": len(slugs)}
            for d, slugs in list(exact_dupes.items())[:20]
        ],
        "near_duplicate_description_groups": len(near_groups),
        "near_duplicate_examples": near_groups[:20],
        "missing_sample": missing[:50],
        "backfilled": 0,
        "note": "Backfill only via approved content pipeline; no invented synopsis.",
    }


def main() -> int:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--details", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()
    data = json.loads(Path(args.details).read_text(encoding="utf-8"))
    report = analyze_details(data)
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")
    print(json.dumps({k: report[k] for k in (
        "titles_total", "with_description", "missing_description",
        "description_coverage_percent", "exact_cross_title_duplicate_groups",
        "near_duplicate_description_groups", "backfilled")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
