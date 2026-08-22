"""
Оценка экспериментов.

Три вещи, которые делают оценку честной:
1) зрелость — не оценивать раньше порогов данных;
2) сравнение с holdout/control, а не с «до и после» (иначе сезонность засчитывается как эффект);
3) конфаундеры — внешние события, которые объясняют изменение без нашего вмешательства.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

from .. import config
from ..analysis import kpi
from .registry import Experiment


@dataclass
class MaturityCheck:
    mature: bool
    reasons: list[str] = field(default_factory=list)
    observed_days: int = 0
    impressions: float = 0.0
    clicks: float = 0.0


@dataclass
class Evaluation:
    experiment_id: str
    decision: str                      # keep | rollback | inconclusive | iterate
    confidence: float
    primary_delta_pct: float | None
    control_delta_pct: float | None
    lift_pct: float | None
    guardrail_breaches: list[str]
    confounders: list[str]
    stop_loss_triggered: bool
    explanation: str
    metrics: dict[str, Any] = field(default_factory=dict)


def check_maturity(exp: Experiment, treatment_rows: list[dict],
                   today: date | None = None) -> MaturityCheck:
    policy = config.experiment_policy()["maturity"]
    today = today or date.today()
    if not exp.started_at:
        return MaturityCheck(False, ["Эксперимент не запущен."])

    started = date.fromisoformat(exp.started_at)
    lag = policy["gsc_data_lag_days"]
    observed_days = max(0, (today - started).days - lag)

    impressions = sum(float(r.get("impressions") or 0) for r in treatment_rows)
    clicks = sum(float(r.get("clicks") or 0) for r in treatment_rows)

    reasons = []
    if observed_days < policy["min_observation_days"]:
        reasons.append(
            f"Наблюдение {observed_days} дн. < {policy['min_observation_days']} (с поправкой на задержку данных).")
    if impressions < policy["min_impressions"]:
        reasons.append(f"Показов {impressions:.0f} < {policy['min_impressions']}.")
    if clicks < policy["min_clicks"]:
        reasons.append(f"Кликов {clicks:.0f} < {policy['min_clicks']}.")

    weekday_pairs = _weekday_pairs(treatment_rows, started, today - timedelta(days=lag))
    if weekday_pairs < policy["min_comparable_weekday_pairs"]:
        reasons.append(f"Сопоставимых пар дней недели {weekday_pairs} < {policy['min_comparable_weekday_pairs']}.")

    return MaturityCheck(not reasons, reasons, observed_days, impressions, clicks)


def _weekday_pairs(rows: list[dict], start: date, end: date) -> int:
    seen: dict[int, int] = {}
    for r in rows:
        d_raw = r.get("date")
        if not d_raw:
            continue
        d = date.fromisoformat(d_raw)
        if start <= d <= end:
            seen[d.weekday()] = seen.get(d.weekday(), 0) + 1
    return min(seen.values()) if len(seen) >= 5 else 0


def check_stop_loss(exp: Experiment, treatment_delta_pct: dict[str, float],
                    guardrail_values: dict[str, Any]) -> tuple[bool, list[str]]:
    """Stop-loss срабатывает по окну в 7 дней, а не по одному плохому дню."""
    breaches = []
    sl = exp.stop_loss or {}
    for metric, limit in sl.items():
        if metric == "guardrail_violation":
            continue
        delta = treatment_delta_pct.get(metric)
        if delta is not None and delta <= -abs(float(limit)):
            breaches.append(f"{metric}: {delta:+.1f}% при пороге -{abs(float(limit))}%")
    for guard in exp.guardrails:
        value = guardrail_values.get(guard)
        if value is True or (isinstance(value, (int, float)) and value > 0):
            breaches.append(f"guardrail '{guard}' нарушен (значение {value})")
    return bool(breaches), breaches


def detect_confounders(exp: Experiment, context: dict[str, Any]) -> list[str]:
    """
    Отличает внешнее изменение от эффекта нашей работы.
    Ничего не «объясняет» само по себе — только помечает, что вывод ненадёжен.
    """
    found = []
    if context.get("algorithm_update_window"):
        found.append("algorithm_update: обновление алгоритма в окне наблюдения")
    if context.get("incident_ids"):
        found.append(f"incident: {context['incident_ids']}")
    if context.get("seasonality_zscore", 0) and abs(context["seasonality_zscore"]) > 2:
        found.append(f"seasonality: z={context['seasonality_zscore']:.1f}")
    if context.get("competitor_release_event"):
        found.append("competitor_or_release_event в окне")
    if context.get("concurrent_experiments"):
        found.append(f"portfolio_internal_change: одновременные эксперименты {context['concurrent_experiments']}")
    if context.get("deploy_in_window"):
        found.append("deploy: релиз кода в окне наблюдения")
    return found


def evaluate(exp: Experiment, treatment_rows: list[dict], control_rows: list[dict],
             guardrail_values: dict[str, Any], context: dict[str, Any],
             today: date | None = None) -> Evaluation:
    today = today or date.today()
    maturity = check_maturity(exp, treatment_rows, today)

    if not maturity.mature:
        return Evaluation(
            experiment_id=exp.id, decision="inconclusive", confidence=0.0,
            primary_delta_pct=None, control_delta_pct=None, lift_pct=None,
            guardrail_breaches=[], confounders=[], stop_loss_triggered=False,
            explanation="Данные не созрели: " + " ".join(maturity.reasons),
            metrics={"observed_days": maturity.observed_days,
                     "impressions": maturity.impressions, "clicks": maturity.clicks},
        )

    metric = exp.primary_kpi
    lag = config.experiment_policy()["maturity"]["gsc_data_lag_days"]
    end = today - timedelta(days=lag)
    window = min(28, maturity.observed_days)

    t = kpi.comparable_window(_as_metric_rows(treatment_rows, metric), metric, end, window)
    c = kpi.comparable_window(_as_metric_rows(control_rows, metric), metric, end, window) if control_rows else None

    treatment_delta = t.delta_pct
    control_delta = c.delta_pct if c else None
    lift = None
    if treatment_delta is not None and control_delta is not None:
        lift = round(treatment_delta - control_delta, 2)
    elif treatment_delta is not None:
        lift = treatment_delta

    stop_triggered, breaches = check_stop_loss(
        exp, {metric: treatment_delta} if treatment_delta is not None else {}, guardrail_values)
    confounders = detect_confounders(exp, context)

    confidence = _confidence(maturity, t, c, confounders)

    if stop_triggered:
        decision = "rollback"
        explanation = "Сработал stop-loss: " + "; ".join(breaches)
    elif lift is None:
        decision = "inconclusive"
        explanation = "Недостаточно сопоставимых данных для расчёта эффекта."
    elif confounders and confidence < 0.5:
        decision = "inconclusive"
        explanation = ("Изменение может объясняться внешними причинами: " + "; ".join(confounders) +
                       ". Эффект не приписывается эксперименту.")
    elif lift >= 5 and confidence >= 0.6:
        decision = "keep"
        explanation = f"Прирост {lift:+.1f}% против контроля при уверенности {confidence:.2f}."
    elif lift <= -10 and confidence >= 0.6:
        decision = "rollback"
        explanation = f"Ухудшение {lift:+.1f}% против контроля при уверенности {confidence:.2f}."
    elif abs(lift) < 5:
        decision = "inconclusive"
        explanation = f"Эффект {lift:+.1f}% в пределах шума — оставлять как выигрыш нельзя."
    else:
        decision = "iterate"
        explanation = f"Эффект {lift:+.1f}%, уверенность {confidence:.2f} — требуется доработка и повтор."

    return Evaluation(
        experiment_id=exp.id, decision=decision, confidence=confidence,
        primary_delta_pct=treatment_delta, control_delta_pct=control_delta, lift_pct=lift,
        guardrail_breaches=breaches, confounders=confounders,
        stop_loss_triggered=stop_triggered, explanation=explanation,
        metrics={
            "observed_days": maturity.observed_days,
            "impressions": maturity.impressions,
            "clicks": maturity.clicks,
            "treatment_window": t.__dict__,
            "control_window": c.__dict__ if c else None,
        },
    )


def _as_metric_rows(rows: list[dict], metric: str) -> list[dict]:
    out = []
    for r in rows:
        if "date" not in r:
            continue
        if metric in r:
            out.append({"date": r["date"], "value": r[metric], "completeness": r.get("completeness", 1.0)})
    return out


def _confidence(maturity: MaturityCheck, t: kpi.WindowMetric,
                c: kpi.WindowMetric | None, confounders: list[str]) -> float:
    score = 0.0
    score += 0.3 if t.complete else 0.0
    score += 0.2 if c is not None else 0.0
    score += 0.2 * min(1.0, maturity.clicks / 200.0)
    score += 0.2 * min(1.0, maturity.observed_days / 28.0)
    score += 0.1 if maturity.impressions >= 5000 else 0.0
    score -= 0.2 * len(confounders)
    return round(max(0.0, min(1.0, score)), 2)
