"""Stage 5 source policy gates — Shikimori only; AMD network forbidden."""

from __future__ import annotations

from typing import Any

from factory.ratings.source_policy import amd_policy, gate_summary, shikimori_policy
from factory.ratings.stage5_constants import (
    CONCURRENCY,
    RATE_LIMIT_RPS,
    SOURCE_ALLOWED,
    SOURCE_DISABLED,
)


class UnauthorizedSourceError(RuntimeError):
    pass


def stage5_shikimori_policy() -> dict[str, Any]:
    base = shikimori_policy().as_dict()
    return {
        **base,
        "SOURCE_POLICY_RESOLVED": "YES",
        "API_CONTRACT": "POST https://shikimori.io/api/graphql; animes(ids:String CSV, limit:Int<=50); "
        "fields id,malId,name,russian,score,scoresStats{score,count},updatedAt,url",
        "ATTRIBUTION_CONTRACT": "docs/rights/shikimori-ratings.md; score labelled Shikimori not MAL; "
        "CONTRACT_GATE attribution/long-term storage undocumented — provenance retained",
        "RATE_LIMIT_RPS": RATE_LIMIT_RPS,
        "CONCURRENCY": CONCURRENCY,
        "FIELDS_ALLOWED": [
            "id",
            "malId",
            "name",
            "russian",
            "score",
            "scoresStats",
            "updatedAt",
            "url",
        ],
        "FIELDS_REJECTED": [
            "html_scrape",
            "rest_v1",
            "rest_v2",
            "mal_score_as_shikimori",
            "browser_ua_spoof",
        ],
        "stage5_override_note": "Stage5 pilot caps RPS at 0.1 regardless of upstream 5 rps / operational 2 rps",
    }


def stage5_amd_policy() -> dict[str, Any]:
    base = amd_policy().as_dict()
    return {
        **base,
        "AMD_SOURCE_STATUS": "DISABLED_PERMISSION_MISSING",
        "AMD_NETWORK_CALLS": 0,
        "AMD_RECURRING_FETCHES": 0,
        "AMD_LAST_GOOD_PRESERVED": 1,
        "forbidden_actions": [
            "AMD GET",
            "HTML fetch",
            "robots probe",
            "canary",
            "refresh",
            "parser test via network",
        ],
    }


def assert_live_source_allowed(source: str) -> str:
    key = (source or "").strip().lower()
    if key in SOURCE_DISABLED or key.startswith("amd"):
        raise UnauthorizedSourceError(
            f"source {source!r} disabled for Stage5 live cycle (AMD/unauthorized)"
        )
    if key != SOURCE_ALLOWED:
        raise UnauthorizedSourceError(
            f"source {source!r} not authorized; only {SOURCE_ALLOWED} allowed"
        )
    return key


def source_isolation_gates(*, active_source: str = SOURCE_ALLOWED) -> dict[str, Any]:
    assert_live_source_allowed(active_source)
    g = gate_summary()
    return {
        **g,
        "ACTIVE_SOURCE_COUNT": 1,
        "ACTIVE_SOURCE": active_source,
        "AMD_CALLS": 0,
        "UNAUTHORIZED_SOURCE_CALLS": 0,
        "SOURCE_RATE_LIMIT_CONFIGURED": 1,
        "SOURCE_CONCURRENCY": CONCURRENCY,
        "SOURCE_RATE_LIMIT_RPS": RATE_LIMIT_RPS,
        "shikimori": stage5_shikimori_policy(),
        "amd": stage5_amd_policy(),
    }
