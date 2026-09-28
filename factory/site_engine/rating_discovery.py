"""Что известно о доступности рейтинга. Не сам рейтинг.

Разделение намеренное. Задача рейтингов — следующая; здесь выясняется только,
есть ли вообще разрешённый источник, вышло ли произведение и почему числа нет.
Смешивать эти вопросы дорого: «рейтинга нет» и «источник не подключён» ведут
к разным действиям, а сведённые в одно поле выглядят одинаково.

Главное правило: **отсутствие числа никогда не превращается в ноль.** Ноль —
это утверждение «оценили и поставили ноль», и в разметке он выглядит именно
так. Отсутствие обязано остаться отсутствием на всём пути до выдачи.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import enum
from typing import Any

from factory.site_engine.content_identity import ContentIdentity

VERSION = "rating-discovery/1.0.0"


class RatingState(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    PRE_RELEASE = "PRE_RELEASE"
    NO_VOTES_YET = "NO_VOTES_YET"
    INSUFFICIENT_VOTES = "INSUFFICIENT_VOTES"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    ENTITY_NOT_MATCHED = "ENTITY_NOT_MATCHED"
    UNSUPPORTED = "UNSUPPORTED"
    NOT_CHECKED_LICENSE_BLOCKED = "NOT_CHECKED_LICENSE_BLOCKED"


class RatingEligibility(str, enum.Enum):
    """Может ли у произведения в принципе быть зрительская оценка."""

    ELIGIBLE = "ELIGIBLE"
    #: Ещё не вышло: оценивать нечего, и это не пробел в данных.
    NOT_RELEASED = "NOT_RELEASED"
    #: Вид произведения, для которого зрительские оценки не собираются.
    NOT_APPLICABLE = "NOT_APPLICABLE"
    #: Год неизвестен — выпущенность недоказуема.
    UNDETERMINED = "UNDETERMINED"


#: Виды, для которых зрительские оценки источниками не ведутся.
NOT_RATED_KINDS = frozenset({"EPISODE", "SEASON", "MUSIC"})


@dataclasses.dataclass
class RatingDiscoveryResult:
    internal_entity_id: str
    external_source: str = ""
    external_entity_id: str = ""
    rating_eligibility: RatingEligibility = RatingEligibility.UNDETERMINED
    rating_state: RatingState = RatingState.SOURCE_UNAVAILABLE
    numeric_rating_present: bool = False
    vote_count_present: bool = False
    captured_at: str = ""
    blocker: str = ""
    recommended_next_source: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "internalEntityId": self.internal_entity_id,
            "externalSource": self.external_source,
            "externalEntityId": self.external_entity_id,
            "ratingEligibility": self.rating_eligibility.value,
            "ratingState": self.rating_state.value,
            "numericRatingPresent": self.numeric_rating_present,
            "voteCountPresent": self.vote_count_present,
            "capturedAt": self.captured_at,
            "blocker": self.blocker,
            "recommendedNextSource": self.recommended_next_source,
            "discoveryVersion": VERSION,
        }


@dataclasses.dataclass(frozen=True)
class SourcePolicy:
    """Что нам разрешено спрашивать. Пустой перечень — это тоже ответ."""

    #: Источники, которые уже настроены и разрешены.
    configured: tuple[str, ...] = ()
    #: Источники, технически подходящие, но без лицензии или настройки.
    known_unlicensed: tuple[str, ...] = ()
    license_policy_version: str = ""

    def first_configured(self, external_ids: dict) -> tuple[str, str]:
        for источник in self.configured:
            значение = (external_ids or {}).get(источник)
            if значение:
                return источник, str(значение)
        return "", ""


def eligibility(identity: ContentIdentity, *, today: dt.date | None = None) -> RatingEligibility:
    """Может ли у записи быть оценка. Год в будущем — не пробел, а факт."""
    if identity.content_kind.value in NOT_RATED_KINDS:
        return RatingEligibility.NOT_APPLICABLE
    if not identity.release_year:
        return RatingEligibility.UNDETERMINED
    сегодня = today or dt.date.today()
    if identity.release_year > сегодня.year:
        return RatingEligibility.NOT_RELEASED
    return RatingEligibility.ELIGIBLE


def discover(
    identity: ContentIdentity,
    *,
    policy: SourcePolicy,
    feed_ratings: dict | None = None,
    today: dt.date | None = None,
    now: dt.datetime | None = None,
) -> RatingDiscoveryResult:
    """Состояние рейтинга по одной записи.

    `feed_ratings` — числа, уже присутствующие в фиде поставщика. Отдельного
    обращения к внешнему источнику здесь не делается: сначала используется то,
    что и так получено, и только затем ставится вопрос о новом источнике.
    """
    когда = (now or dt.datetime.now(dt.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    итог = RatingDiscoveryResult(internal_entity_id=identity.internal_entity_id, captured_at=когда)
    итог.rating_eligibility = eligibility(identity, today=today)

    if not identity.resolved:
        итог.rating_state = RatingState.ENTITY_NOT_MATCHED
        итог.blocker = f"идентичность не разрешена: {identity.identity_status.value}"
        итог.recommended_next_source = "identity-resolution"
        return итог

    if итог.rating_eligibility is RatingEligibility.NOT_APPLICABLE:
        итог.rating_state = RatingState.UNSUPPORTED
        итог.blocker = f"вид {identity.content_kind.value}: оценки не ведутся"
        return итог

    источник, внешний = policy.first_configured(identity.external_ids)
    итог.external_source, итог.external_entity_id = источник, внешний

    числа = {k: v for k, v in (feed_ratings or {}).items() if v is not None}
    if числа:
        итог.numeric_rating_present = True
        # Число голосов фид не отдаёт. Отсутствие фиксируется, а не додумывается.
        итог.vote_count_present = False
        итог.rating_state = RatingState.AVAILABLE
        итог.external_source = итог.external_source or "cdnvideohub-feed"
        return итог

    if итог.rating_eligibility is RatingEligibility.NOT_RELEASED:
        итог.rating_state = RatingState.PRE_RELEASE
        итог.blocker = "произведение ещё не вышло"
        return итог

    if not источник:
        # Разрешённого источника нет вовсе — это не «оценок нет».
        итог.rating_state = (
            RatingState.NOT_CHECKED_LICENSE_BLOCKED
            if policy.known_unlicensed
            else RatingState.SOURCE_UNAVAILABLE
        )
        if policy.known_unlicensed:
            итог.blocker = (
                "разрешённый источник рейтинга не настроен; "
                "технически подходят " + ", ".join(policy.known_unlicensed)
            )
        else:
            итог.blocker = "разрешённый источник рейтинга не настроен"
        итог.recommended_next_source = policy.known_unlicensed[0] if policy.known_unlicensed else ""
        return итог

    if итог.rating_eligibility is RatingEligibility.UNDETERMINED:
        итог.rating_state = RatingState.NO_VOTES_YET
        итог.blocker = "год выпуска неизвестен: выпущенность не доказана"
        return итог

    итог.rating_state = RatingState.NO_VOTES_YET
    итог.blocker = "источник подключён, числа по записи нет"
    return итог


def coverage(results) -> dict[str, Any]:
    """Сводка. Проценты считаются от знаменателя, который назван явно."""
    результаты = list(results or ())
    всего = len(результаты)
    состояния: dict[str, int] = {}
    for r in результаты:
        состояния[r.rating_state.value] = состояния.get(r.rating_state.value, 0) + 1
    подходящие = [r for r in результаты if r.rating_eligibility is RatingEligibility.ELIGIBLE]
    с_числом = [r for r in подходящие if r.numeric_rating_present]
    return {
        "total": всего,
        "withRatingState": всего,
        "ratingStateCoverage": 1.0 if всего else 0.0,
        "byState": состояния,
        "eligibleReleased": len(подходящие),
        "eligibleReleasedWithSource": len(с_числом),
        "numericSourceCoverageEligibleReleased": (
            len(с_числом) / len(подходящие) if подходящие else 0.0
        ),
        "discoveryVersion": VERSION,
    }
