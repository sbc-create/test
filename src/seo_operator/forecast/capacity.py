"""
Прогноз: достаточно ли портфеля для 7 000 000 уников/сутки (ТЗ §8).

Главное свойство этого модуля — он отказывается считать при недостатке фактов.
Прогноз строится на ФАКТИЧЕСКИХ перцентилях зрелых сайтов портфеля; при
отсутствии зрелой когорты возвращается INCONCLUSIVE, а не «отраслевая оценка».

Три сценария — не украшение: одна точная цифра здесь была бы ложью, потому что
разброс между P25 и P75 у сайтов одного возраста обычно кратный.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any, Sequence

from ..statuses import Confidence, Measurement, Status, inconclusive, measured, not_measured

TARGET_DAILY_UNIQUE = 7_000_000

# Возрастные когорты в днях (ТЗ §8).
AGE_COHORTS = (30, 60, 90, 180)

# Сайт считается зрелым, когда вышел на плато: возраст и стабильность.
MATURITY_AGE_DAYS = 180
MIN_MATURE_SITES_FOR_PERCENTILES = 5


class Scenario(str, Enum):
    CONSERVATIVE = "conservative"
    BASE = "base"
    OPTIMISTIC = "optimistic"


SCENARIO_PERCENTILE = {
    Scenario.CONSERVATIVE: 25,
    Scenario.BASE: 50,
    Scenario.OPTIMISTIC: 75,
}

SCENARIO_RU = {
    Scenario.CONSERVATIVE: "Консервативный",
    Scenario.BASE: "Базовый",
    Scenario.OPTIMISTIC: "Оптимистичный",
}


@dataclass(frozen=True)
class SiteFact:
    """Факт по одному сайту портфеля. Никаких оценок — только измеренное."""

    site_id: str
    direction: str
    age_days: int
    daily_unique: int | None            # None => не измерен, в перцентили не входит
    is_alive: bool = True               # False => закрыт/выпал, нужен для survival rate
    launched_at: date | None = None
    days_to_first_traffic: int | None = None
    days_to_plateau: int | None = None

    @property
    def is_mature(self) -> bool:
        return self.age_days >= MATURITY_AGE_DAYS

    @property
    def is_measured(self) -> bool:
        return self.daily_unique is not None


@dataclass
class CohortStats:
    age_bucket: int
    total: int
    measured: int
    alive: int
    p25: Measurement
    p50: Measurement
    p75: Measurement
    survival_rate: Measurement


@dataclass
class ScenarioForecast:
    scenario: Scenario
    per_site_daily: Measurement          # прогноз зрелого сайта (факт-перцентиль)
    success_probability: Measurement     # факт выживаемости когорты
    required_new_sites: Measurement
    reserve_domains: Measurement
    expected_months: Measurement
    confidence: Confidence


@dataclass
class CapacityForecast:
    current: Measurement
    target: int
    gap: Measurement
    scenarios: list[ScenarioForecast]
    cohorts: list[CohortStats]
    growth_without_new_sites: Measurement
    operational_capacity_note: str
    cannibalization_risk_note: str
    blockers: list[str] = field(default_factory=list)

    @property
    def required_range(self) -> str:
        """Диапазон новых сайтов для §18 REQUIRED_NEW_SITES_RANGE."""
        values = [int(s.required_new_sites.value) for s in self.scenarios
                  if s.required_new_sites.measured]
        if not values:
            return Status.INCONCLUSIVE.value
        return f"{min(values)}-{max(values)}"


def _percentile(values: Sequence[float], p: int) -> float:
    """Линейная интерполяция. На выборке меньше 2 значений возвращает единственное."""
    if not values:
        raise ValueError("пустая выборка")
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    k = (len(ordered) - 1) * (p / 100.0)
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return float(ordered[int(k)])
    return float(ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo))


def cohort_stats(sites: Sequence[SiteFact], age_bucket: int, as_of: str,
                 source: str = "portfolio_registry") -> CohortStats:
    """
    Статистика когорты. Перцентили считаются только по ИЗМЕРЕННЫМ живым сайтам;
    выживаемость — по всем сайтам когорты, иначе она всегда была бы 100%.
    """
    in_cohort = [s for s in sites if s.age_days >= age_bucket]
    measured_alive = [s for s in in_cohort if s.is_measured and s.is_alive]
    values = [float(s.daily_unique) for s in measured_alive]  # type: ignore[arg-type]
    period = f"когорта {age_bucket}+ дней"

    def pct(p: int) -> Measurement:
        name = f"cohort_{age_bucket}d.p{p}"
        if len(values) < MIN_MATURE_SITES_FOR_PERCENTILES:
            return inconclusive(
                name,
                f"измеренных живых сайтов {len(values)} < {MIN_MATURE_SITES_FOR_PERCENTILES}; "
                "перцентиль на такой выборке не является фактом",
                source)
        return measured(name, int(_percentile(values, p)), source, period, as_of, unit="уник./сут")

    if in_cohort:
        alive = sum(1 for s in in_cohort if s.is_alive)
        survival = measured(f"cohort_{age_bucket}d.survival", round(alive / len(in_cohort), 3),
                            source, period, as_of, unit="доля")
    else:
        alive = 0
        survival = not_measured(f"cohort_{age_bucket}d.survival",
                                "в когорте нет сайтов", source)

    return CohortStats(age_bucket=age_bucket, total=len(in_cohort), measured=len(values),
                       alive=alive, p25=pct(25), p50=pct(50), p75=pct(75),
                       survival_rate=survival)


def _months_estimate(sites: Sequence[SiteFact], source: str, as_of: str) -> Measurement:
    """Срок выхода на плато — по фактическим наблюдениям, не по общим соображениям."""
    observed = [s.days_to_plateau for s in sites if s.days_to_plateau]
    if len(observed) < 3:
        return inconclusive("time_to_plateau_months",
                            f"наблюдений выхода на плато {len(observed)} < 3", source)
    median_days = statistics.median(observed)
    return measured("time_to_plateau_months", round(median_days / 30.0, 1), source,
                    period=f"по {len(observed)} наблюдениям", as_of=as_of, unit="мес.")


def forecast(sites: Sequence[SiteFact], current: Measurement, as_of: str,
             target: int = TARGET_DAILY_UNIQUE,
             operational_capacity_sites_per_month: int | None = None,
             source: str = "portfolio_registry") -> CapacityForecast:
    """
    Основной расчёт. Возвращает три сценария или честный INCONCLUSIVE.

    Резервные домены закладываются исходя из фактической выживаемости когорты:
    если выживает 60% сайтов, на N рабочих нужно N/0.6 запусков.
    """
    blockers: list[str] = []
    cohorts = [cohort_stats(sites, bucket, as_of, source) for bucket in AGE_COHORTS]
    mature = next((c for c in cohorts if c.age_bucket == MATURITY_AGE_DAYS), cohorts[-1])

    if not current.measured:
        gap = not_measured("target_gap",
                           f"текущий показатель не измерен: {current.note or current.status.value}",
                           source)
        blockers.append("Текущий organic_daily_unique не измерен — разрыв до цели рассчитать нельзя.")
    else:
        gap_value = max(0, target - int(current.value))  # type: ignore[arg-type]
        gap = measured("target_gap", gap_value, source, current.period, as_of, unit="уник./сут",
                       note="цель достигнута" if gap_value == 0 else "")

    months = _months_estimate(sites, source, as_of)
    survival = mature.survival_rate

    if mature.measured < MIN_MATURE_SITES_FOR_PERCENTILES:
        blockers.append(
            f"Зрелых измеренных сайтов ({MATURITY_AGE_DAYS}+ дней): {mature.measured} — "
            f"нужно минимум {MIN_MATURE_SITES_FOR_PERCENTILES}, чтобы перцентили были фактом, "
            "а не выдумкой.")

    scenarios: list[ScenarioForecast] = []
    for scenario in Scenario:
        p = SCENARIO_PERCENTILE[scenario]
        per_site = {25: mature.p25, 50: mature.p50, 75: mature.p75}[p]

        if not (per_site.measured and gap.measured):
            reason = ("нет фактических перцентилей зрелой когорты"
                      if not per_site.measured else "разрыв до цели не измерен")
            scenarios.append(ScenarioForecast(
                scenario=scenario, per_site_daily=per_site, success_probability=survival,
                required_new_sites=inconclusive(f"required_new_sites.{scenario.value}", reason, source),
                reserve_domains=inconclusive(f"reserve_domains.{scenario.value}", reason, source),
                expected_months=months, confidence=Confidence.LOW))
            continue

        per_site_value = float(per_site.value)  # type: ignore[arg-type]
        if per_site_value <= 0:
            scenarios.append(ScenarioForecast(
                scenario=scenario, per_site_daily=per_site, success_probability=survival,
                required_new_sites=inconclusive(f"required_new_sites.{scenario.value}",
                                                "прогноз на сайт равен нулю", source),
                reserve_domains=inconclusive(f"reserve_domains.{scenario.value}",
                                             "прогноз на сайт равен нулю", source),
                expected_months=months, confidence=Confidence.LOW))
            continue

        needed = math.ceil(float(gap.value) / per_site_value)  # type: ignore[arg-type]
        period = f"{mature.p50.period}, сценарий {scenario.value}"

        if survival.measured and 0 < float(survival.value) <= 1:  # type: ignore[arg-type]
            launches = math.ceil(needed / float(survival.value))  # type: ignore[arg-type]
            reserve = measured(f"reserve_domains.{scenario.value}", launches - needed, source,
                               period, as_of, unit="дом.",
                               note=f"выживаемость когорты {float(survival.value):.0%}")
        else:
            reserve = inconclusive(f"reserve_domains.{scenario.value}",
                                   "выживаемость когорты не измерена", source)

        # Уверенность падает, когда выборка мала или срок выхода на плато неизвестен.
        if mature.measured >= 20 and months.measured:
            conf = Confidence.HIGH
        elif mature.measured >= 10:
            conf = Confidence.MEDIUM
        else:
            conf = Confidence.LOW

        scenarios.append(ScenarioForecast(
            scenario=scenario, per_site_daily=per_site, success_probability=survival,
            required_new_sites=measured(f"required_new_sites.{scenario.value}", needed, source,
                                        period, as_of, unit="сайт."),
            reserve_domains=reserve, expected_months=months, confidence=conf))

    growth = _growth_without_new_sites(sites, current, as_of, source)

    if operational_capacity_sites_per_month:
        capacity_note = (f"Операционная мощность: {operational_capacity_sites_per_month} сайтов/мес. "
                         "Срок = требуемые запуски / мощность, если она не изменится.")
    else:
        capacity_note = ("Операционная мощность не задана владельцем — срок запуска "
                         "требуемого числа сайтов рассчитать нельзя.")

    cannibal_note = ("Риск каннибализации растёт с числом сайтов в одном направлении: "
                     "новые домены могут забирать показы у уже работающих, а не добавлять "
                     "к портфелю. Контролируется detect() в analysis/cannibalization.py "
                     "по cross_tenant-конфликтам.")

    return CapacityForecast(current=current, target=target, gap=gap, scenarios=scenarios,
                            cohorts=cohorts, growth_without_new_sites=growth,
                            operational_capacity_note=capacity_note,
                            cannibalization_risk_note=cannibal_note, blockers=blockers)


def _growth_without_new_sites(sites: Sequence[SiteFact], current: Measurement,
                              as_of: str, source: str) -> Measurement:
    """
    Альтернатива покупке доменов: сколько даст доведение существующих сайтов
    до уровня P75 своей когорты. Считается только по фактам.
    """
    mature_measured = [s for s in sites if s.is_mature and s.is_measured and s.is_alive]
    if len(mature_measured) < MIN_MATURE_SITES_FOR_PERCENTILES:
        return inconclusive("growth_without_new_sites",
                            f"зрелых измеренных сайтов {len(mature_measured)} < "
                            f"{MIN_MATURE_SITES_FOR_PERCENTILES}", source)

    values = [float(s.daily_unique) for s in mature_measured]  # type: ignore[arg-type]
    p75 = _percentile(values, 75)
    upside = sum(max(0.0, p75 - v) for v in values)
    return measured("growth_without_new_sites", int(upside), source,
                    period=f"подтягивание {len(mature_measured)} зрелых сайтов до P75 когорты",
                    as_of=as_of, unit="уник./сут",
                    note="верхняя оценка: предполагает, что каждый сайт достижим до уровня P75")


def render_table(fc: CapacityForecast) -> str:
    """Таблица в формате ТЗ §8."""
    lines = [
        "| Сценарий | Прогноз зрелого сайта | Вероятность успеха | Нужны новые сайты | Резервные домены | Срок | Уверенность |",
        "|---|---|---|---|---|---|---|",
    ]
    for s in fc.scenarios:
        lines.append(
            f"| {SCENARIO_RU[s.scenario]} | {s.per_site_daily.render()} | "
            f"{s.success_probability.render()} | {s.required_new_sites.render()} | "
            f"{s.reserve_domains.render()} | {s.expected_months.render()} | {s.confidence.value} |")
    return "\n".join(lines)
