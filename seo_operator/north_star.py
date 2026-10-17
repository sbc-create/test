"""
organic_daily_unique — единственное определение целевого показателя (ТЗ §2).

Три места, где обычно теряется честность, и как они закрыты здесь:

1. Неполный день. Он не смешивается с полными: median-28 берётся строго
   по последним 28 ПОЛНЫМ дням, а не по последним 28 календарным.
2. Сумма по счётчикам. Она не называется «уникальной аудиторией портфеля»,
   пока не доказана возможность дедупликации между доменами.
3. Отсутствие данных. Возвращается NOT_MEASURED или DATA_DELAY, а не 0.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import Any, Iterable, Sequence

from .statuses import Measurement, Status, data_delay, measured, not_measured

METRIC = "organic_daily_unique"
MEDIAN_WINDOW_DAYS = 28

# Полнота дня, ниже которой день не считается полным и в медиану не входит.
MIN_DAY_COMPLETENESS = 0.95


class Engine(str, Enum):
    YANDEX = "yandex"
    GOOGLE = "google"
    OTHER = "other"


# Трафик, который в целевой показатель не входит никогда (ТЗ §2).
EXCLUDED_SOURCES = frozenset({
    "paid", "ad", "direct", "referral", "internal", "social",
    "email", "purchased", "bot", "monitoring",
})


class DedupMode(str, Enum):
    """Как считается портфельная сумма."""

    NONE = "none"                 # дедупликация невозможна — сумма с оговоркой
    ESTIMATED = "estimated"       # оценка пересечения по доступным данным
    EXACT = "exact"               # общий идентификатор посетителя между доменами


@dataclass(frozen=True)
class DayPoint:
    """Один суточный замер по одному счётчику."""

    site_id: str
    day: date
    engine: Engine
    unique_visitors: int
    completeness: float
    source: str
    is_bot_filtered: bool = True

    @property
    def is_full_day(self) -> bool:
        return self.completeness >= MIN_DAY_COMPLETENESS


@dataclass
class SiteNorthStar:
    site_id: str
    median_28: Measurement
    by_engine: dict[Engine, Measurement] = field(default_factory=dict)
    full_days_used: int = 0
    latest_full_day: date | None = None


@dataclass
class PortfolioNorthStar:
    """
    Портфельный показатель. `sum_of_counters` — это именно сумма по счётчикам;
    название «уникальная аудитория портфеля» применимо только при dedup_mode=EXACT.
    """

    sum_of_counters: Measurement
    dedup_mode: DedupMode
    overlap_estimate: Measurement
    deduplicated: Measurement
    by_engine: dict[Engine, Measurement]
    per_site: list[SiteNorthStar]
    caveat: str

    @property
    def headline(self) -> Measurement:
        """Показатель, который можно называть целевым. При отсутствии дедупликации — сумма с оговоркой."""
        return self.deduplicated if self.deduplicated.measured else self.sum_of_counters


def _full_days(points: Iterable[DayPoint]) -> list[DayPoint]:
    return [p for p in points if p.is_full_day and p.is_bot_filtered]


def last_full_day(points: Sequence[DayPoint]) -> date | None:
    days = [p.day for p in _full_days(points)]
    return max(days) if days else None


def actual_source(points: Sequence[DayPoint], fallback: str) -> str:
    """
    Источник берётся из самих данных, а не из параметра вызова: иначе метрика
    заявляет происхождение, которого у неё нет. Разные источники в одном ряду
    показываются явно — это повод для проверки, а не для усреднения.
    """
    sources = sorted({p.source for p in points if p.source})
    if not sources:
        return fallback
    return sources[0] if len(sources) == 1 else "+".join(sources)


def median_28(points: Sequence[DayPoint], site_id: str, today: date,
              source: str = "yandex_metrika") -> tuple[Measurement, int, date | None]:
    """
    Медиана суточных уников за последние 28 ПОЛНЫХ дней.

    Возвращает (измерение, число использованных дней, последний полный день).
    Меньше 28 полных дней — DATA_DELAY, а не медиана по тому, что есть:
    иначе показатель молча меняет смысл при каждом сбое сбора.
    """
    source = actual_source(points, source)
    full = _full_days(points)
    if not full:
        return not_measured(
            METRIC, f"{site_id}: нет ни одного полного дня по данным {source}", source), 0, None

    newest = max(p.day for p in full)
    window_start = newest - timedelta(days=MEDIAN_WINDOW_DAYS - 1)

    # Суммируем по движкам внутри дня: показатель суточный, а не по-движковый.
    per_day: dict[date, int] = {}
    for p in full:
        if window_start <= p.day <= newest:
            per_day[p.day] = per_day.get(p.day, 0) + p.unique_visitors

    if len(per_day) < MEDIAN_WINDOW_DAYS:
        return data_delay(
            METRIC,
            f"{site_id}: полных дней {len(per_day)} из {MEDIAN_WINDOW_DAYS}; "
            "медиана по неполному окну меняет смысл показателя и не публикуется",
            source, expected_by=(newest + timedelta(days=MEDIAN_WINDOW_DAYS - len(per_day))).isoformat(),
        ), len(per_day), newest

    lag_days = (today - newest).days
    note = f"задержка данных {lag_days} дн." if lag_days > 1 else ""
    value = int(statistics.median(per_day.values()))
    return measured(METRIC, value, source,
                    period=f"{window_start.isoformat()}..{newest.isoformat()} (28 полных дней)",
                    as_of=newest.isoformat(), unit="уник./сут", note=note), len(per_day), newest


def by_engine(points: Sequence[DayPoint], site_id: str, today: date,
              source: str = "yandex_metrika") -> dict[Engine, Measurement]:
    """Яндекс, Google и прочие показываются отдельно (ТЗ §2)."""
    out: dict[Engine, Measurement] = {}
    for engine in Engine:
        subset = [p for p in points if p.engine is engine]
        if not subset:
            out[engine] = not_measured(
                f"{METRIC}.{engine.value}", f"{site_id}: нет данных по {engine.value}", source)
            continue
        m, _, _ = median_28(subset, site_id, today, source)
        out[engine] = Measurement(
            metric=f"{METRIC}.{engine.value}", value=m.value, status=m.status,
            source=m.source, period=m.period, as_of=m.as_of, note=m.note, unit=m.unit)
    return out


def site_north_star(points: Sequence[DayPoint], site_id: str, today: date,
                    source: str = "yandex_metrika") -> SiteNorthStar:
    m, used, newest = median_28(points, site_id, today, source)
    return SiteNorthStar(site_id=site_id, median_28=m, by_engine=by_engine(points, site_id, today, source),
                         full_days_used=used, latest_full_day=newest)


def portfolio_north_star(per_site_points: dict[str, Sequence[DayPoint]], today: date,
                         dedup_mode: DedupMode = DedupMode.NONE,
                         overlap_share: float | None = None,
                         source: str = "yandex_metrika") -> PortfolioNorthStar:
    """
    Портфельный показатель.

    overlap_share — доля аудитории, пересекающейся между доменами (0..1).
    Без неё и без EXACT дедупликации портфельное число остаётся суммой по счётчикам,
    и это прямо написано в caveat.
    """
    sites = [site_north_star(pts, sid, today, source) for sid, pts in sorted(per_site_points.items())]
    usable = [s for s in sites if s.median_28.measured]
    # Портфельные измерения наследуют фактический источник сайтов, а не параметр вызова.
    source = actual_source([p for pts in per_site_points.values() for p in pts], source)

    if not usable:
        blocked_metric = not_measured(
            f"portfolio.{METRIC}",
            f"ни один из {len(sites)} сайтов не имеет 28 полных дней", source)
        return PortfolioNorthStar(
            sum_of_counters=blocked_metric, dedup_mode=dedup_mode,
            overlap_estimate=not_measured("portfolio.overlap", "нет измеренных сайтов"),
            deduplicated=blocked_metric,
            by_engine={e: not_measured(f"portfolio.{METRIC}.{e.value}", "нет измеренных сайтов")
                       for e in Engine},
            per_site=sites,
            caveat="Портфельный показатель не измерен: ни один сайт не набрал 28 полных дней.")

    total = sum(int(s.median_28.value) for s in usable)  # type: ignore[arg-type]
    period = f"медиана 28 полных дней, {len(usable)} из {len(sites)} сайтов"
    as_of = max((s.latest_full_day for s in usable if s.latest_full_day), default=today).isoformat()

    sum_m = measured(f"portfolio.{METRIC}.sum_of_counters", total, source,
                     period=period, as_of=as_of, unit="уник./сут",
                     note="сумма по счётчикам, не дедуплицировано" if dedup_mode is not DedupMode.EXACT else "")

    if dedup_mode is DedupMode.EXACT:
        overlap = measured("portfolio.overlap", 0.0, source, period, as_of, unit="доля",
                           note="сквозной идентификатор посетителя между доменами")
        dedup = measured(f"portfolio.{METRIC}", total, source, period, as_of, unit="уник./сут")
        caveat = "Дедупликация выполнена по сквозному идентификатору — число является уникальной аудиторией портфеля."
    elif dedup_mode is DedupMode.ESTIMATED and overlap_share is not None:
        if not 0.0 <= overlap_share <= 1.0:
            raise ValueError("overlap_share вне диапазона 0..1")
        overlap = measured("portfolio.overlap", round(overlap_share, 4), source, period, as_of,
                           unit="доля", note="оценка, не точный замер")
        dedup = measured(f"portfolio.{METRIC}", int(total * (1 - overlap_share)), source,
                         period=period, as_of=as_of, unit="уник./сут",
                         note=f"оценка с поправкой на пересечение {overlap_share:.1%}")
        caveat = (f"Пересечение аудитории между доменами оценено в {overlap_share:.1%} и вычтено. "
                  "Это оценка, а не точный замер.")
    else:
        overlap = not_measured("portfolio.overlap",
                               "дедупликация между доменами технически невозможна", source)
        dedup = not_measured(
            f"portfolio.{METRIC}",
            "без дедупликации сумма по счётчикам не является уникальной аудиторией портфеля", source)
        caveat = ("Дедупликация между доменами невозможна: показано СУММУ ПО СЧЁТЧИКАМ. "
                  "Называть это уникальной аудиторией портфеля нельзя — один человек, "
                  "посетивший три сайта, посчитан трижды.")

    engines: dict[Engine, Measurement] = {}
    for engine in Engine:
        values = [int(s.by_engine[engine].value) for s in sites
                  if engine in s.by_engine and s.by_engine[engine].measured]
        if values:
            engines[engine] = measured(f"portfolio.{METRIC}.{engine.value}", sum(values),
                                       source, period, as_of, unit="уник./сут",
                                       note="сумма по счётчикам")
        else:
            engines[engine] = not_measured(f"portfolio.{METRIC}.{engine.value}",
                                           f"нет измеренных сайтов с данными по {engine.value}", source)

    return PortfolioNorthStar(sum_of_counters=sum_m, dedup_mode=dedup_mode,
                              overlap_estimate=overlap, deduplicated=dedup,
                              by_engine=engines, per_site=sites, caveat=caveat)


def validate_source_excluded(source_name: str) -> bool:
    """True, если такой источник трафика обязан быть исключён из целевого показателя."""
    return source_name.strip().lower() in EXCLUDED_SOURCES
