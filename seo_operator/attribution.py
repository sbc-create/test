"""
Атрибуция изменений (ТЗ §5, шаг 3).

Центральное правило: «сделали, потом выросло» не является доказательством.
Модуль умеет три вещи и честно называет, какая из них применена:

- before_after   — самый слабый вывод, уверенность не выше LOW;
- controlled     — сравнение с контрольной группой, до MEDIUM;
- diff_in_diff   — difference-in-differences, единственный путь к HIGH.

Любой внешний фактор в окне (релиз, сезон, инцидент, обновление алгоритма)
понижает уверенность, а сильный — переводит вывод в INVALIDATED.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import Any, Sequence

from .statuses import Confidence, ExperimentOutcome, Status

MIN_DAYS_PER_PERIOD = 7
MIN_OBSERVATIONS_FOR_HIGH = 14
SIGNIFICANT_EFFECT_PCT = 5.0
LOSS_EFFECT_PCT = -5.0


class Method(str, Enum):
    BEFORE_AFTER = "before_after"
    CONTROLLED = "controlled"
    DIFF_IN_DIFF = "diff_in_diff"
    NONE = "none"


@dataclass(frozen=True)
class Series:
    """Ряд суточных значений одной метрики. Неполные дни исключаются вызывающим кодом."""

    name: str
    points: dict[date, float]

    def window(self, start: date, end: date) -> list[float]:
        return [v for d, v in sorted(self.points.items()) if start <= d <= end]

    def mean(self, start: date, end: date) -> float | None:
        vals = self.window(start, end)
        return statistics.fmean(vals) if vals else None

    def days(self, start: date, end: date) -> int:
        return len(self.window(start, end))


@dataclass
class Confounder:
    kind: str
    detail: str
    severity: str          # "soft" понижает уверенность, "hard" делает вывод невалидным

    @property
    def invalidates(self) -> bool:
        return self.severity == "hard"


@dataclass
class AttributionResult:
    method: Method
    treatment_change_pct: float | None
    control_change_pct: float | None
    lift_pct: float | None
    confidence: Confidence
    outcome: ExperimentOutcome
    confounders: list[Confounder] = field(default_factory=list)
    explanation: str = ""
    observations: dict[str, Any] = field(default_factory=dict)

    @property
    def causal_claim_allowed(self) -> bool:
        """Можно ли говорить «действие привело к», а не «наблюдалось вместе с»."""
        return self.method is Method.DIFF_IN_DIFF and self.confidence is Confidence.HIGH

    def phrase(self) -> str:
        """Формулировка, которую разрешено печатать в отчёте."""
        if self.outcome is ExperimentOutcome.INVALIDATED:
            return "Эксперимент испорчен внешними факторами — вывод не делается."
        if self.lift_pct is None:
            return "Данных недостаточно для вывода."
        if self.causal_claim_allowed:
            return f"Действие дало {self.lift_pct:+.1f}% относительно контроля (DiD, уверенность HIGH)."
        return (f"Наблюдалось изменение {self.lift_pct:+.1f}%; "
                f"метод {self.method.value}, уверенность {self.confidence.value} — "
                "причинная связь не утверждается.")


def _pct_change(before: float | None, after: float | None) -> float | None:
    if before is None or after is None or before == 0:
        return None
    return round((after - before) / before * 100, 2)


def analyze(*, treatment: Series, control: Series | None,
            change_date: date, today: date,
            period_days: int = 14, confounders: Sequence[Confounder] = (),
            lag_days: int = 0) -> AttributionResult:
    """
    change_date — день внедрения. lag_days — задержка данных источника: последние
    lag_days дней в окно «после» не берутся, иначе неполные дни занижают эффект.
    """
    confounders = list(confounders)

    before_end = change_date - timedelta(days=1)
    before_start = before_end - timedelta(days=period_days - 1)
    after_start = change_date
    after_end = min(today - timedelta(days=lag_days), change_date + timedelta(days=period_days - 1))

    t_before_days = treatment.days(before_start, before_end)
    t_after_days = treatment.days(after_start, after_end)

    if t_before_days < MIN_DAYS_PER_PERIOD or t_after_days < MIN_DAYS_PER_PERIOD:
        return AttributionResult(
            method=Method.NONE, treatment_change_pct=None, control_change_pct=None,
            lift_pct=None, confidence=Confidence.LOW, outcome=ExperimentOutcome.INCONCLUSIVE,
            confounders=confounders,
            explanation=(f"Полных дней до/после: {t_before_days}/{t_after_days} "
                         f"при минимуме {MIN_DAYS_PER_PERIOD}. Вывод не делается."),
            observations={"before_days": t_before_days, "after_days": t_after_days})

    t_change = _pct_change(treatment.mean(before_start, before_end),
                           treatment.mean(after_start, after_end))

    c_change = None
    if control is not None:
        c_before = control.days(before_start, before_end)
        c_after = control.days(after_start, after_end)
        if c_before >= MIN_DAYS_PER_PERIOD and c_after >= MIN_DAYS_PER_PERIOD:
            c_change = _pct_change(control.mean(before_start, before_end),
                                   control.mean(after_start, after_end))

    if c_change is not None:
        method = Method.DIFF_IN_DIFF
        lift = round(t_change - c_change, 2) if t_change is not None else None
    elif control is not None:
        method = Method.CONTROLLED
        lift = t_change
    else:
        method = Method.BEFORE_AFTER
        lift = t_change

    hard = [c for c in confounders if c.invalidates]
    soft = [c for c in confounders if not c.invalidates]

    if hard:
        return AttributionResult(
            method=method, treatment_change_pct=t_change, control_change_pct=c_change,
            lift_pct=lift, confidence=Confidence.LOW, outcome=ExperimentOutcome.INVALIDATED,
            confounders=confounders,
            explanation="Жёсткие внешние факторы в окне: " + "; ".join(c.detail for c in hard),
            observations={"before_days": t_before_days, "after_days": t_after_days})

    confidence = _confidence(method, t_after_days, len(soft), c_change)
    outcome = _outcome(lift, confidence)

    if outcome is ExperimentOutcome.WIN:
        explanation = f"Критерий успеха выполнен: {lift:+.1f}% при методе {method.value}."
    elif outcome is ExperimentOutcome.LOSS:
        explanation = f"Подтверждено ухудшение: {lift:+.1f}%."
    elif outcome is ExperimentOutcome.NEUTRAL:
        explanation = f"Эффект {lift:+.1f}% в пределах шума — значимого изменения нет."
    else:
        explanation = ("Эффект есть, но уверенность недостаточна для вывода"
                       if lift is not None else "Эффект не рассчитан.")
    if soft:
        explanation += " Учтены сопутствующие факторы: " + "; ".join(c.detail for c in soft) + "."

    return AttributionResult(
        method=method, treatment_change_pct=t_change, control_change_pct=c_change,
        lift_pct=lift, confidence=confidence, outcome=outcome, confounders=confounders,
        explanation=explanation,
        observations={"before_days": t_before_days, "after_days": t_after_days,
                      "before_window": f"{before_start}..{before_end}",
                      "after_window": f"{after_start}..{after_end}"})


def _confidence(method: Method, after_days: int, soft_confounders: int,
                control_change: float | None) -> Confidence:
    """HIGH достижим только через DiD с достаточным окном и без сопутствующих факторов."""
    if method is Method.DIFF_IN_DIFF and after_days >= MIN_OBSERVATIONS_FOR_HIGH \
            and soft_confounders == 0:
        return Confidence.HIGH
    if method in (Method.DIFF_IN_DIFF, Method.CONTROLLED) and soft_confounders <= 1:
        return Confidence.MEDIUM
    # before/after остаётся LOW всегда: у него нет защиты от сезонности.
    return Confidence.LOW


def _outcome(lift: float | None, confidence: Confidence) -> ExperimentOutcome:
    if lift is None:
        return ExperimentOutcome.INCONCLUSIVE
    if confidence is Confidence.LOW and abs(lift) >= SIGNIFICANT_EFFECT_PCT:
        # Заметное движение без надёжного метода — это не победа и не поражение.
        return ExperimentOutcome.INCONCLUSIVE
    if lift >= SIGNIFICANT_EFFECT_PCT:
        return ExperimentOutcome.WIN
    if lift <= LOSS_EFFECT_PCT:
        return ExperimentOutcome.LOSS
    return ExperimentOutcome.NEUTRAL


def link_to_actions(change_date: date, actions: Sequence[Any],
                    window_days: int = 7) -> list[dict[str, Any]]:
    """
    Какие наши действия предшествовали изменению. Возвращает кандидатов
    с оговоркой: одновременность нескольких действий не позволяет разделить их вклад.
    """
    start = change_date - timedelta(days=window_days)
    candidates = []
    for a in actions:
        executed = a["executed_at"] if isinstance(a, dict) or hasattr(a, "keys") else None
        if not executed:
            continue
        d = date.fromisoformat(str(executed)[:10])
        if start <= d <= change_date:
            candidates.append({"action_id": a["action_id"], "action_type": a["action_type"],
                               "executed_at": executed, "hypothesis": a["hypothesis"]})
    for c in candidates:
        c["separable"] = len(candidates) == 1
        if len(candidates) > 1:
            c["note"] = (f"Одновременно выполнено {len(candidates)} действий — "
                         "вклад каждого по отдельности не определяется.")
    return candidates
