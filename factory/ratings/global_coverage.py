"""Global per-source coverage inventory (no mass external fetches)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from factory.ratings.catalog import load_catalog_json
from factory.ratings.coverage_policy import is_covered_row


@dataclass
class CoverageCell:
    title_id: str
    source: str
    title_type: str
    lifecycle: str  # ongoing/completed/unknown
    new_30_days: bool
    catalog_tail: bool
    mapping: str  # mapped/unmapped/ambiguous
    freshness: str  # current/stale/missing


def classify_lifecycle(title) -> str:
    if title.is_ongoing:
        return "ongoing"
    if title.days_since_release is not None and title.days_since_release > 180:
        return "completed"
    if title.days_since_release is not None:
        return "completed"
    return "unknown"


def build_global_inventory(
    *,
    catalog_path: Path,
    db_path: Path,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    titles = load_catalog_json(catalog_path)
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    # Covered by source from rating_current
    covered: dict[tuple[str, str], dict] = {}
    for row in conn.execute("SELECT * FROM rating_current"):
        key = (row["canonical_title_id"], row["source_key"])
        covered[key] = dict(row)

    # Mappings
    maps: dict[tuple[str, str], dict] = {}
    for row in conn.execute("SELECT * FROM title_source_mappings"):
        maps[(row["canonical_title_id"], row["source_key"])] = dict(row)

    # AMD rows use amd_online:{id} — not nova catalog ids
    amd_covered = sum(
        1
        for (cid, src), row in covered.items()
        if src == "amd_online" and is_covered_row(score=row.get("normalized_score"), vote_count=row.get("vote_count"))
    )
    stale = sum(1 for row in covered.values() if row.get("freshness") == "STALE")

    # Shikimori eligible = catalog titles with mal/shikimori external id
    shiki_eligible_ids: list[str] = []
    for t in titles:
        ext = t.external_ids or {}
        if ext.get("shikimori") or ext.get("myanimelist") or ext.get("mal"):
            shiki_eligible_ids.append(t.canonical_title_id)

    # AMD: no catalog crosswalk → eligible unknown beyond current mapped set
    # Document AMD_ELIGIBLE as "mapped_in_db_or_absence" for inventory honesty
    amd_mapped = [
        r["canonical_title_id"]
        for r in conn.execute(
            "SELECT DISTINCT canonical_title_id FROM title_source_mappings WHERE source_key='amd_online'"
        )
    ]
    amd_absence = [
        r["canonical_title_id"]
        for r in conn.execute(
            "SELECT DISTINCT canonical_title_id FROM rating_source_absence WHERE source_key='amd_online'"
        )
    ]
    amd_eligible = sorted(set(amd_mapped) | set(amd_absence))

    ongoing = [t for t in titles if t.is_ongoing]
    new30 = [t for t in titles if t.days_since_release is not None and t.days_since_release <= 30]
    # catalog tail: not new30, not ongoing, older than 180d or unknown
    tail = [
        t
        for t in titles
        if not t.is_ongoing
        and (t.days_since_release is None or t.days_since_release > 180)
    ]

    # Per-source uncovered among eligible
    shiki_covered_nova = 0
    for cid in shiki_eligible_ids:
        row = covered.get((cid, "shikimori"))
        if row and is_covered_row(score=row.get("normalized_score"), vote_count=row.get("vote_count")):
            shiki_covered_nova += 1

    shiki_uncovered = len(shiki_eligible_ids) - shiki_covered_nova
    # AMD uncovered cannot be estimated from catalog without mapping — use eligible - covered
    amd_uncovered = max(0, len(amd_eligible) - amd_covered)

    # Global source-target pairs: every title × {shikimori if eligible} + amd only when mapped
    global_source_target = len(shiki_eligible_ids) + len(amd_eligible)
    global_covered = shiki_covered_nova + amd_covered
    global_uncovered = global_source_target - global_covered

    def eta(uncovered: int, rate: int) -> str | None:
        if rate <= 0:
            return None
        days = (uncovered + rate - 1) // rate
        return f"~{days}d"

    # Ongoing uncovered for shikimori-eligible ongoing
    ongoing_uncovered = 0
    for t in ongoing:
        if t.canonical_title_id not in shiki_eligible_ids:
            continue
        row = covered.get((t.canonical_title_id, "shikimori"))
        if not (row and is_covered_row(score=row.get("normalized_score"), vote_count=row.get("vote_count"))):
            ongoing_uncovered += 1

    new30_uncovered = 0
    for t in new30:
        if t.canonical_title_id not in shiki_eligible_ids:
            continue
        row = covered.get((t.canonical_title_id, "shikimori"))
        if not (row and is_covered_row(score=row.get("normalized_score"), vote_count=row.get("vote_count"))):
            new30_uncovered += 1

    # Primary backlog for ETA: shikimori uncovered (authorized source) + note AMD blocked
    backlog_for_eta = shiki_uncovered

    out = {
        "catalog_path": str(catalog_path),
        "db_path": str(db_path),
        "as_of": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": (
            "Canary cohort 150 is NOT the global denominator. "
            "AMD has no catalog crosswalk; AMD_ELIGIBLE = DB-mapped/absence only. "
            "AMD new fetches DISABLED (permission missing). "
            "Shikimori eligible = MAL/shikimori external_ids in lords-01 catalog."
        ),
        "GLOBAL_TITLE_TOTAL": len(titles),
        "GLOBAL_SOURCE_TARGET_TOTAL": global_source_target,
        "GLOBAL_COVERED_TOTAL": global_covered,
        "GLOBAL_UNCOVERED_TOTAL": global_uncovered,
        "GLOBAL_STALE_TOTAL": stale,
        "AMD_ELIGIBLE_TOTAL": len(amd_eligible),
        "AMD_COVERED_TOTAL": amd_covered,
        "AMD_COVERAGE_PERCENT": round(100.0 * amd_covered / len(amd_eligible), 2) if amd_eligible else None,
        "SHIKIMORI_ELIGIBLE_TOTAL": len(shiki_eligible_ids),
        "SHIKIMORI_COVERED_TOTAL": shiki_covered_nova,
        "SHIKIMORI_COVERAGE_PERCENT": round(100.0 * shiki_covered_nova / len(shiki_eligible_ids), 2)
        if shiki_eligible_ids
        else None,
        "ONGOING_TOTAL": len(ongoing),
        "ONGOING_UNCOVERED": ongoing_uncovered,
        "ONGOING_COVERAGE_PERCENT": round(
            100.0 * (len(ongoing) - ongoing_uncovered) / len(ongoing), 2
        )
        if ongoing
        else None,
        "NEW_30_DAYS_TOTAL": len(new30),
        "NEW_30_DAYS_UNCOVERED": new30_uncovered,
        "NEW_30_DAYS_COVERAGE_PERCENT": round(
            100.0 * (len([t for t in new30 if t.canonical_title_id in shiki_eligible_ids]) - new30_uncovered)
            / max(1, len([t for t in new30 if t.canonical_title_id in shiki_eligible_ids])),
            2,
        ),
        "TAIL_TOTAL": len(tail),
        "TAIL_UNCOVERED": None,  # filled below for shiki-eligible tail
        "BACKLOG_FOR_ETA": backlog_for_eta,
        "BACKLOG_ETA_AT_100": eta(backlog_for_eta, 100),
        "BACKLOG_ETA_AT_250": eta(backlog_for_eta, 250),
        "BACKLOG_ETA_AT_500": eta(backlog_for_eta, 500),
        "STAGE3_CANARY_COHORT_NOT_GLOBAL": True,
        "stage3_canary_accepted": 100,
        "stage3_candidate_cap": 150,
    }
    tail_shiki = [t for t in tail if t.canonical_title_id in shiki_eligible_ids]
    tail_unc = 0
    for t in tail_shiki:
        row = covered.get((t.canonical_title_id, "shikimori"))
        if not (row and is_covered_row(score=row.get("normalized_score"), vote_count=row.get("vote_count"))):
            tail_unc += 1
    out["TAIL_UNCOVERED"] = tail_unc
    conn.close()
    return out
