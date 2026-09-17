"""Versioned topical-relevance decisions for query -> URL pairs.

A relevance decision is never inferred from keyword overlap alone. It has to
account for the query's classified intent, the entity/taxonomy the query
actually names, what the landing page is tagged as, rendered evidence that the
page answers the query, and whether another site in the portfolio already
claims the same query for the same entity (portfolio non-compete / query
ownership).

Reuses :class:`seo_operator.priority.QueryClass` for intent rather than
defining a second taxonomy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from seo_operator.priority import QueryClass

#: Revision of the relevance-decision rules below. Bumped whenever the
#: decision logic itself changes, independent of the frequency-band policy
#: revision.
RELEVANCE_POLICY_REVISION = 1


class RelevanceVerdict(str, Enum):
    APPROVED_RELEVANT = "APPROVED_RELEVANT"
    AMBIGUOUS = "AMBIGUOUS"
    OFF_TOPIC = "OFF_TOPIC"
    SUSPICIOUS_REQUIRES_REVIEW = "SUSPICIOUS_REQUIRES_REVIEW"


@dataclass(frozen=True)
class RelevanceDecision:
    """A ``TopicalRelevanceDecision``: versioned, dated, and never silent about why."""

    verdict: RelevanceVerdict
    reason: str
    policy_revision: int
    decided_at: str

    @property
    def sync_eligible(self) -> bool:
        """Only APPROVED_RELEVANT may ever become eligible for a future sync."""
        return self.verdict is RelevanceVerdict.APPROVED_RELEVANT


@dataclass(frozen=True)
class RelevanceInput:
    site_id: str
    query: str
    normalized_query: str
    entity_id: str
    taxonomy_id: str
    intent: QueryClass
    target_url: str
    landing_page_taxonomy_id: str
    #: None: no rendered check was captured. True/False: it was, and what it found.
    rendered_evidence_confirmed: bool | None
    #: Other distinct entity IDs the raw query title also matches (homonymy).
    homonym_entity_ids: tuple[str, ...] = ()


class OwnershipConflict(RuntimeError):
    """A different site already owns this (query, entity) pair."""


@dataclass
class OwnershipIndex:
    """Tracks which site first claimed a (normalized_query, taxonomy_id) pair.

    Two sites in the same portfolio approving the same query for the same
    entity is a non-compete violation to flag, not a coincidence to wave
    through. The index is in-memory and scoped to one manifest build; it is
    not a registry of its own.
    """

    _claims: dict[tuple[str, str], str] = field(default_factory=dict)

    def owner_of(self, normalized_query: str, taxonomy_id: str) -> str | None:
        return self._claims.get((normalized_query, taxonomy_id))

    def claim(self, normalized_query: str, taxonomy_id: str, site_id: str) -> None:
        self._claims[(normalized_query, taxonomy_id)] = site_id


def decide_relevance(
    data: RelevanceInput,
    *,
    ownership: OwnershipIndex,
    now: datetime,
) -> RelevanceDecision:
    """Decide topical relevance for one query -> URL pair. Fails closed.

    Order matters and is deliberate: a wrong landing page is worse than an
    ambiguous title, ambiguity is worse than missing rendered evidence, and
    none of those are overridden by an otherwise-clean ownership check.
    """
    decided_at = now.isoformat()

    if data.landing_page_taxonomy_id != data.taxonomy_id:
        return RelevanceDecision(
            RelevanceVerdict.OFF_TOPIC,
            f"landing page {data.target_url!r} is tagged {data.landing_page_taxonomy_id!r}, "
            f"but the query targets taxonomy {data.taxonomy_id!r}: wrong landing page",
            RELEVANCE_POLICY_REVISION,
            decided_at,
        )

    if len(data.homonym_entity_ids) > 1:
        return RelevanceDecision(
            RelevanceVerdict.AMBIGUOUS,
            f"query title matches {len(data.homonym_entity_ids)} distinct entities "
            f"({', '.join(sorted(data.homonym_entity_ids))}); title text alone cannot resolve it",
            RELEVANCE_POLICY_REVISION,
            decided_at,
        )

    if data.rendered_evidence_confirmed is None:
        return RelevanceDecision(
            RelevanceVerdict.SUSPICIOUS_REQUIRES_REVIEW,
            "no rendered-page evidence was captured to confirm the landing page answers the query",
            RELEVANCE_POLICY_REVISION,
            decided_at,
        )
    if data.rendered_evidence_confirmed is False:
        return RelevanceDecision(
            RelevanceVerdict.OFF_TOPIC,
            "rendered evidence contradicts the query: the page does not actually answer it",
            RELEVANCE_POLICY_REVISION,
            decided_at,
        )

    existing_owner = ownership.owner_of(data.normalized_query, data.taxonomy_id)
    if existing_owner is not None and existing_owner != data.site_id:
        return RelevanceDecision(
            RelevanceVerdict.SUSPICIOUS_REQUIRES_REVIEW,
            f"query already approved for site {existing_owner!r}; {data.site_id!r} "
            "claiming the same query for the same entity is a portfolio "
            "non-compete / query-ownership conflict",
            RELEVANCE_POLICY_REVISION,
            decided_at,
        )

    ownership.claim(data.normalized_query, data.taxonomy_id, data.site_id)
    return RelevanceDecision(
        RelevanceVerdict.APPROVED_RELEVANT,
        f"intent {data.intent.value} matches landing page taxonomy {data.taxonomy_id!r}; "
        "rendered evidence confirmed; no ownership conflict",
        RELEVANCE_POLICY_REVISION,
        decided_at,
    )
