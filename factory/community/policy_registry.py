"""Versioned owner policy registry for community ratings (Stage05)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from factory.community.source_policy import (
    RATING_POLICY_DIGEST,
    SourcePolicyRow,
    build_source_policy_matrix,
    matrix_digest,
    yummy_source_policy_branch,
)

OWNER_POLICY_DECISION_ID = "COMMUNITY-RATINGS-05-NATIVE-SECURITY-20260920"


def build_policy_registry() -> dict[str, Any]:
    rows = build_source_policy_matrix()
    branch = yummy_source_policy_branch()
    registry = {
        "OWNER_POLICY_DECISION_ID": OWNER_POLICY_DECISION_ID,
        "RATING_POLICY_VERSION": "rating_policy_v1",
        "RATING_POLICY_DIGEST": RATING_POLICY_DIGEST,
        "SOURCE_POLICY_DIGEST": matrix_digest(rows),
        "branch": branch,
        "sources": [asdict(r) for r in rows],
        "double_count_exclusions": [
            "animedia_projected",
            "animedia_blend",
            "amd_online_in_yummy_prior",
            "summing_vote_counts_across_sources",
        ],
        "invariants": {
            "SOURCE_LINEAGE_DOUBLE_COUNT_COUNT": 0,
            "SHIKIMORI_MAX_USES_IN_YUMMY_PRIOR": 1,
            "ANIMEDIA_NATIVE_EXCLUDES_EXTERNAL": 1,
            "YUMMY_PRIOR_PUBLICLY_VISIBLE": 0,
            "YUMMY_PUBLIC_MODE": "NATIVE_ONLY_SAFE_FALLBACK",
            "PUBLIC_NATIVE_WRITES_ENABLED": 0,
            "COMMENTS_PUBLICATION_ENABLED": 0,
        },
    }
    return registry


def write_registry(path: Path) -> dict[str, Any]:
    reg = build_policy_registry()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return reg
