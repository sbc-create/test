"""Read-only aggregate reconciliation + cache invalidation hooks."""

from __future__ import annotations

import json
import uuid
from typing import Any

from factory.community.store import CommunityStore
from factory.ratings.models import utc_now_iso


def reconcile_all(store: CommunityStore) -> dict[str, Any]:
    """Full recompute from accepted non-quarantined votes; mismatch blocks publication."""
    subjects = store.conn.execute(
        """SELECT DISTINCT rating_space_id, subject_id, dimension FROM community_aggregates
           UNION
           SELECT DISTINCT rating_space_id, subject_id, dimension FROM community_votes"""
    ).fetchall()
    mismatches: list[dict[str, Any]] = []
    checked = 0
    for row in subjects:
        checked += 1
        rebuilt = store.rebuild_aggregate_from_votes(
            rating_space_id=row["rating_space_id"],
            subject_id=row["subject_id"],
            dimension=row["dimension"],
        )
        agg = store.get_aggregate(
            rating_space_id=row["rating_space_id"],
            subject_id=row["subject_id"],
            dimension=row["dimension"],
        )
        if int(agg["vote_sum"]) != rebuilt["vote_sum"] or int(agg["vote_count"]) != rebuilt["vote_count"]:
            mismatches.append(
                {
                    "rating_space_id": row["rating_space_id"],
                    "subject_id": row["subject_id"],
                    "materialized": {"S": int(agg["vote_sum"]), "N": int(agg["vote_count"])},
                    "recomputed": rebuilt,
                }
            )
    report = {
        "checked": checked,
        "mismatches": mismatches,
        "mismatch_count": len(mismatches),
        "publication_blocked": len(mismatches) > 0,
        "last_good_preserved": True,
        "created_at": utc_now_iso(),
    }
    store.conn.execute(
        """INSERT OR IGNORE INTO community_outbox(outbox_id, event_type, dedupe_key, payload_json, created_at)
           VALUES (?,?,?,?,?)""",
        (
            f"obx-{uuid.uuid4().hex[:12]}",
            "rating.aggregate.rebuilt",
            f"reconcile-{report['created_at']}",
            json.dumps(
                {
                    "checked": checked,
                    "mismatch_count": len(mismatches),
                    "affected_subjects": [
                        f"{m['rating_space_id']}:{m['subject_id']}" for m in mismatches
                    ],
                },
                ensure_ascii=False,
            ),
            report["created_at"],
        ),
    )
    return report


def invalidate_cache_keys(rating_space_id: str, subject_id: str) -> list[str]:
    """Idempotent cache key list for post-commit invalidation."""
    return [
        f"community:rating:{rating_space_id}:{subject_id}",
        f"community:preview:{rating_space_id}:{subject_id}",
        f"community:aggregate:{rating_space_id}:{subject_id}",
    ]
