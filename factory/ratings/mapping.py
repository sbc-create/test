"""Сопоставление canonical_title_id ↔ external source id.

Автоматическая публикация разрешена только:

1. Подтверждённый Shikimori ID
2. Подтверждённый MAL ID / crosswalk
3. Единственное exact normalized совпадение: title + year + kind + season +
   episode_count (или допустимый ongoing)

Fuzzy — только кандидаты в review queue, никогда auto-publish.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from factory.ratings.models import (
    CatalogTitle,
    MappingMethod,
    MappingState,
    TitleSourceMapping,
    utc_now_iso,
)

_KIND_INCOMPATIBLE = {
    ("tv", "movie"),
    ("movie", "tv"),
    ("tv", "ova"),
    ("ova", "tv"),
    ("movie", "ova"),
    ("ova", "movie"),
    ("tv", "special"),
    ("special", "tv"),
    ("movie", "special"),
    ("special", "movie"),
}


def normalize_title(text: str) -> str:
    text = unicodedata.normalize("NFKD", (text or "").lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9а-яё]+", " ", text, flags=re.I)
    return " ".join(text.split())


def _norm_kind(kind: str) -> str:
    k = (kind or "").strip().lower()
    aliases = {
        "series": "tv",
        "сериал": "tv",
        "tv": "tv",
        "movie": "movie",
        "фильм": "movie",
        "ova": "ova",
        "ona": "ona",
        "special": "special",
        "спешл": "special",
    }
    return aliases.get(k, k)


@dataclass(frozen=True)
class MappingDecision:
    mapping: TitleSourceMapping | None
    auto_publish: bool
    review_candidates: list[dict[str, Any]]
    conflict_reason: str = ""


def resolve_mapping(
    title: CatalogTitle,
    *,
    source_key: str,
    candidates: list[dict[str, Any]] | None = None,
) -> MappingDecision:
    """Определить mapping. Не публикует ambiguous/fuzzy автоматически."""
    ext = title.external_ids or {}

    # 1. Confirmed Shikimori ID
    shiki = ext.get("shikimori") or ext.get("shikimori_id")
    if shiki and source_key == "shikimori":
        return MappingDecision(
            mapping=TitleSourceMapping(
                canonical_title_id=title.canonical_title_id,
                source_key=source_key,
                external_title_id=str(shiki),
                mapping_method=MappingMethod.SHIKIMORI_ID,
                confidence=1.0,
                evidence="confirmed shikimori id in catalog external_ids",
                verified_at=utc_now_iso(),
                state=MappingState.VERIFIED,
            ),
            auto_publish=True,
            review_candidates=[],
        )

    # 2. Confirmed MAL ID crosswalk (Shikimori often shares id space; still labelled MAL_ID)
    mal = ext.get("myanimelist") or ext.get("mal") or ext.get("mal_id")
    if mal and source_key == "shikimori":
        return MappingDecision(
            mapping=TitleSourceMapping(
                canonical_title_id=title.canonical_title_id,
                source_key=source_key,
                external_title_id=str(mal),
                mapping_method=MappingMethod.MAL_ID_CROSSWALK,
                confidence=1.0,
                evidence="confirmed mal id crosswalk; score remains shikimori-labelled",
                verified_at=utc_now_iso(),
                state=MappingState.VERIFIED,
            ),
            auto_publish=True,
            review_candidates=[],
        )

    candidates = list(candidates or [])
    if not candidates:
        return MappingDecision(mapping=None, auto_publish=False, review_candidates=[])

    exact = []
    fuzzy = []
    for cand in candidates:
        reason = _exact_match_reason(title, cand)
        if reason == "exact":
            exact.append(cand)
        elif reason == "fuzzy":
            fuzzy.append(cand)
        elif reason.startswith("conflict:"):
            return MappingDecision(
                mapping=None,
                auto_publish=False,
                review_candidates=candidates,
                conflict_reason=reason,
            )

    if len(exact) == 1:
        cand = exact[0]
        return MappingDecision(
            mapping=TitleSourceMapping(
                canonical_title_id=title.canonical_title_id,
                source_key=source_key,
                external_title_id=str(cand["external_id"]),
                external_url=str(cand.get("url") or ""),
                mapping_method=MappingMethod.EXACT_TITLE_YEAR_KIND_SEASON,
                confidence=1.0,
                evidence="unique exact title+year+kind+season(+episodes) match",
                verified_at=utc_now_iso(),
                state=MappingState.VERIFIED,
            ),
            auto_publish=True,
            review_candidates=[],
        )

    if len(exact) > 1:
        return MappingDecision(
            mapping=None,
            auto_publish=False,
            review_candidates=exact,
            conflict_reason="multiple exact candidates",
        )

    # Fuzzy — review only
    if fuzzy:
        return MappingDecision(
            mapping=None,
            auto_publish=False,
            review_candidates=fuzzy,
            conflict_reason="fuzzy_candidates_for_review",
        )

    return MappingDecision(
        mapping=None,
        auto_publish=False,
        review_candidates=candidates,
        conflict_reason="no_exact_match",
    )


def _exact_match_reason(title: CatalogTitle, cand: dict[str, Any]) -> str:
    our_titles = {
        normalize_title(title.title),
        normalize_title(title.original_title),
        normalize_title(title.russian_title),
        *(normalize_title(a) for a in title.aliases),
    }
    our_titles.discard("")
    cand_titles = {
        normalize_title(str(cand.get("name") or "")),
        normalize_title(str(cand.get("russian") or "")),
        *(normalize_title(str(a)) for a in (cand.get("aliases") or [])),
    }
    cand_titles.discard("")
    if not our_titles or not cand_titles or our_titles.isdisjoint(cand_titles):
        # Fuzzy suggestion only if partial token overlap — never auto.
        if our_titles and cand_titles:
            tokens_a = set().union(*(t.split() for t in our_titles))
            tokens_b = set().union(*(t.split() for t in cand_titles))
            if tokens_a & tokens_b:
                return "fuzzy"
        return "no"

    # Year must match when both known
    cy = cand.get("year")
    if title.year is not None and cy is not None and int(title.year) != int(cy):
        return "conflict:year"

    ok = _norm_kind(title.kind)
    ck = _norm_kind(str(cand.get("kind") or cand.get("type") or ""))
    if ok and ck and (ok, ck) in _KIND_INCOMPATIBLE:
        return f"conflict:kind:{ok}/{ck}"

    # Season mismatch
    os_ = (title.season or "").strip().lower()
    cs = str(cand.get("season") or "").strip().lower()
    if os_ and cs and os_ != cs:
        return "conflict:season"

    # Episode count — allow ongoing without count
    oe, ce = title.episode_count, cand.get("episode_count")
    if (
        oe is not None
        and ce is not None
        and int(oe) != int(ce)
        and not (title.is_ongoing or cand.get("is_ongoing"))
    ):
        return "conflict:episode_count"

    # Remake / original flags if present
    if (
        bool(cand.get("is_remake"))
        and not bool(getattr(title, "is_remake", False))
        and title.year
        and cy
        and int(title.year) != int(cy)
    ):
        return "conflict:remake"

    return "exact"
