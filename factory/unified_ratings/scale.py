"""Нормализация внешних оценок к внутренней шкале 1.0–10.0.

Формула не выбирается по внешнему виду числа. Она объявлена в контракте
конкретного источника и применяется только к источнику, для которого
проверена: 86 у AniList и 8.6 у Shikimori — одно и то же качество, но
универсальное правило «поделить на 10, если больше десяти» превратило бы
оценку 9.5 по пятибалльной шкале в 0.95 молча и правдоподобно.

Отсутствие значения, ноль как «ещё не оценили», значение вне шкалы и
неизмеренное значение — четыре разных состояния. Ни одно из них не
становится нулём и ни одно не становится другим.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from enum import Enum
from typing import Any

from factory.unified_ratings import SCALE_MAX, SCALE_MIN


class ScoreState(str, Enum):
    """Исход нормализации. Различает отсутствие, ноль и невалидность."""

    OK = "OK"
    #: источник не имеет оценки для этого тайтла (null / пусто)
    ABSENT = "ABSENT"
    #: источник вернул 0 — у всех наших источников это «ещё не оценили»
    ZERO_NOT_A_RATING = "ZERO_NOT_A_RATING"
    #: значение реально, но после нормализации ниже нашей шкалы
    OUT_OF_RANGE_LOW = "OUT_OF_RANGE_LOW"
    #: значение выше исходной шкалы источника — нарушение контракта
    OUT_OF_RANGE_HIGH = "OUT_OF_RANGE_HIGH"
    #: строка, NaN, bool, inf — не число
    INVALID_TYPE = "INVALID_TYPE"
    #: формула для источника не проверена; нормализовать нельзя
    CONTRACT_UNVERIFIED = "CONTRACT_UNVERIFIED"
    #: измерение не выполнялось (источник недоступен, ключа нет)
    UNMEASURED = "UNMEASURED"


class FormulaId(str, Enum):
    """Идентификатор формулы. Записывается в снимок вместе с результатом."""

    IDENTITY_0_10 = "identity_0_10"
    DIVIDE_10_FROM_0_100 = "divide_10_from_0_100"
    MULTIPLY_2_FROM_0_5 = "multiply_2_from_0_5"


#: Человекочитаемая запись формулы — попадает в отчёт и в API.
FORMULA_EXPRESSION: dict[FormulaId, str] = {
    FormulaId.IDENTITY_0_10: "normalized = raw",
    FormulaId.DIVIDE_10_FROM_0_100: "normalized = raw / 10",
    FormulaId.MULTIPLY_2_FROM_0_5: "normalized = raw * 2",
}

_FORMULA_SCALE_MAX: dict[FormulaId, Decimal] = {
    FormulaId.IDENTITY_0_10: Decimal(10),
    FormulaId.DIVIDE_10_FROM_0_100: Decimal(100),
    FormulaId.MULTIPLY_2_FROM_0_5: Decimal(5),
}


def _apply(formula: FormulaId, raw: Decimal) -> Decimal:
    if formula is FormulaId.IDENTITY_0_10:
        return raw
    if formula is FormulaId.DIVIDE_10_FROM_0_100:
        return raw / Decimal(10)
    if formula is FormulaId.MULTIPLY_2_FROM_0_5:
        return raw * Decimal(2)
    raise ValueError(f"неизвестная формула: {formula}")


@dataclass(frozen=True)
class SourceScaleContract:
    """Проверенный контракт шкалы одного источника.

    ``verified`` — не украшение. Пока контракт не подтверждён живым
    ответом источника, нормализация возвращает CONTRACT_UNVERIFIED вместо
    числа: адаптер, который угадал шкалу, выдаёт правдоподобные оценки,
    и ошибка обнаруживается только жалобой пользователя.
    """

    source_key: str
    source_scale_min: Decimal
    source_scale_max: Decimal
    formula: FormulaId
    #: что именно измеряет поле — защита от нормализации ранга или процента
    measures: str
    #: поле исходного ответа, из которого взято значение
    raw_field: str
    verified: bool = False
    verified_evidence: str = ""
    #: поле с числом голосов; пусто — источник его не отдаёт
    vote_count_field: str = ""
    #: поле с числом пользователей, если источник отличает его от голосов
    user_count_field: str = ""
    notes: str = ""

    @property
    def scale_label(self) -> str:
        return f"{_plain(self.source_scale_min)}–{_plain(self.source_scale_max)}"

    @property
    def formula_expression(self) -> str:
        return FORMULA_EXPRESSION[self.formula]


def _plain(value: Decimal) -> str:
    """Человекочитаемая запись без экспоненты.

    ``Decimal(100).normalize()`` даёт ``1E+2``, и шкала «0–1E+2» в отчёте
    читается как опечатка, а не как ноль-сто.
    """
    if value == value.to_integral_value():
        return str(int(value))
    return format(value.normalize(), "f")


@dataclass(frozen=True)
class NormalizedScore:
    """Результат нормализации. Хранит исходник рядом с результатом."""

    state: ScoreState
    raw_value: Decimal | None
    source_scale_min: Decimal | None
    source_scale_max: Decimal | None
    formula: FormulaId | None
    normalized: Decimal | None
    reason: str = ""

    @property
    def ok(self) -> bool:
        return self.state is ScoreState.OK

    def display(self) -> str | None:
        """Внешние оценки показываются с одним знаком после запятой."""
        if self.normalized is None:
            return None
        return f"{self.normalized.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP):.1f}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "raw_value": None if self.raw_value is None else str(self.raw_value),
            "source_scale": (
                None
                if self.source_scale_max is None
                else f"{_plain(self.source_scale_min)}–{_plain(self.source_scale_max)}"
            ),
            "formula": None if self.formula is None else self.formula.value,
            "formula_expression": (
                None if self.formula is None else FORMULA_EXPRESSION[self.formula]
            ),
            "normalized": None if self.normalized is None else str(self.normalized),
            "display": self.display(),
            "reason": self.reason,
        }


def _to_decimal(raw: Any) -> Decimal | None:
    """Строгое приведение. bool — не число; NaN и inf — не числа."""
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, Decimal):
        return None if not raw.is_finite() else raw
    if isinstance(raw, int):
        return Decimal(raw)
    if isinstance(raw, float):
        if math.isnan(raw) or math.isinf(raw):
            return None
        return Decimal(str(raw))
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        try:
            value = Decimal(text)
        except InvalidOperation:
            return None
        return value if value.is_finite() else None
    return None


def normalize(raw: Any, contract: SourceScaleContract) -> NormalizedScore:
    """Привести исходное значение источника к шкале 1.0–10.0."""
    if not contract.verified:
        return NormalizedScore(
            state=ScoreState.CONTRACT_UNVERIFIED,
            raw_value=None,
            source_scale_min=contract.source_scale_min,
            source_scale_max=contract.source_scale_max,
            formula=contract.formula,
            normalized=None,
            reason=f"контракт шкалы {contract.source_key} не подтверждён живым ответом",
        )

    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return NormalizedScore(
            state=ScoreState.ABSENT,
            raw_value=None,
            source_scale_min=contract.source_scale_min,
            source_scale_max=contract.source_scale_max,
            formula=contract.formula,
            normalized=None,
            reason="источник не вернул значение",
        )

    value = _to_decimal(raw)
    if value is None:
        return NormalizedScore(
            state=ScoreState.INVALID_TYPE,
            raw_value=None,
            source_scale_min=contract.source_scale_min,
            source_scale_max=contract.source_scale_max,
            formula=contract.formula,
            normalized=None,
            reason=f"не число: {type(raw).__name__}",
        )

    if value == 0:
        return NormalizedScore(
            state=ScoreState.ZERO_NOT_A_RATING,
            raw_value=value,
            source_scale_min=contract.source_scale_min,
            source_scale_max=contract.source_scale_max,
            formula=contract.formula,
            normalized=None,
            reason="ноль у этого источника означает «ещё не оценили», а не оценку 0",
        )

    if value < 0:
        return NormalizedScore(
            state=ScoreState.INVALID_TYPE,
            raw_value=value,
            source_scale_min=contract.source_scale_min,
            source_scale_max=contract.source_scale_max,
            formula=contract.formula,
            normalized=None,
            reason="отрицательная оценка невозможна ни по одной объявленной шкале",
        )

    if value > contract.source_scale_max:
        return NormalizedScore(
            state=ScoreState.OUT_OF_RANGE_HIGH,
            raw_value=value,
            source_scale_min=contract.source_scale_min,
            source_scale_max=contract.source_scale_max,
            formula=contract.formula,
            normalized=None,
            reason=(
                f"значение {value} выше объявленной шкалы "
                f"{contract.scale_label} — контракт источника изменился"
            ),
        )

    normalized = _apply(contract.formula, value)

    if normalized > Decimal(str(SCALE_MAX)):
        return NormalizedScore(
            state=ScoreState.OUT_OF_RANGE_HIGH,
            raw_value=value,
            source_scale_min=contract.source_scale_min,
            source_scale_max=contract.source_scale_max,
            formula=contract.formula,
            normalized=None,
            reason=f"после нормализации {normalized} > {SCALE_MAX}",
        )

    if normalized < Decimal(str(SCALE_MIN)):
        # Значение настоящее, но ниже нашей шкалы. Подтягивать его до 1.0
        # значило бы показать пользователю оценку, которой источник не
        # ставил, поэтому оно не публикуется и остаётся с причиной.
        return NormalizedScore(
            state=ScoreState.OUT_OF_RANGE_LOW,
            raw_value=value,
            source_scale_min=contract.source_scale_min,
            source_scale_max=contract.source_scale_max,
            formula=contract.formula,
            normalized=normalized,
            reason=f"после нормализации {normalized} < {SCALE_MIN}; не публикуется",
        )

    return NormalizedScore(
        state=ScoreState.OK,
        raw_value=value,
        source_scale_min=contract.source_scale_min,
        source_scale_max=contract.source_scale_max,
        formula=contract.formula,
        normalized=normalized,
    )


def validate_community_score(raw: Any) -> int:
    """Оценка пользователя и редакции — только целое 1–10.

    Отдельная функция, а не переиспользование ``normalize``: у внешней
    оценки дробность допустима, у поставленной человеком — нет, и общая
    точка входа рано или поздно пропустила бы 8.5 в таблицу голосов.
    """
    if isinstance(raw, bool):
        raise ValueError("оценка должна быть целым числом 1–10, получено: bool")
    if isinstance(raw, float):
        if math.isnan(raw) or math.isinf(raw) or raw != int(raw):
            raise ValueError(f"оценка должна быть целым числом 1–10, получено: {raw!r}")
        raw = int(raw)
    if isinstance(raw, str):
        text = raw.strip()
        if not text or not (text.isdigit() or (text.startswith("-") and text[1:].isdigit())):
            raise ValueError(f"оценка должна быть целым числом 1–10, получено: {raw!r}")
        raw = int(text)
    if not isinstance(raw, int):
        raise ValueError(f"оценка должна быть целым числом 1–10, получено: {type(raw).__name__}")
    if raw < 1 or raw > 10:
        raise ValueError(f"оценка вне диапазона 1–10: {raw}")
    return raw
