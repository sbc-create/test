"""Сводная оценка — `composite_external_rating`, в интерфейсе «Сводная оценка».

Это четвёртая величина рядом с тремя уже существующими, а не замена им:

* ``community_rating`` — оценки зрителей нашего сайта;
* ``editorial_rating`` — наша редакционная оценка;
* ``composite_external_rating`` — среднее по внешним источникам;
* сами внешние оценки, каждая отдельной строкой.

Формула первой версии намеренно простая и проверяемая: среднее
нормализованных оценок с равными весами.

    composite = Σ(normalized_i × weight_i) / Σ(weight_i),  weight_i = 1.0

Число голосов **не** является весом. У AniList под сто тысяч оценивших, у
Kitsu — десятки тысяч; взвешивание по голосам означало бы, что сводная
оценка почти равна AniList, а остальные источники присутствуют в ней
номинально. Количество голосов показывается пользователю отдельно и
используется как признак уверенности.

Сводная оценка появляется только при двух и более независимых
источниках. С одним источником это не «сводная оценка», а оценка этого
источника, и называть её иначе — вводить читателя в заблуждение; такой
случай возвращается отдельным состоянием ``SINGLE_SOURCE_ONLY``.

Веса и минимальное число источников живут в конфигурации версии формулы,
а не в коде вызывающего: смена весов — это новая версия формулы с
записью в аудит, а не правка константы.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from factory.unified_ratings.coverage import SLA_HOURS
from factory.unified_ratings.scale import ScoreState
from factory.unified_ratings.sources import EXTERNAL_DISPLAY_ORDER
from factory.unified_ratings.store import UnifiedStore

DISPLAY_NAME = "Сводная оценка"
INTERNAL_NAME = "composite_external_rating"

FORMULA_VERSION = "equal_weight_mean_v1"

#: Минимум независимых источников. Ниже — не сводная оценка.
MIN_SOURCES = 2

#: Веса источников этой версии формулы. Все равны: ни один источник не
#: объявлен более правильным, пока владелец такого решения не принял.
SOURCE_WEIGHTS: dict[str, Decimal] = {
    "anilist": Decimal("1.0"),
    "simkl": Decimal("1.0"),
    "shikimori": Decimal("1.0"),
    "kitsu": Decimal("1.0"),
    "provider_feed_imdb": Decimal("1.0"),
    "provider_feed_kinopoisk": Decimal("1.0"),
    "amd_online": Decimal("1.0"),
}


class FreshnessStatus(str):
    FRESH = "FRESH"
    STALE = "STALE"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class SourceContribution:
    source_key: str
    normalized: str
    raw_value: str | None
    source_scale: str | None
    vote_count: int | None
    fetched_at: str
    weight: str
    stale: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source_key,
            "normalized": self.normalized,
            "raw_value": self.raw_value,
            "source_scale": self.source_scale,
            "vote_count": self.vote_count,
            "fetched_at": self.fetched_at,
            "weight": self.weight,
            "stale": self.stale,
        }


@dataclass(frozen=True)
class CompositeRating:
    title_id: str
    state: str
    value: str | None
    formula_version: str
    calculated_at: str
    sources_used: list[SourceContribution] = field(default_factory=list)
    sources_excluded: list[dict[str, Any]] = field(default_factory=list)
    confidence: str = "UNKNOWN"
    freshness_status: str = FreshnessStatus.UNKNOWN
    reason: str = ""

    @property
    def source_count(self) -> int:
        return len(self.sources_used)

    @property
    def total_votes(self) -> int | None:
        counts = [c.vote_count for c in self.sources_used if c.vote_count is not None]
        return sum(counts) if counts else None

    def as_dict(self) -> dict[str, Any]:
        return {
            "internal_name": INTERNAL_NAME,
            "display_name": DISPLAY_NAME,
            "title_id": self.title_id,
            "state": self.state,
            "value": self.value,
            "display_value": self.value,
            "formula_version": self.formula_version,
            "calculated_at": self.calculated_at,
            "source_count": self.source_count,
            "sources_used": [c.as_dict() for c in self.sources_used],
            "sources_excluded": self.sources_excluded,
            "confidence": self.confidence,
            "total_votes_across_sources": self.total_votes,
            "freshness_status": self.freshness_status,
            "reason": self.reason,
            "min_sources": MIN_SOURCES,
            "note": (
                "среднее по внешним источникам; это не оценка зрителей нашего "
                "сайта и не редакционная оценка"
            ),
        }


def _parse(stamp: str) -> datetime | None:
    if not stamp:
        return None
    try:
        return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _confidence(contributions: list[SourceContribution]) -> str:
    """Уверенность по числу источников и объёму голосов — отдельно от значения.

    Число голосов не влияет на саму оценку; оно отвечает на другой вопрос —
    насколько устойчиво то, что мы показали.
    """
    if len(contributions) < MIN_SOURCES:
        return "UNKNOWN"
    votes = [c.vote_count for c in contributions if c.vote_count is not None]
    total = sum(votes) if votes else 0
    if len(contributions) >= 4 and total >= 10_000:
        return "HIGH"
    if len(contributions) >= 3 or total >= 1_000:
        return "MEDIUM"
    return "LOW"


def compute(
    store: UnifiedStore,
    *,
    title_id: str,
    now: datetime | None = None,
    weights: dict[str, Decimal] | None = None,
) -> CompositeRating:
    now = now or datetime.now(timezone.utc)
    weights = weights or SOURCE_WEIGHTS
    calculated_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    tiers = {
        r["source_key"]: r["tier"]
        for r in store.query(
            "SELECT source_key, tier FROM unified_schedule_state WHERE title_id=?", (title_id,)
        )
    }
    ambiguous = {
        r["source_key"]
        for r in store.query(
            "SELECT source_key FROM unified_source_links WHERE title_id=?"
            " AND status IN ('pending','conflict','rejected')",
            (title_id,),
        )
    }

    used: list[SourceContribution] = []
    excluded: list[dict[str, Any]] = []

    for row in store.query(
        "SELECT * FROM unified_external_current WHERE title_id=? ORDER BY source_key",
        (title_id,),
    ):
        source_key = row["source_key"]
        if row["validation_state"] != ScoreState.OK.value:
            # Отсутствующее значение не становится нулём и не участвует.
            excluded.append({"source": source_key, "reason": f"состояние {row['validation_state']}"})
            continue
        if source_key in ambiguous:
            excluded.append({"source": source_key, "reason": "сопоставление не подтверждено"})
            continue
        weight = weights.get(source_key)
        if weight is None:
            excluded.append({"source": source_key, "reason": "источник не разрешён в этой версии формулы"})
            continue
        checked = _parse(row["last_checked_at"]) or _parse(row["fetched_at"])
        tier = tiers.get(source_key, "UNSCHEDULED")
        stale = bool(
            checked is None
            or now - checked > timedelta(hours=SLA_HOURS.get(tier, SLA_HOURS["UNSCHEDULED"]))
        )
        if stale:
            excluded.append({"source": source_key, "reason": "значение устарело по SLA"})
            continue
        used.append(
            SourceContribution(
                source_key=source_key,
                normalized=str(row["normalized_score"]),
                raw_value=row["raw_score"],
                source_scale=f"0–{row['source_scale_max']}",
                vote_count=row["vote_count"],
                fetched_at=row["fetched_at"],
                weight=str(weight),
                stale=False,
            )
        )

    if not used:
        return CompositeRating(
            title_id=title_id, state="NO_SOURCES", value=None,
            formula_version=FORMULA_VERSION, calculated_at=calculated_at,
            sources_excluded=excluded, freshness_status=FreshnessStatus.UNKNOWN,
            reason="ни один внешний источник не даёт подтверждённой свежей оценки",
        )

    if len(used) < MIN_SOURCES:
        return CompositeRating(
            title_id=title_id, state="SINGLE_SOURCE_ONLY", value=None,
            formula_version=FORMULA_VERSION, calculated_at=calculated_at,
            sources_used=used, sources_excluded=excluded,
            confidence="UNKNOWN", freshness_status=FreshnessStatus.FRESH,
            reason=(
                f"доступен один источник ({used[0].source_key}); его оценка показывается "
                "отдельно и сводной не называется"
            ),
        )

    numerator = sum(Decimal(c.normalized) * Decimal(c.weight) for c in used)
    denominator = sum(Decimal(c.weight) for c in used)
    value = (numerator / denominator).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)

    return CompositeRating(
        title_id=title_id,
        state="OK",
        value=f"{value:.1f}",
        formula_version=FORMULA_VERSION,
        calculated_at=calculated_at,
        sources_used=used,
        sources_excluded=excluded,
        confidence=_confidence(used),
        freshness_status=FreshnessStatus.FRESH,
    )


def store_composite(store: UnifiedStore, rating: CompositeRating) -> None:
    """Сохранить пересчитанное значение. Пересчёт всегда возможен заново."""
    with store.write_tx() as conn:
        conn.execute(
            """INSERT INTO unified_composite_ratings(
                   title_id, formula_version, state, value, source_count, sources_json,
                   confidence, freshness_status, calculated_at)
               VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT(title_id, formula_version) DO UPDATE SET
                   state=excluded.state, value=excluded.value,
                   source_count=excluded.source_count, sources_json=excluded.sources_json,
                   confidence=excluded.confidence, freshness_status=excluded.freshness_status,
                   calculated_at=excluded.calculated_at""",
            (
                rating.title_id,
                rating.formula_version,
                rating.state,
                rating.value,
                rating.source_count,
                json.dumps([c.as_dict() for c in rating.sources_used], ensure_ascii=False),
                rating.confidence,
                rating.freshness_status,
                rating.calculated_at,
            ),
        )


def record_formula_change(
    store: UnifiedStore, *, version: str, weights: dict[str, Decimal], actor: str, rationale: str
) -> None:
    """Аудит изменения формулы. Веса — конфигурация, а не константа в коде."""
    with store.write_tx() as conn:
        conn.execute(
            """INSERT INTO unified_composite_formula_audit(
                   formula_version, weights_json, min_sources, actor, rationale, created_at)
               VALUES (?,?,?,?,?,?)""",
            (
                version,
                json.dumps({k: str(v) for k, v in weights.items()}, ensure_ascii=False, sort_keys=True),
                MIN_SOURCES,
                actor,
                rationale,
                datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            ),
        )


def recompute_many(
    store: UnifiedStore, title_ids: list[str], *, now: datetime | None = None
) -> dict[str, int]:
    counts = {"OK": 0, "SINGLE_SOURCE_ONLY": 0, "NO_SOURCES": 0}
    for title_id in title_ids:
        rating = compute(store, title_id=title_id, now=now)
        store_composite(store, rating)
        counts[rating.state] = counts.get(rating.state, 0) + 1
    return counts


def display_order() -> tuple[str, ...]:
    """Порядок внешних источников в детализации сводной оценки."""
    return EXTERNAL_DISPLAY_ORDER
