"""
Расчёт KPI на сопоставимых окнах.

Два правила, из-за которых обычно врут SEO-отчёты и которых здесь нет:
1) неполные дни не сравниваются с полными;
2) окна сравниваются по одинаковому набору дней недели.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Iterable, Sequence


@dataclass(frozen=True)
class WindowMetric:
    metric: str
    window_days: int
    current: float
    previous: float
    delta_abs: float
    delta_pct: float | None
    comparable_days: int
    complete: bool

    @property
    def direction(self) -> str:
        if self.delta_pct is None:
            return "unknown"
        if self.delta_pct > 2:
            return "up"
        if self.delta_pct < -2:
            return "down"
        return "flat"


def _weekday_aligned(rows: Sequence[dict], end: date, days: int) -> dict[int, list[float]]:
    """Группирует значения окна по дню недели."""
    start = end - timedelta(days=days - 1)
    out: dict[int, list[float]] = {i: [] for i in range(7)}
    for r in rows:
        d = date.fromisoformat(r["date"])
        if start <= d <= end:
            out[d.weekday()].append(float(r.get("value", 0)))
    return out


def comparable_window(rows: Sequence[dict], metric: str, end: date, days: int,
                      min_completeness: float = 0.9) -> WindowMetric:
    """
    Сравнивает [end-days+1 .. end] с непосредственно предыдущим окном той же длины,
    учитывая только дни недели, представленные в ОБОИХ окнах.
    """
    usable = [r for r in rows if r.get("completeness", 1.0) >= min_completeness]
    prev_end = end - timedelta(days=days)

    cur = _weekday_aligned(usable, end, days)
    prev = _weekday_aligned(usable, prev_end, days)

    shared = [wd for wd in range(7) if cur[wd] and prev[wd]]
    cur_sum = sum(sum(cur[wd]) for wd in shared)
    prev_sum = sum(sum(prev[wd]) for wd in shared)
    comparable_days = sum(len(cur[wd]) for wd in shared)

    delta_pct = None if prev_sum == 0 else round((cur_sum - prev_sum) / prev_sum * 100, 2)
    expected_days = days
    return WindowMetric(
        metric=metric, window_days=days, current=cur_sum, previous=prev_sum,
        delta_abs=cur_sum - prev_sum, delta_pct=delta_pct,
        comparable_days=comparable_days,
        complete=comparable_days >= expected_days * 0.7,
    )


def position_buckets(rows: Iterable[dict]) -> dict[str, int]:
    """Доля отслеживаемых запросов в TOP-3 / TOP-10 / TOP-20."""
    buckets = {"top3": 0, "top10": 0, "top20": 0, "beyond": 0, "total": 0}
    for r in rows:
        pos = r.get("position")
        if pos is None:
            continue
        buckets["total"] += 1
        if pos <= 3:
            buckets["top3"] += 1
        if pos <= 10:
            buckets["top10"] += 1
        if pos <= 20:
            buckets["top20"] += 1
        else:
            buckets["beyond"] += 1
    return buckets


def ctr_vs_expected(position: float, ctr: float, curve: dict[int, float] | None = None) -> float:
    """
    CTR относительно ожидаемого для позиции. >1 = лучше ожидания.
    Кривая по умолчанию грубая; при наличии портфельных данных заменяется на измеренную.
    """
    curve = curve or {1: 0.28, 2: 0.15, 3: 0.11, 4: 0.08, 5: 0.06,
                      6: 0.05, 7: 0.04, 8: 0.034, 9: 0.03, 10: 0.026}
    bucket = min(10, max(1, int(round(position))))
    expected = curve.get(bucket, 0.01)
    return round(ctr / expected, 3) if expected else 0.0


def weighted_position(rows: Iterable[dict]) -> float | None:
    """Позиция, взвешенная по показам: медиана по запросам вводит в заблуждение при перекосе спроса."""
    num = den = 0.0
    for r in rows:
        imp = float(r.get("impressions") or 0)
        pos = r.get("position")
        if pos is None or imp <= 0:
            continue
        num += pos * imp
        den += imp
    return round(num / den, 2) if den else None


def median_position(rows: Iterable[dict]) -> float | None:
    values = [float(r["position"]) for r in rows if r.get("position") is not None]
    return round(statistics.median(values), 2) if values else None


def entrances_per_1k_indexable(organic_entrances: float, indexable_pages: int) -> float | None:
    if not indexable_pages:
        return None
    return round(organic_entrances / indexable_pages * 1000, 2)


def impression_coverage(pages_with_impressions: int, indexable_pages: int) -> float | None:
    """Доля индексируемых страниц, получивших хотя бы один показ. Ловит «мёртвый» индекс."""
    if not indexable_pages:
        return None
    return round(pages_with_impressions / indexable_pages, 4)
