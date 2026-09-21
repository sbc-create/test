"""Сводный показатель для сортировки — отдельный, версионируемый, выключенный.

Это не «общий рейтинг тайтла» и не замена исходным оценкам. Это число,
по которому можно упорядочить список, и у него есть ровно одно назначение
— сортировка.

Почему он не показывается пользователю по умолчанию: у AniList, Кинопоиска
и наших зрителей разные аудитории и разные объёмы голосов, и любое их
усреднение зависит от того, какие источники ответили сегодня. Тайтл,
который «поднялся в рейтинге» из-за того, что добавился Kitsu, выглядит
как изменение мнения зрителей и им не является.

Формула ``weighted_bayes_v1``:

    score = (C * m + Σ(wᵢ · nᵢ · sᵢ)) / (m + Σ(wᵢ · nᵢ))

где sᵢ — нормализованная оценка источника, nᵢ — число голосов, wᵢ — вес
источника, C — общий приор, m — вес приора. Приор тянет тайтлы с малым
числом голосов к середине: без него один голос «10» ставит новинку выше
всего каталога.

Источники без числа голосов в формулу не входят: вес такого источника
пришлось бы придумать, а придуманный вес — это придуманный рейтинг.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from factory.unified_ratings.scale import ScoreState
from factory.unified_ratings.store import UnifiedStore

FORMULA_VERSION = "weighted_bayes_v1"

#: Общий приор — середина шкалы 1–10.
PRIOR_SCORE = Decimal("5.5")
#: Вес приора в «эквивалентных голосах».
PRIOR_WEIGHT = Decimal(50)

#: Минимум голосов на источник, ниже которого источник не участвует.
MIN_VOTES_PER_SOURCE = 20
#: Минимум участвующих источников.
MIN_SOURCES = 1
#: Минимум суммарных голосов, ниже которого показатель не вычисляется вовсе.
MIN_TOTAL_VOTES = 50

#: Веса источников. Собственные зрители весят больше внешних: это наша
#: аудитория, и её оценка относится именно к нашему каталогу.
SOURCE_WEIGHTS: dict[str, Decimal] = {
    "community": Decimal("1.0"),
    "anilist": Decimal("0.6"),
    "shikimori": Decimal("0.6"),
    "kitsu": Decimal("0.4"),
    "simkl": Decimal("0.4"),
    # Фидовые оценки приходят без числа голосов и поэтому не участвуют;
    # вес объявлен, чтобы его не пришлось придумывать при появлении голосов.
    "provider_feed_imdb": Decimal("0.5"),
    "provider_feed_kinopoisk": Decimal("0.5"),
}


@dataclass(frozen=True)
class CompositeResult:
    title_id: str
    formula_version: str
    value: str | None
    state: str
    sources_used: list[dict[str, Any]] = field(default_factory=list)
    sources_excluded: list[dict[str, Any]] = field(default_factory=list)
    total_votes: int = 0
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "title_id": self.title_id,
            "formula_version": self.formula_version,
            "value": self.value,
            "state": self.state,
            "sources_used": self.sources_used,
            "sources_excluded": self.sources_excluded,
            "total_votes": self.total_votes,
            "reason": self.reason,
            "purpose": "сортировка; исходные оценки не заменяет",
            "parameters": {
                "prior_score": str(PRIOR_SCORE),
                "prior_weight": str(PRIOR_WEIGHT),
                "min_votes_per_source": MIN_VOTES_PER_SOURCE,
                "min_total_votes": MIN_TOTAL_VOTES,
                "min_sources": MIN_SOURCES,
                "weights": {k: str(v) for k, v in SOURCE_WEIGHTS.items()},
            },
        }


def compute(
    store: UnifiedStore, *, title_id: str, tenant_id: str = ""
) -> CompositeResult:
    used: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    scope_kind = "tenant" if tenant_id else "network"
    agg = store.query_one(
        """SELECT vote_count, average_score FROM unified_user_aggregates
           WHERE scope_kind=? AND scope_id=? AND title_id=? AND dimension='overall'""",
        (scope_kind, tenant_id, title_id),
    )
    if agg is not None and int(agg["vote_count"]) > 0 and agg["average_score"]:
        _admit(
            used, excluded, "community", Decimal(str(agg["average_score"])), int(agg["vote_count"])
        )
    else:
        excluded.append({"source": "community", "reason": "нет пользовательских оценок"})

    for row in store.query(
        "SELECT source_key, normalized_score, vote_count, validation_state"
        " FROM unified_external_current WHERE title_id=? ORDER BY source_key",
        (title_id,),
    ):
        source_key = row["source_key"]
        if row["validation_state"] != ScoreState.OK.value:
            excluded.append(
                {"source": source_key, "reason": f"состояние оценки {row['validation_state']}"}
            )
            continue
        votes = row["vote_count"]
        if votes is None:
            excluded.append(
                {"source": source_key, "reason": "источник не отдаёт число голосов; вес неизвестен"}
            )
            continue
        _admit(used, excluded, source_key, Decimal(str(row["normalized_score"])), int(votes))

    total_votes = sum(int(s["vote_count"]) for s in used)
    if len(used) < MIN_SOURCES or total_votes < MIN_TOTAL_VOTES:
        return CompositeResult(
            title_id=title_id,
            formula_version=FORMULA_VERSION,
            value=None,
            state="INSUFFICIENT_DATA",
            sources_used=used,
            sources_excluded=excluded,
            total_votes=total_votes,
            reason=(
                f"нужно не менее {MIN_SOURCES} источника и {MIN_TOTAL_VOTES} голосов; "
                f"есть {len(used)} и {total_votes}"
            ),
        )

    numerator = PRIOR_SCORE * PRIOR_WEIGHT
    denominator = PRIOR_WEIGHT
    for entry in used:
        weight = SOURCE_WEIGHTS.get(entry["source"], Decimal("0.3"))
        effective = weight * Decimal(entry["vote_count"])
        numerator += effective * Decimal(entry["normalized"])
        denominator += effective
    value = (numerator / denominator).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)

    return CompositeResult(
        title_id=title_id,
        formula_version=FORMULA_VERSION,
        value=str(value),
        state="OK",
        sources_used=used,
        sources_excluded=excluded,
        total_votes=total_votes,
    )


def _admit(
    used: list[dict[str, Any]],
    excluded: list[dict[str, Any]],
    source: str,
    normalized: Decimal,
    votes: int,
) -> None:
    if votes < MIN_VOTES_PER_SOURCE:
        excluded.append(
            {
                "source": source,
                "reason": f"{votes} голосов меньше порога {MIN_VOTES_PER_SOURCE}",
                "vote_count": votes,
            }
        )
        return
    used.append({"source": source, "normalized": str(normalized), "vote_count": votes})


def explain(result: CompositeResult) -> str:
    """Читаемое объяснение — что вошло, что нет и почему."""
    return json.dumps(result.as_dict(), ensure_ascii=False, indent=2)
