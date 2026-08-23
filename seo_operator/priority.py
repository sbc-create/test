"""New-release priority model and query taxonomy.

Both are deliberately transparent scoring functions rather than opaque weights:
the daily report has to be able to explain *why* an item was prioritised, and a
number nobody can derive is not an explanation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum


class QueryClass(str, Enum):
    TITLE_EXACT = "title_exact"  # точное название произведения
    TITLE_SEASON = "title_season"  # название + сезон/серия
    WATCH_INTENT = "watch_intent"  # смотреть / онлайн
    DISCOVERY = "discovery"  # подборки, "что посмотреть"
    INFORMATIONAL = "informational"  # сюжет, актёры, дата выхода
    NAVIGATIONAL = "navigational"  # бренд сайта
    UNCLASSIFIED = "unclassified"


TAXONOMY_RULES: list[tuple[QueryClass, tuple[str, ...]]] = [
    (QueryClass.TITLE_SEASON, ("сезон", "серия", "серии", "эпизод", "season")),
    (QueryClass.WATCH_INTENT, ("смотреть", "онлайн", "бесплатно", "watch")),
    (QueryClass.DISCOVERY, ("похожие", "подборка", "топ", "что посмотреть", "лучшие", "список")),
    (
        QueryClass.INFORMATIONAL,
        (
            "сюжет",
            "актёры",
            "актеры",
            "дата выхода",
            "когда выйдет",
            "описание",
            "рецензия",
            "отзывы",
        ),
    ),
]


def classify_query(query: str, brand_terms: frozenset[str] = frozenset()) -> QueryClass:
    q = query.strip().lower()
    if not q:
        return QueryClass.UNCLASSIFIED
    for term in brand_terms:
        if term.lower() in q:
            return QueryClass.NAVIGATIONAL
    for cls, markers in TAXONOMY_RULES:
        if any(m in q for m in markers):
            return cls
    return QueryClass.TITLE_EXACT


@dataclass
class ReleaseCandidate:
    """An item competing for editorial attention."""

    entity_id: str
    title: str
    release_date: date | None
    is_new_season: bool = False
    is_ongoing: bool = False
    confirmed_source: bool = False
    current_impressions: int | None = None
    has_landing_page: bool = True
    rights_confirmed: bool = False


@dataclass
class PriorityScore:
    entity_id: str
    score: float
    factors: dict[str, float]
    explanation: str
    eligible: bool


def score_release(candidate: ReleaseCandidate, today: date) -> PriorityScore:
    """Score a release candidate. Ineligible items score 0 and say why.

    Eligibility is a hard gate, not a weight: an unconfirmed or unlicensed item
    never competes for a slot, regardless of how much traffic it might attract.
    """
    factors: dict[str, float] = {}

    if not candidate.confirmed_source:
        return PriorityScore(
            candidate.entity_id,
            0.0,
            {},
            "нет подтверждённого источника — материал не планируется",
            False,
        )
    if not candidate.rights_confirmed:
        return PriorityScore(
            candidate.entity_id, 0.0, {}, "не подтверждены права — материал не планируется", False
        )

    # Proximity to the release date: the window around a release is when demand
    # concentrates, so both sides of it score, with the run-up scoring highest.
    if candidate.release_date:
        days = (candidate.release_date - today).days
        if 0 <= days <= 14:
            factors["окно релиза"] = 3.0
        elif -7 <= days < 0:
            factors["только что вышло"] = 2.5
        elif 15 <= days <= 60:
            factors["анонс заранее"] = 1.5
        elif days > 60:
            factors["далёкий анонс"] = 0.5
        else:
            factors["архив"] = 0.2
    else:
        factors["дата неизвестна"] = 0.3

    if candidate.is_new_season:
        factors["новый сезон"] = 2.0
    if candidate.is_ongoing:
        factors["онгоинг"] = 1.5
    if not candidate.has_landing_page:
        factors["нет посадочной страницы"] = 2.0

    if candidate.current_impressions is not None:
        if candidate.current_impressions > 5000:
            factors["высокий спрос"] = 2.0
        elif candidate.current_impressions > 500:
            factors["средний спрос"] = 1.0
    # No impressions data is not a zero: it simply contributes no factor.

    score = round(sum(factors.values()), 2)
    explanation = ", ".join(
        f"{k} (+{v})" for k, v in sorted(factors.items(), key=lambda kv: -kv[1])
    )
    return PriorityScore(candidate.entity_id, score, factors, explanation, True)


def rank(candidates, today: date) -> list[PriorityScore]:
    scored = [score_release(c, today) for c in candidates]
    return sorted([s for s in scored if s.eligible], key=lambda s: -s.score)
