"""Stage 4 source policy records and fetch authorization."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class SourcePolicy:
    source: str
    access_method: str
    public_api_or_html: str
    robots_status: str
    terms_status: str
    permission_status: str
    owner_use_approval: str
    allowed_rate: str
    concurrency: int
    challenge_policy: str
    publication_scope: str
    decision: str
    new_fetches_allowed: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def amd_policy() -> SourcePolicy:
    """Written commercial permission NOT_PROVIDED → disable recurring fetches.

    Closed Stage 2/3 canary was a one-shot technical probe under closed noindex.
    Stage 4 recurring Daily-100 cannot inherit that as standing authorization.
    Last-good observations remain; new AMD fetches blocked until documented grant.
    """
    return SourcePolicy(
        source="amd.online",
        access_method="public_html_detail_get",
        public_api_or_html="html_detail_only",
        robots_status="detail_html_not_disallowed; engine/user paths disallowed (robots.txt 2026-09-19)",
        terms_status="no_written_reuse_grant_on_file",
        permission_status="NOT_PROVIDED",
        owner_use_approval="closed_canary_only_stage2_3; recurring_not_approved",
        allowed_rate="0.1 rps (if authorized)",
        concurrency=1,
        challenge_policy="AUTO_STOP_NO_BYPASS",
        publication_scope="CLOSED_NOINDEX_ONLY_WHEN_AUTHORIZED",
        decision="AMD_SOURCE_DISABLED_PERMISSION_MISSING",
        new_fetches_allowed=False,
    )


def shikimori_policy() -> SourcePolicy:
    return SourcePolicy(
        source="shikimori",
        access_method="official_graphql",
        public_api_or_html="graphql_api",
        robots_status="robots_disallow_/api/*_for_crawlers; official_API_client_per_docs/rights",
        terms_status="CONTRACT_GATE_attribution_long_term_storage_undocumented",
        permission_status="granted_for_factory_ratings_adapter",
        owner_use_approval="docs/rights/shikimori-ratings.md Stage1+; HTML scrape forbidden",
        allowed_rate="<=2 rps operational (upstream 5 rps / 90 rpm)",
        concurrency=1,
        challenge_policy="circuit_on_401_403_schema_drift; no_html_fallback",
        publication_scope="CLOSED_NOINDEX_ANIMEDIA_UNTIL_INDEXING_DECISION",
        decision="SHIKIMORI_SOURCE_POLICY_RESOLVED",
        new_fetches_allowed=True,  # policy resolved; pilot may still stay off until other gates
    )


def policy_matrix() -> list[SourcePolicy]:
    return [amd_policy(), shikimori_policy()]


def gate_summary() -> dict[str, str]:
    amd = amd_policy()
    shiki = shikimori_policy()
    return {
        "AMD_SOURCE_STATUS": amd.decision,
        "SHIKIMORI_SOURCE_STATUS": shiki.decision,
        "AMD_SOURCE_AUTHORIZED_OR_DISABLED": "YES",
        "SHIKIMORI_SOURCE_POLICY_RESOLVED": "YES",
        "AMD_NEW_FETCHES_ALLOWED": "NO",
        "SHIKIMORI_NEW_FETCHES_ALLOWED": "YES_POLICY" if shiki.new_fetches_allowed else "NO",
        "AUTHORIZED_SOURCE_COUNT": "1",  # shikimori only for new fetches
    }
