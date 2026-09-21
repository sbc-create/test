"""Адаптивное расписание обновления внешних оценок.

Полного обхода всех источников сразу не бывает: каждый источник идёт по
своей очереди со своим лимитом. Одновременный обход — это способ
одновременно попасть во все rate limits и потерять сутки на всех
источниках вместо одного.

Интервал подстраивается под поведение конкретной пары (тайтл, источник):
неизменившееся значение отодвигает следующую проверку, изменившееся —
приближает, отказ отодвигает сильнее и считается отдельно. Границы
интервала заданы тиром и за них подстройка не выходит, иначе редкий
архивный тайтл с дёргающейся оценкой утащил бы бюджет запросов у
онгоингов.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from factory.unified_ratings.store import UnifiedStore
from factory.unified_ratings.titles import CanonicalTitle, utc_now


class Tier(str, Enum):
    ONGOING = "ONGOING"
    RECENT_FINISHED = "RECENT_FINISHED"
    ARCHIVE = "ARCHIVE"
    RETRY = "RETRY"


@dataclass(frozen=True)
class TierPolicy:
    base_hours: int
    min_hours: int
    max_hours: int


#: Стартовый режим, предложенный владельцем, с границами подстройки.
TIER_POLICY: dict[Tier, TierPolicy] = {
    Tier.ONGOING: TierPolicy(base_hours=24, min_hours=12, max_hours=72),
    Tier.RECENT_FINISHED: TierPolicy(base_hours=24 * 7, min_hours=48, max_hours=24 * 21),
    Tier.ARCHIVE: TierPolicy(base_hours=24 * 30, min_hours=24 * 14, max_hours=24 * 90),
    Tier.RETRY: TierPolicy(base_hours=6, min_hours=1, max_hours=24 * 7),
}

#: Сколько неудач подряд прежде, чем пара уходит из очереди повторов.
MAX_FAILURE_STREAK = 5

#: Во сколько раз растёт интервал за каждую серию неизменившихся проверок.
UNCHANGED_BACKOFF = 1.5
#: Во сколько раз сокращается интервал при изменении значения.
CHANGED_SPEEDUP = 0.5


def classify(title: CanonicalTitle, *, now: datetime | None = None, is_ongoing: bool = False) -> Tier:
    """Тир тайтла. Год выпуска — то немногое, что известно про все тайтлы."""
    now = now or datetime.now(timezone.utc)
    if is_ongoing:
        return Tier.ONGOING
    year = title.release_year
    if year is None:
        return Tier.ARCHIVE
    if year >= now.year:
        return Tier.ONGOING
    if year >= now.year - 1:
        return Tier.RECENT_FINISHED
    return Tier.ARCHIVE


def _parse(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


class Scheduler:
    def __init__(self, store: UnifiedStore) -> None:
        self.store = store

    # ------------------------------------------------------------------

    def enroll(
        self,
        *,
        title: CanonicalTitle,
        source_key: str,
        tier: Tier | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        now = now or datetime.now(timezone.utc)
        tier = tier or classify(title, now=now)
        policy = TIER_POLICY[tier]
        due = now + timedelta(hours=policy.base_hours)
        with self.store.write_tx() as conn:
            conn.execute(
                """INSERT INTO unified_schedule_state(
                       title_id, source_key, tier, interval_hours, next_due_at)
                   VALUES (?,?,?,?,?)
                   ON CONFLICT(title_id, source_key) DO UPDATE SET
                       tier=excluded.tier""",
                (title.title_id, source_key, tier.value, policy.base_hours, _iso(due)),
            )
        return {"title_id": title.title_id, "source_key": source_key, "tier": tier.value,
                "interval_hours": policy.base_hours, "next_due_at": _iso(due)}

    # ------------------------------------------------------------------

    def due(self, *, source_key: str, limit: int, now: datetime | None = None) -> list[str]:
        """Тайтлы, которым пора. Приостановленные не возвращаются вовсе."""
        now = now or datetime.now(timezone.utc)
        stamp = _iso(now)
        rows = self.store.query(
            """SELECT title_id FROM unified_schedule_state
               WHERE source_key=? AND next_due_at <= ?
                 AND (paused_until = '' OR paused_until <= ?)
                 AND failure_streak < ?
               ORDER BY next_due_at LIMIT ?""",
            (source_key, stamp, stamp, MAX_FAILURE_STREAK, limit),
        )
        return [r["title_id"] for r in rows]

    def observe(
        self,
        *,
        title_id: str,
        source_key: str,
        outcome: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Учесть исход проверки и сдвинуть следующую.

        ``outcome``: ``changed`` | ``unchanged`` | ``failed``.
        """
        now = now or datetime.now(timezone.utc)
        row = self.store.query_one(
            "SELECT * FROM unified_schedule_state WHERE title_id=? AND source_key=?",
            (title_id, source_key),
        )
        if row is None:
            raise KeyError(f"пара не в расписании: {title_id}/{source_key}")

        tier = Tier(row["tier"])
        policy = TIER_POLICY[tier]
        interval = int(row["interval_hours"])
        unchanged_streak = int(row["unchanged_streak"])
        failure_streak = int(row["failure_streak"])
        last_changed = row["last_changed_at"]

        if outcome == "changed":
            interval = max(policy.min_hours, int(interval * CHANGED_SPEEDUP))
            unchanged_streak = 0
            failure_streak = 0
            last_changed = _iso(now)
        elif outcome == "unchanged":
            unchanged_streak += 1
            failure_streak = 0
            interval = min(policy.max_hours, int(interval * UNCHANGED_BACKOFF) or policy.min_hours)
        elif outcome == "failed":
            failure_streak += 1
            # Отказ отодвигает сильнее удачной проверки: источник, который
            # не отвечает, не станет отвечать чаще оттого, что мы спросим
            # его раньше.
            interval = min(policy.max_hours, max(policy.min_hours, interval * 2))
        else:
            raise ValueError(f"неизвестный исход: {outcome}")

        next_due = now + timedelta(hours=interval)
        with self.store.write_tx() as conn:
            conn.execute(
                """UPDATE unified_schedule_state SET
                       interval_hours=?, next_due_at=?, last_checked_at=?, last_changed_at=?,
                       unchanged_streak=?, failure_streak=?
                   WHERE title_id=? AND source_key=?""",
                (
                    interval, _iso(next_due), _iso(now), last_changed,
                    unchanged_streak, failure_streak, title_id, source_key,
                ),
            )
        return {
            "title_id": title_id,
            "source_key": source_key,
            "tier": tier.value,
            "interval_hours": interval,
            "next_due_at": _iso(next_due),
            "unchanged_streak": unchanged_streak,
            "failure_streak": failure_streak,
            "exhausted": failure_streak >= MAX_FAILURE_STREAK,
        }

    # ------------------------------------------------------------------

    def pause_source(
        self, *, source_key: str, until: datetime, reason: str
    ) -> int:
        """Приостановить источник до разрешённого времени (rate limit)."""
        with self.store.write_tx() as conn:
            cursor = conn.execute(
                "UPDATE unified_schedule_state SET paused_until=?, pause_reason=? WHERE source_key=?",
                (_iso(until), reason, source_key),
            )
        return cursor.rowcount

    def resume_source(self, *, source_key: str) -> int:
        with self.store.write_tx() as conn:
            cursor = conn.execute(
                "UPDATE unified_schedule_state SET paused_until='', pause_reason='' WHERE source_key=?",
                (source_key,),
            )
        return cursor.rowcount

    # ------------------------------------------------------------------

    def plan(self, *, now: datetime | None = None) -> dict[str, Any]:
        """Сводка расписания. Источники идут по очереди, не одновременно."""
        now = now or datetime.now(timezone.utc)
        rows = self.store.query(
            """SELECT source_key, tier, COUNT(*) AS n, MIN(next_due_at) AS soonest,
                      SUM(CASE WHEN paused_until <> '' THEN 1 ELSE 0 END) AS paused
               FROM unified_schedule_state GROUP BY source_key, tier ORDER BY source_key, tier"""
        )
        by_source: dict[str, Any] = {}
        for row in rows:
            entry = by_source.setdefault(row["source_key"], {"tiers": {}, "total": 0, "paused": 0})
            entry["tiers"][row["tier"]] = {
                "titles": int(row["n"]),
                "soonest_due": row["soonest"],
                "interval_hours": TIER_POLICY[Tier(row["tier"])].base_hours,
            }
            entry["total"] += int(row["n"])
            entry["paused"] += int(row["paused"] or 0)
        return {
            "generated_at": utc_now(),
            "concurrent_full_sweep": False,
            "sources": by_source,
            "starting_intervals": {
                "ONGOING": "раз в 24 часа",
                "RECENT_FINISHED": "раз в 7 дней",
                "ARCHIVE": "раз в 30 дней",
                "RETRY": "ограниченные повторы, не более 5 подряд",
            },
        }


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
