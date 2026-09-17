"""Five distinct observation/decision entities for query and index state.

* :class:`QueryObservation` — real impressions/clicks/average position for a
  query, from search analytics (Yandex Webmaster, Google Search Console).
* :class:`RankObservation` — an approved query's exact tracked position from
  Topvisor.
* :class:`SearchIndexObservation` — provider-specific evidence that a URL is
  present in a search index.
* :class:`IndexabilityObservation` — HTTP/robots/canonical/sitemap/rendered
  evidence for a URL.
* ``TopicalRelevanceDecision`` lives in :mod:`seo_operator.relevance`; it
  consumes the four observation types above as evidence but is not one of
  them.

None of these implies another, and the types are shaped so the forbidden
inferences cannot be expressed by accident:

* :class:`RankObservation` has no field that could be read as "indexed" —
  a tracked position is not proof of index presence.
* :class:`IndexabilityObservation.proves_indexed` is always ``False``: crawl
  and indexability evidence, however complete, is not a search-index check.
* Nothing here accepts a bare query as the subject of an index directive —
  :func:`noindex_directive` only accepts ``subject_kind="url"``.
"""
from __future__ import annotations

from dataclasses import dataclass


class ObservationError(ValueError):
    """Raised when a caller tries to construct or use an observation dishonestly."""


#: Sources allowed to produce a QueryObservation. Matches the source names
#: already registered in seo_operator.datasources.live (kind="search_analytics").
QUERY_OBSERVATION_SOURCES = ("yandex_webmaster", "google_search_console")

#: Sources allowed to produce a RankObservation. Matches factory.topvisor.
RANK_OBSERVATION_SOURCES = ("topvisor",)


@dataclass(frozen=True)
class QueryObservation:
    """Real impressions/clicks/average position for one query.

    Every metric is ``None``, never ``0``, when the source did not report it.
    """

    site_id: str
    domain: str
    query: str
    source: str
    period_start: str
    period_end: str
    impressions: int | None = None
    clicks: int | None = None
    average_position: float | None = None

    def __post_init__(self) -> None:
        if self.source not in QUERY_OBSERVATION_SOURCES:
            raise ObservationError(f"unknown query observation source: {self.source!r}")


@dataclass(frozen=True)
class RankObservation:
    """An approved query's tracked position from Topvisor.

    Carries no field about index presence: a tracked, even a good, position
    says nothing about whether the URL is currently in the index.
    """

    site_id: str
    domain: str
    query: str
    source: str
    position: int | None
    checked_at: str
    searcher: str
    region: str

    def __post_init__(self) -> None:
        if self.source not in RANK_OBSERVATION_SOURCES:
            raise ObservationError(f"unknown rank observation source: {self.source!r}")


@dataclass(frozen=True)
class SearchIndexObservation:
    """Provider-specific evidence that a URL is, or is not, present in an index.

    This is the only one of the five entities that may assert index presence.
    """

    site_id: str
    url: str
    provider: str
    indexed: bool
    checked_at: str
    evidence_ref: str


@dataclass(frozen=True)
class IndexabilityObservation:
    """HTTP/robots/canonical/sitemap/rendered evidence for one URL.

    Each flag is ``None`` when it was not checked; ``None`` is not "assume
    fine". :attr:`fully_confirmed_indexable` is only ``True`` when every flag
    is known and green — and even then it does not claim the URL is indexed.
    """

    site_id: str
    url: str
    status_code: int | None = None
    robots_allowed: bool | None = None
    canonical_matches_self: bool | None = None
    in_sitemap: bool | None = None
    rendered_ok: bool | None = None
    checked_at: str = ""

    @property
    def fully_confirmed_indexable(self) -> bool:
        flags = (
            self.robots_allowed, self.canonical_matches_self,
            self.in_sitemap, self.rendered_ok,
        )
        return self.status_code == 200 and all(flag is True for flag in flags)

    @property
    def proves_indexed(self) -> bool:
        """Indexability evidence never proves the URL is actually indexed.

        Only a :class:`SearchIndexObservation` can make that claim. This
        property exists so a caller who reaches for "is it indexed?" on the
        wrong type gets an explicit ``False`` rather than an absent attribute
        that might get silently treated as truthy elsewhere.
        """
        return False


def noindex_directive(subject: str, *, subject_kind: str) -> str:
    """Build a noindex directive. Only ``subject_kind="url"`` is accepted.

    A query cannot be closed to indexing — noindex is an HTTP-header/meta-tag
    instruction that a page serves about itself. Calling this for a query
    (or anything else that is not a URL) is rejected, not silently narrowed.
    """
    if subject_kind != "url":
        raise ObservationError(
            f"noindex cannot target a {subject_kind} ({subject!r}); "
            "noindex is a URL-level directive only"
        )
    return subject
