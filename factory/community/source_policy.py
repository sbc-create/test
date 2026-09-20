"""Per-source permission matrix for community ratings (Stage04).

Native vote ledger is independent of external prior / public badge permission.
Silence or technical availability is never treated as grant.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

Decision = Literal[
    "ALLOWED_PUBLIC_INDEXED",
    "ALLOWED_PUBLIC_CLOSED_ONLY",
    "ALLOWED_INTERNAL_ONLY",
    "DENIED",
    "UNKNOWN_SAFE_FALLBACK",
]

POLICY_OBSERVED_AT = "2026-09-20T14:12:00Z"
RATING_POLICY_DIGEST = (
    "a2daf212d92ea40dc3de658806fb6f5f5cf7ae77890ff0c25f81bd89088c17d5"
)


@dataclass(frozen=True)
class SourcePolicyRow:
    source_name: str
    source_id: str
    acquisition_allowed: int
    storage_allowed: int
    internal_calculation_allowed: int
    public_display_closed_site_allowed: int
    public_display_open_site_allowed: int
    derived_formula_allowed: int
    attribution_required: int
    required_attribution: str
    freshness_requirement: str
    deletion_requirement: str
    policy_source: str
    policy_observed_at: str
    policy_digest: str
    decision: Decision
    notes: str = ""


def _row(**kwargs: Any) -> SourcePolicyRow:
    return SourcePolicyRow(**kwargs)


def build_source_policy_matrix() -> list[SourcePolicyRow]:
    """Authoritative Stage04 matrix from prior owner/docs evidence + safe fallback."""
    d = POLICY_OBSERVED_AT
    dig = RATING_POLICY_DIGEST
    return [
        _row(
            source_name="Shikimori",
            source_id="shikimori",
            acquisition_allowed=1,  # official GraphQL; no new crawl this stage
            storage_allowed=1,
            internal_calculation_allowed=1,
            public_display_closed_site_allowed=1,  # Animedia CLOSED_NOINDEX
            public_display_open_site_allowed=0,  # not granted for yummyani.site OPEN
            derived_formula_allowed=0,  # derived prior public on OPEN blocked
            attribution_required=1,
            required_attribution="Label «Shikimori»; docs/rights/shikimori-ratings.md",
            freshness_requirement="retain_existing_observation; no Stage04 network refresh",
            deletion_requirement="retain_with_provenance; CONTRACT_GATE long-term storage",
            policy_source=(
                "artifacts/evidence/ratings-ingestion-05/SOURCE_POLICY.md;"
                "community-ratings-02/SOURCE_PERMISSION_MATRIX.md;"
                "publication_scope=CLOSED_NOINDEX_ANIMEDIA_UNTIL_INDEXING_DECISION"
            ),
            policy_observed_at=d,
            policy_digest=dig,
            decision="ALLOWED_PUBLIC_CLOSED_ONLY",
            notes=(
                "Owner Stage03/04 canary auth does not expand Shikimori onto open-index Yummy. "
                "Internal calc of derived prior may run in shadow; public badges stay hidden."
            ),
        ),
        _row(
            source_name="AMD Online",
            source_id="amd_online",
            acquisition_allowed=0,
            storage_allowed=1,  # retain last-good only
            internal_calculation_allowed=0,
            public_display_closed_site_allowed=0,
            public_display_open_site_allowed=0,
            derived_formula_allowed=0,
            attribution_required=1,
            required_attribution="AMD attribution if ever shown",
            freshness_requirement="no_network; last-good retain only",
            deletion_requirement="retain_quarantine; no public projection",
            policy_source="ratings-ingestion-05 SOURCE_POLICY AMD_SOURCE_DISABLED_PERMISSION_MISSING",
            policy_observed_at=d,
            policy_digest=dig,
            decision="DENIED",
            notes="No exact site crosswalk; SKIP_PUBLIC_PROJECTION.",
        ),
        _row(
            source_name="Animedia native community rating",
            source_id="animedia_native",
            acquisition_allowed=1,
            storage_allowed=1,
            internal_calculation_allowed=1,
            public_display_closed_site_allowed=1,
            public_display_open_site_allowed=0,  # Animedia sites are CLOSED
            derived_formula_allowed=1,  # may feed Yummy prior as independent component
            attribution_required=0,
            required_attribution="",
            freshness_requirement="read_your_write_after_vote",
            deletion_requirement="user_retract_tombstone; canary hard-delete allowed",
            policy_source="rating_policy_v1 spaces.animedia; Stage02 public read allowlist",
            policy_observed_at=d,
            policy_digest=dig,
            decision="ALLOWED_PUBLIC_CLOSED_ONLY",
            notes="A=S/N from animedia ledger only; does NOT embed Shikimori.",
        ),
        _row(
            source_name="Animedia projected/blended rating",
            source_id="animedia_projected",
            acquisition_allowed=0,
            storage_allowed=0,
            internal_calculation_allowed=0,
            public_display_closed_site_allowed=0,
            public_display_open_site_allowed=0,
            derived_formula_allowed=0,
            attribution_required=1,
            required_attribution="n/a — forbidden as Yummy prior input",
            freshness_requirement="n/a",
            deletion_requirement="n/a",
            policy_source="rating_policy_v1 double_count_guard; LINEAGE_DOUBLE_COUNT.md",
            policy_observed_at=d,
            policy_digest=dig,
            decision="DENIED",
            notes="Legacy blend/projected must not enter Yummy prior (may embed externals).",
        ),
        _row(
            source_name="Yummy native community rating",
            source_id="yummy_native",
            acquisition_allowed=1,
            storage_allowed=1,
            internal_calculation_allowed=1,
            public_display_closed_site_allowed=0,  # yummy org/biz closed tenants separate
            public_display_open_site_allowed=0,  # Stage04: shadow only; no public write UI
            derived_formula_allowed=0,
            attribution_required=0,
            required_attribution="",
            freshness_requirement="read_your_write_after_vote",
            deletion_requirement="ordinary retract=tombstone; canary hard-delete allowed",
            policy_source=(
                "rating_policy_v1 spaces.yummy; "
                "OWNER_AUTHORIZATION_ID=COMMUNITY-RATINGS-04-YUMMY-NATIVE-CANARY-20260920"
            ),
            policy_observed_at=d,
            policy_digest=dig,
            decision="ALLOWED_INTERNAL_ONLY",
            notes=(
                "Ledger independent of Shikimori display permission. "
                "Supervised canary cast/update/retract in shadow; public endpoint stays off."
            ),
        ),
        _row(
            source_name="Kinopoisk (provider feed)",
            source_id="provider_feed_kinopoisk",
            acquisition_allowed=0,  # via existing catalog feed only
            storage_allowed=1,
            internal_calculation_allowed=0,  # not in community prior
            public_display_closed_site_allowed=1,
            public_display_open_site_allowed=1,  # existing vitrine, not community layer
            derived_formula_allowed=0,
            attribution_required=1,
            required_attribution="КП",
            freshness_requirement="provider_feed",
            deletion_requirement="catalog_owned",
            policy_source="community-ratings-02 SOURCE_PERMISSION_MATRIX KEEP_EXISTING_VITRINE",
            policy_observed_at=d,
            policy_digest=dig,
            decision="ALLOWED_PUBLIC_INDEXED",
            notes="Existing catalog vitrine only; never enters Yummy community prior.",
        ),
        _row(
            source_name="IMDb (provider feed)",
            source_id="provider_feed_imdb",
            acquisition_allowed=0,
            storage_allowed=1,
            internal_calculation_allowed=0,
            public_display_closed_site_allowed=1,
            public_display_open_site_allowed=1,
            derived_formula_allowed=0,
            attribution_required=1,
            required_attribution="IMDb",
            freshness_requirement="provider_feed",
            deletion_requirement="catalog_owned",
            policy_source="community-ratings-02 SOURCE_PERMISSION_MATRIX KEEP_EXISTING_VITRINE",
            policy_observed_at=d,
            policy_digest=dig,
            decision="ALLOWED_PUBLIC_INDEXED",
            notes="Existing catalog vitrine only; never enters Yummy community prior.",
        ),
    ]


def matrix_digest(rows: list[SourcePolicyRow] | None = None) -> str:
    rows = rows or build_source_policy_matrix()
    payload = [asdict(r) for r in rows]
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def get_source(source_id: str) -> SourcePolicyRow:
    for r in build_source_policy_matrix():
        if r.source_id == source_id:
            return r
    raise KeyError(source_id)


def yummy_open_external_prior_allowed() -> bool:
    """True only if Shikimori (or other external) may appear in public derived prior on OPEN Yummy."""
    shiki = get_source("shikimori")
    return (
        shiki.public_display_open_site_allowed == 1
        and shiki.derived_formula_allowed == 1
        and shiki.decision in ("ALLOWED_PUBLIC_INDEXED",)
    )


def yummy_source_policy_branch() -> dict[str, Any]:
    """Independent contours + branch selection for Stage04."""
    open_prior = yummy_open_external_prior_allowed()
    branch = (
        "EXTERNAL_PRIOR_PUBLIC_ALLOWED"
        if open_prior
        else "NATIVE_ONLY_SAFE_FALLBACK"
    )
    return {
        "SOURCE_POLICY_BRANCH": branch,
        "YUMMY_SOURCE_POLICY_PASS": 1 if open_prior else 0,
        "PUBLIC_DISPLAY_PERMISSION_SHIKIMORI": get_source(
            "shikimori"
        ).public_display_open_site_allowed,
        "PUBLIC_DERIVATION_PERMISSION_SHIKIMORI": get_source(
            "shikimori"
        ).derived_formula_allowed,
        "PUBLIC_DISPLAY_PERMISSION_ANIMEDIA_NATIVE": get_source(
            "animedia_native"
        ).public_display_closed_site_allowed,
        "contours": {
            "YUMMY_NATIVE_VOTE_LEDGER": {
                "depends_on_shikimori_display": False,
                "canary_allowed": True,
                "public_write_enabled": False,
            },
            "YUMMY_EXTERNAL_PRIOR": {
                "open_site_public": open_prior,
                "internal_shadow_calc": True,
                "components_allowed": ["animedia_native", "shikimori"],
                "components_forbidden": ["animedia_projected", "amd_online"],
            },
            "YUMMY_PUBLIC_RATING_DISPLAY": {
                "external_badges": 0,
                "derived_prior_public": 0,
                "native_shadow": 1,
            },
            "YUMMY_STRUCTURED_DATA": {
                "aggregateRating_emitted": 0,
            },
        },
        "SOURCE_POLICY_DIGEST": matrix_digest(),
        "observed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def write_evidence(path: Path) -> dict[str, Any]:
    rows = build_source_policy_matrix()
    branch = yummy_source_policy_branch()
    doc = {
        "RATING_POLICY_DIGEST": RATING_POLICY_DIGEST,
        "SOURCE_POLICY_DIGEST": branch["SOURCE_POLICY_DIGEST"],
        "branch": branch,
        "matrix": [asdict(r) for r in rows],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return doc
