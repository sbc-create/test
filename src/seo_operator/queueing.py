"""
Очереди, квоты и rate limiting для портфеля 100+ сайтов (ТЗ §4).

Требование, вокруг которого построен модуль: сбой одного сайта или одного API
не должен останавливать портфель. Поэтому:

- квота API делится между сайтами, а не расходуется первым в алфавите;
- сайт, исчерпавший попытки, уходит в карантин и не блокирует очередь;
- backoff считается от типа ошибки: 429 и 5xx ждут, 401 и 403 не ждут никогда.
"""
from __future__ import annotations

import hashlib
import math
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Iterable, Sequence

from .statuses import Status


class FailureKind(str, Enum):
    """От типа ошибки зависит, имеет ли смысл повтор."""

    TRANSIENT_NETWORK = "transient_network"
    RATE_LIMIT = "rate_limit"
    SERVER_ERROR = "server_error"
    AUTH = "auth"                 # повтор бессмысленен: токен не починится сам
    FORBIDDEN = "forbidden"       # нет прав: повтор бессмысленен
    NOT_FOUND = "not_found"
    SCHEMA = "schema"             # контракт изменился: нужен человек
    RIGHTS = "rights"


RETRIABLE = frozenset({FailureKind.TRANSIENT_NETWORK, FailureKind.RATE_LIMIT,
                       FailureKind.SERVER_ERROR})

TERMINAL_STATUS = {
    FailureKind.AUTH: Status.BLOCKED_SECRET,
    FailureKind.FORBIDDEN: Status.BLOCKED_ACCESS,
    FailureKind.NOT_FOUND: Status.FAILED,
    FailureKind.SCHEMA: Status.FAILED,
    FailureKind.RIGHTS: Status.BLOCKED_RIGHTS,
}

HTTP_TO_KIND = {
    408: FailureKind.TRANSIENT_NETWORK,
    429: FailureKind.RATE_LIMIT,
    401: FailureKind.AUTH,
    403: FailureKind.FORBIDDEN,
    404: FailureKind.NOT_FOUND,
    500: FailureKind.SERVER_ERROR,
    502: FailureKind.SERVER_ERROR,
    503: FailureKind.SERVER_ERROR,
    504: FailureKind.SERVER_ERROR,
}


def classify_http(status_code: int) -> FailureKind:
    if status_code in HTTP_TO_KIND:
        return HTTP_TO_KIND[status_code]
    if 500 <= status_code < 600:
        return FailureKind.SERVER_ERROR
    if 400 <= status_code < 500:
        return FailureKind.FORBIDDEN
    return FailureKind.TRANSIENT_NETWORK


def backoff_seconds(attempt: int, kind: FailureKind, job_key: str,
                    base: float = 2.0, cap: float = 900.0,
                    retry_after: float | None = None) -> float | None:
    """
    Экспоненциальный backoff с детерминированным джиттером.

    Возвращает None, если повтор бессмысленен — это не то же самое, что 0.
    Джиттер берётся из хэша job_key, а не из random: одинаковые прогоны
    должны быть воспроизводимы, а разные джобы — не бить в API синхронно.
    """
    if kind not in RETRIABLE:
        return None
    if kind is FailureKind.RATE_LIMIT and retry_after is not None:
        return max(1.0, float(retry_after))
    delay = min(cap, base ** max(1, attempt))
    jitter = int(hashlib.sha256(job_key.encode()).hexdigest()[:4], 16) / 0xFFFF
    return round(delay * (0.75 + 0.5 * jitter), 2)


@dataclass
class QuotaPlan:
    """Как суточная квота API делится между сайтами."""

    source: str
    daily_budget: int
    per_site: dict[str, int]
    reserve: int
    note: str = ""

    def budget_for(self, site_id: str) -> int:
        return self.per_site.get(site_id, 0)


