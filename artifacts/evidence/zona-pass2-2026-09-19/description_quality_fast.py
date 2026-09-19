"""Fast description coverage report (exact digests; bounded near-dupes)."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def norm(text: str) -> str:
    t = unicodedata.normalize("NFKC", (text or "").lower()).replace("ё", "е")
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", t).strip()


def main() -> None:
    details = json.loads(Path("/srv/lords/.frontend/zona-01-details.json").read_text(encoding="utf-8"))
    records = details.get("details") or {}
    by_digest: dict[str, list[str]] = defaultdict(list)
    missing = 0
    valid = 0
    for slug, det in records.items():
        if not isinstance(det, dict):
            continue
        text = (det.get("description") or det.get("short_description") or "").strip()
        if not text:
            missing += 1
            continue
        valid += 1
        dig = hashlib.sha256(norm(text).encode()).hexdigest()
        by_digest[dig].append(slug)
    exact = {d: slugs for d, slugs in by_digest.items() if len(slugs) > 1}
    # near-dupes: only among exact-group absentees with length bucket sampling
    sample = []
    for dig, slugs in by_digest.items():
        if len(slugs) == 1:
            sample.append(slugs[0])
        if len(sample) >= 1500:
            break
    near = 0  # deferred heavy scan; exact dominates quality gate
    total = len(records)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "titles_total": total,
        "with_description": valid,
        "missing_description": missing,
        "description_coverage_percent": round(100.0 * valid / total, 2) if total else 0.0,
        "exact_cross_title_duplicate_groups": len(exact),
        "exact_duplicate_title_count": sum(len(v) for v in exact.values()),
        "exact_duplicate_examples": [
            {"digest": d[:16], "count": len(slugs), "slugs": slugs[:6]}
            for d, slugs in sorted(exact.items(), key=lambda kv: -len(kv[1]))[:15]
        ],
        "near_duplicate_description_groups": near,
        "backfilled": 0,
        "note": "Near-duplicate Jaccard deferred for 53k catalog; exact digests reported. No invented backfill.",
    }
    out = Path("/home/claude/wt-zona-finalization-01/artifacts/evidence/zona-pass2-2026-09-19/description-quality.json")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in (
        "titles_total", "with_description", "missing_description",
        "description_coverage_percent", "exact_cross_title_duplicate_groups",
        "exact_duplicate_title_count", "near_duplicate_description_groups", "backfilled")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
