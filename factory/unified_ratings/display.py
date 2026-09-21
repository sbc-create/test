"""Модель отображения: каждая оценка отдельной строкой со своим источником.

Отсутствующая оценка не становится нулём и не исчезает молча. У каждой
строки есть состояние и причина, потому что «источник не знает этот
тайтл», «источник ещё никем не оценён» и «источник заблокирован» — это
три разных сообщения пользователю, а ноль вместо любого из них — четвёртое
и неверное.

Сводного «общего рейтинга» здесь нет. У AniList, Кинопоиска и наших
зрителей разные аудитории, шкалы и объёмы голосов, и среднее по ним не
измеряет ничего: оно меняется от того, какой источник ответил сегодня.
Сортировочный показатель живёт отдельно, в ``composite.py``, включается
явно и исходные значения не подменяет.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import Any

from factory.unified_ratings.community import CommunityRatings
from factory.unified_ratings.editorial import EditorialRatings
from factory.unified_ratings.scale import ScoreState
from factory.unified_ratings.sources import EXTERNAL_DISPLAY_ORDER, REGISTRY, SourceStatus
from factory.unified_ratings.store import UnifiedStore

LABEL_EDITORIAL = "Наша оценка"
LABEL_COMMUNITY = "Оценка зрителей"


class RowKind(str, Enum):
    EDITORIAL = "editorial"
    COMMUNITY = "community"
    EXTERNAL = "external"


class Availability(str, Enum):
    PRESENT = "PRESENT"
    #: источник опрошен, оценки у него нет
    NO_RATING_AT_SOURCE = "NO_RATING_AT_SOURCE"
    #: тайтл с источником не связан
    NOT_LINKED = "NOT_LINKED"
    #: связь есть, но отправлена на проверку
    PENDING_REVIEW = "PENDING_REVIEW"
    #: источник заблокирован (нет ключа, нет разрешения)
    SOURCE_BLOCKED = "SOURCE_BLOCKED"
    #: измерение не выполнялось
    UNMEASURED = "UNMEASURED"


@dataclass(frozen=True)
class RatingRow:
    kind: RowKind
    key: str
    label: str
    availability: Availability
    #: строка с одним знаком после запятой для внешних, целое для наших
    display_value: str | None = None
    numeric: str | None = None
    vote_count: int | None = None
    user_count: int | None = None
    raw_value: str | None = None
    source_scale: str | None = None
    formula: str | None = None
    provenance_url: str = ""
    fetched_at: str = ""
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "key": self.key,
            "label": self.label,
            "availability": self.availability.value,
            "display_value": self.display_value,
            "numeric": self.numeric,
            "vote_count": self.vote_count,
            "user_count": self.user_count,
            "raw_value": self.raw_value,
            "source_scale": self.source_scale,
            "formula": self.formula,
            "provenance_url": self.provenance_url,
            "fetched_at": self.fetched_at,
            "reason": self.reason,
        }


class DisplayModel:
    def __init__(
        self,
        store: UnifiedStore,
        *,
        editorial: EditorialRatings | None = None,
        community: CommunityRatings | None = None,
    ) -> None:
        self.store = store
        self.editorial = editorial or EditorialRatings(store)
        self.community = community

    # ------------------------------------------------------------------

    def rows_for(self, *, title_id: str, tenant_id: str = "") -> list[RatingRow]:
        rows = [self._editorial_row(title_id, tenant_id), self._community_row(title_id, tenant_id)]
        for source_key in EXTERNAL_DISPLAY_ORDER:
            rows.append(self._external_row(title_id, source_key))
        return rows

    def view(self, *, title_id: str, tenant_id: str = "") -> dict[str, Any]:
        rows = self.rows_for(title_id=title_id, tenant_id=tenant_id)
        return {
            "title_id": title_id,
            "tenant_id": tenant_id,
            "scale": "1-10",
            "combined_rating": None,
            "combined_rating_note": (
                "единый рейтинг по умолчанию не вычисляется: источники "
                "измеряют разные аудитории по разным шкалам"
            ),
            "rows": [r.as_dict() for r in rows],
        }

    # ------------------------------------------------------------------

    def _editorial_row(self, title_id: str, tenant_id: str) -> RatingRow:
        rating = self.editorial.effective(title_id=title_id, tenant_id=tenant_id)
        if rating is None:
            return RatingRow(
                kind=RowKind.EDITORIAL,
                key="editorial",
                label=LABEL_EDITORIAL,
                availability=Availability.NO_RATING_AT_SOURCE,
                reason="редакция ещё не поставила оценку",
            )
        return RatingRow(
            kind=RowKind.EDITORIAL,
            key="editorial",
            label=LABEL_EDITORIAL,
            availability=Availability.PRESENT,
            display_value=f"{rating.score}/10",
            numeric=str(rating.score),
            fetched_at=rating.updated_at,
        )

    def _community_row(self, title_id: str, tenant_id: str) -> RatingRow:
        scope_kind = "tenant" if tenant_id else "network"
        row = self.store.query_one(
            """SELECT * FROM unified_user_aggregates
               WHERE scope_kind=? AND scope_id=? AND title_id=? AND dimension='overall'""",
            (scope_kind, tenant_id, title_id),
        )
        if row is None:
            return RatingRow(
                kind=RowKind.COMMUNITY,
                key="community",
                label=LABEL_COMMUNITY,
                availability=Availability.UNMEASURED,
                reason="агрегат не рассчитывался для этой площадки",
            )
        count = int(row["vote_count"])
        if count == 0:
            return RatingRow(
                kind=RowKind.COMMUNITY,
                key="community",
                label=LABEL_COMMUNITY,
                availability=Availability.NO_RATING_AT_SOURCE,
                vote_count=0,
                reason="пока нет оценок",
            )
        average = row["average_score"]
        return RatingRow(
            kind=RowKind.COMMUNITY,
            key="community",
            label=LABEL_COMMUNITY,
            availability=Availability.PRESENT,
            display_value=_one_decimal(average),
            numeric=str(average),
            vote_count=count,
            fetched_at=row["recomputed_at"],
        )

    def _external_row(self, title_id: str, source_key: str) -> RatingRow:
        source = REGISTRY[source_key]
        link = self.store.query_one(
            "SELECT status FROM unified_source_links WHERE title_id=? AND source_key=?",
            (title_id, source_key),
        )
        current = self.store.query_one(
            "SELECT * FROM unified_external_current WHERE title_id=? AND source_key=?",
            (title_id, source_key),
        )

        if source.status in (SourceStatus.BLOCKED_SECRET, SourceStatus.BLOCKED_PAID,
                             SourceStatus.BLOCKED_AUTHORIZATION, SourceStatus.BLOCKED_ACCESS):
            return RatingRow(
                kind=RowKind.EXTERNAL,
                key=source_key,
                label=source.ui_label,
                availability=Availability.SOURCE_BLOCKED,
                reason=source.blocker or f"источник в состоянии {source.status.value}",
            )

        if current is None:
            if link is not None and link["status"] in ("pending", "conflict"):
                return RatingRow(
                    kind=RowKind.EXTERNAL,
                    key=source_key,
                    label=source.ui_label,
                    availability=Availability.PENDING_REVIEW,
                    reason="сопоставление отправлено на проверку и не публикуется",
                )
            return RatingRow(
                kind=RowKind.EXTERNAL,
                key=source_key,
                label=source.ui_label,
                availability=Availability.NOT_LINKED,
                reason="тайтл не связан с этим источником",
            )

        state = current["validation_state"]
        if state != ScoreState.OK.value:
            return RatingRow(
                kind=RowKind.EXTERNAL,
                key=source_key,
                label=source.ui_label,
                availability=(
                    Availability.NO_RATING_AT_SOURCE
                    if state in (ScoreState.ABSENT.value, ScoreState.ZERO_NOT_A_RATING.value)
                    else Availability.UNMEASURED
                ),
                vote_count=current["vote_count"],
                user_count=current["user_count"],
                fetched_at=current["fetched_at"],
                reason=_state_reason(state),
            )

        normalized = current["normalized_score"]
        return RatingRow(
            kind=RowKind.EXTERNAL,
            key=source_key,
            label=source.ui_label,
            availability=Availability.PRESENT,
            display_value=_one_decimal(normalized),
            numeric=str(normalized),
            vote_count=current["vote_count"],
            user_count=current["user_count"],
            raw_value=current["raw_score"],
            source_scale=source.scale.scale_label,
            formula=source.scale.formula_expression,
            provenance_url=current["provenance_url"],
            fetched_at=current["fetched_at"],
        )


def _one_decimal(value: Any) -> str | None:
    if value in (None, ""):
        return None
    quantized = Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return f"{quantized:.1f}"


def _state_reason(state: str) -> str:
    return {
        ScoreState.ABSENT.value: "источник не вернул оценку для этого тайтла",
        ScoreState.ZERO_NOT_A_RATING.value: "источник вернул ноль — «ещё не оценили»",
        ScoreState.OUT_OF_RANGE_LOW.value: "нормализованное значение ниже шкалы 1–10; не публикуется",
        ScoreState.OUT_OF_RANGE_HIGH.value: "нормализованное значение выше шкалы 1–10; не публикуется",
        ScoreState.INVALID_TYPE.value: "источник вернул не число",
        ScoreState.CONTRACT_UNVERIFIED.value: "контракт шкалы источника не подтверждён",
        ScoreState.UNMEASURED.value: "измерение не выполнялось",
    }.get(state, f"состояние {state}")
