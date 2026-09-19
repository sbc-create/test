#!/usr/bin/env python3
"""Animedia ratings source registry (CLOSED_WORLD).

Canonical sources with inventory/contract evidence may be ENABLED.
Owner-spoken names without a verified origin stay UNVERIFIED/DISABLED —
no network fetch, no rename-by-guess to MAL/AniList/etc.
"""

from __future__ import annotations

from typing import Any

#: Verified / provisional registry. Keys are stable source ids.
RATING_SOURCES: dict[str, dict[str, Any]] = {
    "shikimori": {
        "name": "Shikimori",
        "canonical_origin": "https://shikimori.one",
        "api_base": "https://shikimori.one/api",
        "adapter_version": "1.0.0",
        "score_scale": 10.0,
        "has_vote_count": True,
        "rate_limit": "documented-api; respect Retry-After",
        "freshness_hours": 168,
        "access_legal_evidence": (
            "Official HTTP JSON API; HTML scraping forbidden by factory policy. "
            "Storage of score/votes/ids allowed as observed facts with provenance."
        ),
        "state": "ENABLED",
        "last_successful_fetch": None,
        "health": "UNKNOWN",
    },
    "kp": {
        "name": "КП",
        "canonical_origin": "kinopoisk",
        "adapter_version": "legacy-details-field",
        "score_scale": 10.0,
        "has_vote_count": False,
        "rate_limit": "n/a-snapshot",
        "freshness_hours": None,
        "access_legal_evidence": "Values arrive only via approved catalog/details snapshot.",
        "state": "ENABLED_SNAPSHOT",
        "last_successful_fetch": None,
        "health": "SNAPSHOT",
    },
    "imdb": {
        "name": "IMDb",
        "canonical_origin": "imdb",
        "adapter_version": "legacy-details-field",
        "score_scale": 10.0,
        "has_vote_count": True,
        "rate_limit": "n/a-snapshot",
        "freshness_hours": None,
        "access_legal_evidence": "Values arrive only via approved catalog/details snapshot.",
        "state": "ENABLED_SNAPSHOT",
        "last_successful_fetch": None,
        "health": "SNAPSHOT",
    },
    # Owner-spoken names — no inventory match for a distinct canonical API.
    "shikimuni": {
        "name": "Шикимуни",
        "canonical_origin": None,
        "adapter_version": None,
        "score_scale": None,
        "has_vote_count": None,
        "rate_limit": None,
        "freshness_hours": None,
        "access_legal_evidence": None,
        "state": "UNVERIFIED/DISABLED",
        "reason": (
            "Owner-spoken name «Шикимуни» has no verified inventory/config/contract "
            "entry distinct from Shikimori. Not aliased by guess."
        ),
        "last_successful_fetch": None,
        "health": "DISABLED",
    },
    "nisa_media": {
        "name": "Nisa Media",
        "canonical_origin": None,
        "adapter_version": None,
        "score_scale": None,
        "has_vote_count": None,
        "rate_limit": None,
        "freshness_hours": None,
        "access_legal_evidence": None,
        "state": "UNVERIFIED/DISABLED",
        "reason": (
            "Owner-spoken name «Nisa Media» has no verified inventory/config/contract "
            "entry. Not renamed to MAL/AniList/other by guess; no network fetch."
        ),
        "last_successful_fetch": None,
        "health": "DISABLED",
    },
}


def unresolved_owner_names() -> list[str]:
    return [
        row["name"]
        for row in RATING_SOURCES.values()
        if row.get("state") == "UNVERIFIED/DISABLED"
    ]


def enabled_source_keys() -> list[str]:
    return [
        key
        for key, row in RATING_SOURCES.items()
        if str(row.get("state", "")).startswith("ENABLED")
    ]
