"""Deterministic rotation / ranking: animedia_rotation_v1.

Does not mutate AMD source scores — only internal card order.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import Any

ROTATION_ALGORITHM_VERSION = "animedia_rotation_v1"


def sort_for_rotation(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    def sort_key(r: dict[str, Any]):
        raw = r.get("rotation_score")
        if raw is None:
            raw = r.get("combined_raw")
        combined = Decimal(str(raw)) if raw is not None else None
        combined_key = Decimal("-Infinity") if combined is None else -combined
        local_key = -int(r.get("local_vote_count") or 0)
        amd_key = (
            (1, 0)
            if r.get("amd_vote_count") is None
            else (0, -int(r["amd_vote_count"]))
        )
        freshness = r.get("updated_at") or ""
        fresh_sort = (
            (0 if freshness else 1),
            "".join(chr(255 - ord(c)) for c in freshness[:32]) if freshness else "",
        )
        cid = r.get("canonical_title_id") or ""
        return (combined_key, local_key, amd_key, fresh_sort, cid)

    ranked = sorted(rows, key=sort_key)
    out = []
    for i, row in enumerate(ranked, start=1):
        item = dict(row)
        item["rotation_rank"] = i
        item["rotation_algorithm_version"] = ROTATION_ALGORITHM_VERSION
        out.append(item)
    return out