def allocate_quota(source: str, daily_budget: int, sites: Sequence[str],
                   priority_weights: dict[str, float] | None = None,
                   reserve_share: float = 0.1,
                   min_per_site: int = 1) -> QuotaPlan:
    """
    Делит квоту между сайтами пропорционально весам, оставляя резерв
    на внеплановые проверки (инциденты нельзя ставить в очередь за квотой).

    Каждый сайт получает как минимум min_per_site — иначе низкоприоритетные
    сайты никогда не собираются и тихо выпадают из портфеля.
    """
    if not sites:
        return QuotaPlan(source, daily_budget, {}, daily_budget, "нет сайтов")

    reserve = int(daily_budget * reserve_share)
    distributable = daily_budget - reserve

    floor_total = min_per_site * len(sites)
    if floor_total > distributable:
        # Квоты не хватает даже на минимум — честно урезаем минимум и говорим об этом.
        per_site_equal = max(0, distributable // len(sites))
        return QuotaPlan(
            source, daily_budget, {s: per_site_equal for s in sites}, reserve,
            note=(f"Квоты {daily_budget} не хватает на {len(sites)} сайтов при минимуме "
                  f"{min_per_site}: выдано по {per_site_equal}. Часть данных будет собрана позже."))

    weights = priority_weights or {}
    total_weight = sum(weights.get(s, 1.0) for s in sites)
    remaining = distributable - floor_total

    plan: dict[str, int] = {}
    for site in sites:
        w = weights.get(site, 1.0) / total_weight if total_weight else 1.0 / len(sites)
        plan[site] = min_per_site + int(remaining * w)

    spent = sum(plan.values())
    leftover = distributable - spent
    for site in sorted(sites, key=lambda s: -weights.get(s, 1.0))[:max(0, leftover)]:
        plan[site] += 1

    return QuotaPlan(source, daily_budget, plan, reserve,
                     note=f"резерв {reserve} на инциденты и переобход")


@dataclass
class JobOutcome:
    job_key: str
    site_id: str
    status: Status
    attempts: int
    detail: str = ""
    next_run_at: str | None = None


@dataclass
class BatchResult:
    """Итог прохода по портфелю. Успех части сайтов — нормальный исход."""

    succeeded: list[str] = field(default_factory=list)
    retrying: list[JobOutcome] = field(default_factory=list)
    quarantined: list[JobOutcome] = field(default_factory=list)
    skipped_no_quota: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return (len(self.succeeded) + len(self.retrying) + len(self.quarantined)
                + len(self.skipped_no_quota))

    @property
    def coverage(self) -> float:
        """Доля сайтов, по которым данные собраны. KPI надёжности ТЗ §15."""
        return round(len(self.succeeded) / self.total, 4) if self.total else 0.0

    def summary(self) -> dict[str, Any]:
        return {"total": self.total, "succeeded": len(self.succeeded),
                "retrying": len(self.retrying), "quarantined": len(self.quarantined),
                "skipped_no_quota": len(self.skipped_no_quota), "coverage": self.coverage}


def run_batch(sites: Sequence[str], plan: QuotaPlan,
              worker: Callable[[str], tuple[bool, FailureKind | None, str]],
              max_attempts: int = 4) -> BatchResult:
    """
    Прогон по портфелю. worker возвращает (успех, вид ошибки, деталь).

    Исключение внутри worker считается transient-сбоем ОДНОГО сайта и не
    прерывает батч: падение одного сайта не должно останавливать портфель.
    """
    result = BatchResult()

    for site in sites:
        if plan.budget_for(site) <= 0:
            result.skipped_no_quota.append(site)
            continue

        job_key = f"{plan.source}:{site}"
        attempts = 0
        while True:
            attempts += 1
            try:
                ok, kind, detail = worker(site)
            except Exception as exc:  # noqa: BLE001 — сбой сайта, а не батча
                ok, kind, detail = False, FailureKind.TRANSIENT_NETWORK, \
                    f"{type(exc).__name__}: {exc}"

            if ok:
                result.succeeded.append(site)
                break

            kind = kind or FailureKind.TRANSIENT_NETWORK
            if kind not in RETRIABLE:
                result.quarantined.append(JobOutcome(
                    job_key, site, TERMINAL_STATUS.get(kind, Status.FAILED), attempts,
                    f"{kind.value}: {detail} (повтор не имеет смысла)"))
                break

            if attempts >= max_attempts:
                result.quarantined.append(JobOutcome(
                    job_key, site, Status.FAILED, attempts,
                    f"{kind.value}: {detail} (исчерпаны {max_attempts} попытки)"))
                break

            delay = backoff_seconds(attempts, kind, job_key)
            result.retrying.append(JobOutcome(
                job_key, site, Status.RUNNING, attempts, f"{kind.value}: {detail}",
                next_run_at=(datetime.now(timezone.utc)
                             + timedelta(seconds=delay or 0)).isoformat()))
            break   # повтор выполняется следующим проходом планировщика, не блокируя батч

    return result
