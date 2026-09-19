"""Stage 5 deterministic priority queue — uncovered Shikimori-eligible only."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from factory.ratings.catalog import load_catalog_json
from factory.ratings.mapping import resolve_mapping
from factory.ratings.models import CatalogTitle
from factory.ratings.stage5_constants import (
    ACCEPTED_TARGET,
    CANDIDATE_CAP,
    SOURCE_ALLOWED,
)
from factory.ratings.store import RatingsStore

# Higher tier score = earlier in queue (DESC).
TIER_ONGOING = 600
TIER_CURRENT_SEASON = 500
TIER_NEW_30D = 400
TIER_RECENTLY_UPDATED = 300
TIER_POPULAR = 200
TIER_TAIL = 100

TIER_LABELS = {
    TIER_ONGOING: "ongoing",
    TIER_CURRENT_SEASON: "current_season",
    TIER_NEW_30D: "new_30_days",
    TIER_RECENTLY_UPDATED: "recently_updated",
    TIER_POPULAR: "popular_playable",
    TIER_TAIL: "tail",
}


@dataclass(frozen=True)
class QueueCandidate:
    canonical_title_id: str
    external_id: str
    mapping_method: str
    mapping_confidence: float
    tier: int
    tier_label: str
    priority_score: int
    updated_at: str
    title: str
    year: int | None
    kind: str


def _mal_or_shiki(title: CatalogTitle) -> str | None:
    ext = title.external_ids or {}
    for k in ("shikimori", "shikimori_id", "myanimelist", "mal", "mal_id"):
        if ext.get(k):
            return str(ext[k])
    return None


def classify_tier(title: CatalogTitle) -> tuple[int, str]:
    if title.is_ongoing or title.has_new_episode:
        return TIER_ONGOING, TIER_LABELS[TIER_ONGOING]
    days = title.days_since_release
    if title.is_seasonal or (days is not None and days <= 120 and (title.kind or "") == "tv"):
        return TIER_CURRENT_SEASON, TIER_LABELS[TIER_CURRENT_SEASON]
    if days is not None and days <= 30:
        return TIER_NEW_30D, TIER_LABELS[TIER_NEW_30D]
    if days is not None and days <= 180:
        return TIER_RECENTLY_UPDATED, TIER_LABELS[TIER_RECENTLY_UPDATED]
    if title.is_popular or title.on_home_or_top:
        return TIER_POPULAR, TIER_LABELS[TIER_POPULAR]
    return TIER_TAIL, TIER_LABELS[TIER_TAIL]


def _covered_shikimori_ids(store: RatingsStore | None) -> set[str]:
    if store is None:
        return set()
    rows = store.conn.execute(
        """SELECT canonical_title_id FROM rating_current
           WHERE source_key=? AND normalized_score IS NOT NULL AND vote_count IS NOT NULL
             AND vote_count > 0""",
        (SOURCE_ALLOWED,),
    ).fetchall()
    return {r["canonical_title_id"] for r in rows}


def _quarantined_ids(store: RatingsStore | None) -> set[str]:
    if store is None:
        return set()
    out: set[str] = set()
    try:
        rows = store.conn.execute(
            """SELECT canonical_title_id FROM rating_review_queue
               WHERE source_key=? AND state IN ('OPEN','QUARANTINED','AMBIGUOUS')""",
            (SOURCE_ALLOWED,),
        ).fetchall()
        out.update(r["canonical_title_id"] for r in rows)
    except Exception:  # noqa: BLE001
        pass
    return out


def build_priority_queue(
    *,
    catalog_path: Path,
    store: RatingsStore | None = None,
    candidate_cap: int = CANDIDATE_CAP,
    accepted_target: int = ACCEPTED_TARGET,
    run_id: str,
    frozen_catalog_digest: str = "",
) -> dict[str, Any]:
    """Build deterministic uncovered exact-mapped Shikimori queue (≤ candidate_cap)."""
    titles = load_catalog_json(catalog_path)
    covered = _covered_shikimori_ids(store)
    quarantined = _quarantined_ids(store)

    ranked: list[QueueCandidate] = []
    mapping_audit: list[dict[str, Any]] = []
    quarantine: list[dict[str, Any]] = []
    skipped = {
        "covered": 0,
        "no_external_id": 0,
        "ambiguous": 0,
        "unmatched": 0,
        "quarantined": 0,
        "invalid": 0,
        "amd_only": 0,
    }

    for title in titles:
        cid = title.canonical_title_id
        if cid.startswith("amd_online:"):
            skipped["amd_only"] += 1
            continue
        if cid in covered:
            skipped["covered"] += 1
            continue
        if cid in quarantined:
            skipped["quarantined"] += 1
            continue
        if not _mal_or_shiki(title):
            skipped["no_external_id"] += 1
            continue

        decision = resolve_mapping(title, source_key=SOURCE_ALLOWED)
        if decision.conflict_reason or (
            decision.review_candidates and not decision.auto_publish
        ):
            reason = decision.conflict_reason or "AMBIGUOUS"
            quarantine.append(
                {
                    "canonical_title_id": cid,
                    "result": "AMBIGUOUS_QUARANTINED",
                    "reason": reason,
                }
            )
            skipped["ambiguous"] += 1
            mapping_audit.append(
                {
                    "internal_title_id": cid,
                    "shikimori_id": "",
                    "mapping_method": "",
                    "mapping_version": "stage5_v1",
                    "mapping_confidence": 0.0,
                    "result": "AMBIGUOUS_QUARANTINED",
                }
            )
            continue
        if not decision.mapping or not decision.auto_publish:
            quarantine.append(
                {
                    "canonical_title_id": cid,
                    "result": "UNMATCHED_QUARANTINED",
                    "reason": "no_exact_mapping",
                }
            )
            skipped["unmatched"] += 1
            mapping_audit.append(
                {
                    "internal_title_id": cid,
                    "shikimori_id": "",
                    "mapping_method": "",
                    "mapping_version": "stage5_v1",
                    "mapping_confidence": 0.0,
                    "result": "UNMATCHED_QUARANTINED",
                }
            )
            continue

        m = decision.mapping
        tier, label = classify_tier(title)
        # priority_score: prefer popular/home within tier (higher better for DESC)
        score = 0
        if title.on_home_or_top:
            score += 1000
        if title.is_popular:
            score += 500
        if title.has_new_episode:
            score += 200
        if title.days_since_release is not None:
            score += max(0, 200 - int(title.days_since_release))

        updated = title.first_seen_at or ""
        cand = QueueCandidate(
            canonical_title_id=cid,
            external_id=str(m.external_title_id),
            mapping_method=m.mapping_method.value
            if hasattr(m.mapping_method, "value")
            else str(m.mapping_method),
            mapping_confidence=float(m.confidence),
            tier=tier,
            tier_label=label,
            priority_score=score,
            updated_at=updated,
            title=title.title or title.russian_title,
            year=title.year,
            kind=title.kind,
        )
        ranked.append(cand)
        mapping_audit.append(
            {
                "internal_title_id": cid,
                "shikimori_id": cand.external_id,
                "mapping_method": cand.mapping_method,
                "mapping_version": "stage5_v1",
                "mapping_confidence": cand.mapping_confidence,
                "result": "EXACT_MATCH",
                "registry_digest": "",
            }
        )

    # Stable order: tier DESC, priority_score DESC, updated_at DESC, title_id ASC
    ranked.sort(
        key=lambda c: (
            -c.tier,
            -c.priority_score,
            -( _ts_key(c.updated_at)),
            c.canonical_title_id,
        )
    )
    selected = ranked[: max(0, int(candidate_cap))]

    # Duplicate ID check
    ids = [c.canonical_title_id for c in selected]
    ext_ids = [c.external_id for c in selected]
    dup_ids = len(ids) - len(set(ids))
    dup_ext = len(ext_ids) - len(set(ext_ids))

    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    candidate_payload = [
        {
            "canonical_title_id": c.canonical_title_id,
            "external_id": c.external_id,
            "mapping_method": c.mapping_method,
            "mapping_confidence": c.mapping_confidence,
            "tier": c.tier,
            "tier_label": c.tier_label,
            "priority_score": c.priority_score,
            "updated_at": c.updated_at,
            "title": c.title,
            "year": c.year,
            "kind": c.kind,
        }
        for c in selected
    ]
    digest_src = json.dumps(
        {
            "run_id": run_id,
            "source": SOURCE_ALLOWED,
            "candidate_cap": candidate_cap,
            "ids": ids,
            "tiers": [c.tier_label for c in selected],
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    queue_digest = hashlib.sha256(digest_src.encode()).hexdigest()

    tier_breakdown: dict[str, int] = {}
    for c in selected:
        tier_breakdown[c.tier_label] = tier_breakdown.get(c.tier_label, 0) + 1

    # Fill registry digests for exact matches in selected
    for row in mapping_audit:
        if row["result"] != "EXACT_MATCH":
            continue
        blob = f"{row['internal_title_id']}|{row['shikimori_id']}|{row['mapping_method']}|stage5_v1"
        row["registry_digest"] = hashlib.sha256(blob.encode()).hexdigest()[:16]

    return {
        "run_id": run_id,
        "created_at": created_at,
        "frozen_catalog_digest": frozen_catalog_digest,
        "source": SOURCE_ALLOWED,
        "candidate_cap": candidate_cap,
        "accepted_target": accepted_target,
        "priority_tiers": TIER_LABELS,
        "tier_breakdown": tier_breakdown,
        "candidate_ids": ids,
        "candidates": candidate_payload,
        "mapping_method": "exact_shikimori_id_or_mal_crosswalk_only",
        "current_coverage_state": {
            "shikimori_covered_excluded": skipped["covered"],
            "eligible_exact_ranked": len(ranked),
            "selected": len(selected),
        },
        "skipped": skipped,
        "QUEUE_SOURCE": SOURCE_ALLOWED,
        "QUEUE_CANDIDATE_COUNT": len(selected),
        "QUEUE_COVERED_TITLE_COUNT": 0,  # by construction
        "QUEUE_AMD_ONLY_COUNT": 0,  # filtered out before select
        "QUEUE_AMBIGUOUS_COUNT": 0,  # quarantined, not queued
        "QUEUE_DUPLICATE_IDS": dup_ids,
        "QUEUE_DUPLICATE_EXTERNAL_IDS": dup_ext,
        "queue_digest": queue_digest,
        "mapping_audit": mapping_audit,
        "quarantine": quarantine,
        "gates": {
            "QUEUE_SOURCE": SOURCE_ALLOWED,
            "QUEUE_CANDIDATE_COUNT_OK": len(selected) <= candidate_cap,
            "QUEUE_COVERED_TITLE_COUNT": 0,
            "QUEUE_AMD_ONLY_COUNT": 0,
            "QUEUE_AMBIGUOUS_COUNT": 0,
            "QUEUE_DUPLICATE_IDS": dup_ids,
        },
    }


def _ts_key(value: str) -> int:
    if not value:
        return 0
    try:
        return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())
    except ValueError:
        return 0


def replay_digest(manifest: dict[str, Any]) -> str:
    digest_src = json.dumps(
        {
            "run_id": manifest["run_id"],
            "source": manifest["source"],
            "candidate_cap": manifest["candidate_cap"],
            "ids": manifest["candidate_ids"],
            "tiers": [c["tier_label"] for c in manifest["candidates"]],
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(digest_src.encode()).hexdigest()
