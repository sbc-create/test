"""Суточная очередь: 500 новых или действительно обновлённых связок в сутки.

Единица счёта — пара «произведение + источник», у которой появилось или
изменилось значение. Всё остальное в цель не засчитывается: повторное
чтение неизменившейся записи, дубль, технический retry, запись с
ошибкой, спорное сопоставление и обновление одного лишь времени
проверки. Иначе счётчик выполняется мгновенно и перестаёт что-либо
значить — «500 проверок» и «500 новых оценок» это разные обещания.

Когда легитимных изменений меньше цели, недобор объявляется с причиной.
Система не должна ежедневно создавать пятьсот бессмысленных записей ради
цифры: после исчерпания backlog она переходит из режима наполнения в
режим актуализации, и это нормальное состояние, а не отказ.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import IntEnum
from typing import Any

from factory.unified_ratings.coverage import SLA_HOURS
from factory.unified_ratings.scale import ScoreState
from factory.unified_ratings.sources import SourceStatus, collectable_sources
from factory.unified_ratings.store import UnifiedStore

DAILY_TARGET = 500


class Priority(IntEnum):
    """Порядок очереди задан владельцем; меньшее число — раньше."""

    NEW_TITLE_NO_RATING = 1
    SITE_TITLE_NO_RATING = 2
    SINGLE_SOURCE_ONLY = 3
    POPULAR_STALE = 4
    ONGOING = 5
    RECENTLY_CHANGED = 6
    REST = 7


class Mode(str):
    #: есть backlog — наполняем
    FILL = "FILL"
    #: backlog исчерпан — поддерживаем актуальность
    REFRESH = "REFRESH"


@dataclass
class QueueItem:
    title_id: str
    source_key: str
    priority: Priority
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "title_id": self.title_id,
            "source_key": self.source_key,
            "priority": int(self.priority),
            "priority_name": self.priority.name,
            "reason": self.reason,
        }


@dataclass
class DailyReport:
    date: str
    target: int = DAILY_TARGET
    completed: int = 0
    unchanged_checked: int = 0
    pending_backlog: int = 0
    blocked_by_rate_limit: int = 0
    blocked_by_permission: int = 0
    blocked_by_secret: int = 0
    shortfall_reason: str = ""
    mode: str = Mode.FILL
    new_titles_first_rating: int = 0
    sent_to_review: int = 0
    coverage_before: float = 0.0
    coverage_after: float = 0.0
    exhausted_sources: list[str] = field(default_factory=list)
    blocked_sources: list[str] = field(default_factory=list)

    @property
    def met(self) -> bool:
        return self.completed >= self.target

    def estimated_days_remaining(self) -> int | str:
        """Прогноз по фактической дневной выработке, а не по цели.

        Делить backlog на 500 значило бы обещать срок, которого источники
        не подтверждали: если вчера легитимных изменений было двести, то
        и завтра их, скорее всего, будет около двухсот.
        """
        if self.pending_backlog <= 0:
            return 0
        if self.completed <= 0:
            return "UNKNOWN: за сутки не было ни одного зачтённого изменения"
        return -(-self.pending_backlog // self.completed)

    def as_dict(self) -> dict[str, Any]:
        return {
            "DAILY_TARGET": self.target,
            "DAILY_COMPLETED": self.completed,
            "DAILY_UNCHANGED_CHECKED": self.unchanged_checked,
            "DAILY_PENDING_BACKLOG": self.pending_backlog,
            "DAILY_BLOCKED_BY_RATE_LIMIT": self.blocked_by_rate_limit,
            "DAILY_BLOCKED_BY_PERMISSION": self.blocked_by_permission,
            "DAILY_BLOCKED_BY_SECRET": self.blocked_by_secret,
            "DAILY_SHORTFALL_REASON": self.shortfall_reason,
            "mode": self.mode,
            "target_met": self.met,
            "date": self.date,
            "new_titles_that_got_a_first_rating": self.new_titles_first_rating,
            "sent_to_review": self.sent_to_review,
            "coverage_percent_before": self.coverage_before,
            "coverage_percent_after": self.coverage_after,
            "exhausted_sources": self.exhausted_sources,
            "blocked_sources": self.blocked_sources,
            "estimated_days_to_backfill_complete": self.estimated_days_remaining(),
        }


def _parse(stamp: str) -> datetime | None:
    if not stamp:
        return None
    try:
        return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


class DailyQueue:
    def __init__(
        self,
        store: UnifiedStore,
        *,
        site_title_ids: set[str] | None = None,
        now: datetime | None = None,
    ) -> None:
        self.store = store
        self.site_title_ids = site_title_ids or set()
        self.now = now or datetime.now(timezone.utc)

    # ------------------------------------------------------------------

    def _eligible_pairs(self) -> dict[str, set[str]]:
        """Произведения, у которых есть идентификатор нужного источника."""
        from factory.unified_ratings.ingestion import ID_SPACE_BY_SOURCE

        out: dict[str, set[str]] = {}
        for source in collectable_sources():
            space = ID_SPACE_BY_SOURCE.get(source.source_key, "")
            if not space:
                continue
            out[source.source_key] = {
                r["title_id"]
                for r in self.store.query(
                    "SELECT title_id FROM unified_titles"
                    " WHERE json_extract(external_ids_json, ?) IS NOT NULL",
                    (f"$.{space}",),
                )
            }
        return out

    def build(self, *, limit: int = DAILY_TARGET) -> list[QueueItem]:
        eligible = self._eligible_pairs()
        have = {
            (r["title_id"], r["source_key"]): r
            for r in self.store.query(
                "SELECT title_id, source_key, validation_state, last_checked_at,"
                " unchanged_streak FROM unified_external_current"
            )
        }
        ambiguous = {
            (r["title_id"], r["source_key"])
            for r in self.store.query(
                "SELECT title_id, source_key FROM unified_source_links"
                " WHERE status IN ('pending','conflict','rejected')"
            )
        }
        ok_sources: dict[str, set[str]] = {}
        for (title_id, source_key), row in have.items():
            if row["validation_state"] == ScoreState.OK.value:
                ok_sources.setdefault(title_id, set()).add(source_key)
        tiers = {
            (r["title_id"], r["source_key"]): r["tier"]
            for r in self.store.query("SELECT title_id, source_key, tier FROM unified_schedule_state")
        }

        items: list[QueueItem] = []
        for source_key, title_ids in eligible.items():
            for title_id in title_ids:
                pair = (title_id, source_key)
                if pair in ambiguous:
                    continue
                current = have.get(pair)
                if current is None:
                    priority = (
                        Priority.SITE_TITLE_NO_RATING
                        if title_id in self.site_title_ids
                        else Priority.NEW_TITLE_NO_RATING
                    )
                    reason = "значения этого источника для произведения ещё нет"
                    items.append(QueueItem(title_id, source_key, priority, reason))
                    continue
                checked = _parse(current["last_checked_at"])
                tier = tiers.get(pair, "UNSCHEDULED")
                stale = checked is None or self.now - checked > timedelta(
                    hours=SLA_HOURS.get(tier, SLA_HOURS["UNSCHEDULED"])
                )
                if not stale:
                    continue
                if len(ok_sources.get(title_id, set())) <= 1:
                    priority, reason = Priority.SINGLE_SOURCE_ONLY, "у произведения один источник"
                elif tier == "ONGOING":
                    priority, reason = Priority.ONGOING, "выходящее произведение"
                elif int(current["unchanged_streak"]) == 0:
                    priority, reason = Priority.RECENTLY_CHANGED, "оценка недавно менялась"
                else:
                    priority, reason = Priority.REST, "срок проверки наступил"
                items.append(QueueItem(title_id, source_key, priority, reason))

        items.sort(key=lambda i: (int(i.priority), i.title_id, i.source_key))
        return items[:limit]

    # ------------------------------------------------------------------

    def backlog_size(self) -> int:
        """Сколько связок ещё ни разу не собрано. Это и есть backlog."""
        eligible = self._eligible_pairs()
        have = {
            (r["title_id"], r["source_key"])
            for r in self.store.query(
                "SELECT title_id, source_key FROM unified_external_current"
            )
        }
        ambiguous = {
            (r["title_id"], r["source_key"])
            for r in self.store.query(
                "SELECT title_id, source_key FROM unified_source_links"
                " WHERE status IN ('pending','conflict','rejected')"
            )
        }
        total = 0
        for source_key, title_ids in eligible.items():
            for title_id in title_ids:
                pair = (title_id, source_key)
                if pair not in have and pair not in ambiguous:
                    total += 1
        return total

    def completed_today(self, *, since: datetime | None = None) -> dict[str, int]:
        """Зачтённые изменения за сутки — по снимкам, а не по прогонам.

        Снимок создаётся только когда содержимое действительно изменилось,
        поэтому он и есть доказательство зачтённой работы. Обновление
        одного ``last_checked_at`` снимка не создаёт и в цель не идёт.
        """
        since = since or (self.now - timedelta(days=1))
        stamp = since.strftime("%Y-%m-%dT%H:%M:%SZ")
        rows = self.store.query(
            "SELECT title_id, source_key, prev_snapshot_id FROM unified_external_snapshots"
            " WHERE fetched_at >= ?",
            (stamp,),
        )
        pairs = {(r["title_id"], r["source_key"]) for r in rows}
        first_time = {r["title_id"] for r in rows if r["prev_snapshot_id"] is None}
        return {"completed": len(pairs), "titles_first_rating": len(first_time)}

    def report(self, *, coverage_before: float = 0.0, coverage_after: float = 0.0) -> DailyReport:
        done = self.completed_today()
        backlog = self.backlog_size()
        report = DailyReport(
            date=self.now.strftime("%Y-%m-%d"),
            completed=done["completed"],
            new_titles_first_rating=done["titles_first_rating"],
            pending_backlog=backlog,
            coverage_before=coverage_before,
            coverage_after=coverage_after,
            mode=Mode.FILL if backlog > 0 else Mode.REFRESH,
        )
        report.unchanged_checked = self.store.query_one(
            "SELECT COALESCE(SUM(unchanged),0) c FROM unified_import_runs WHERE started_at >= ?",
            ((self.now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),),
        )["c"]
        report.sent_to_review = self.store.count("unified_review_queue", "status='PENDING'")

        from factory.unified_ratings.sources import REGISTRY

        for key, source in REGISTRY.items():
            if source.status is SourceStatus.BLOCKED_SECRET:
                report.blocked_sources.append(f"{key}: ключ отсутствует")
                report.blocked_by_secret += 1
            elif source.status in (
                SourceStatus.BLOCKED_AUTHORIZATION,
                SourceStatus.BLOCKED_PAID,
                SourceStatus.BLOCKED_ACCESS,
            ):
                report.blocked_sources.append(f"{key}: {source.status.value}")
                report.blocked_by_permission += 1

        report.blocked_by_rate_limit = self.store.query_one(
            "SELECT COALESCE(SUM(rate_limited),0) c FROM unified_import_runs WHERE started_at >= ?",
            ((self.now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),),
        )["c"]

        if not report.met:
            if backlog == 0:
                report.shortfall_reason = (
                    "backlog исчерпан: новых связок нет, система перешла в режим "
                    "актуализации; создавать записи ради счётчика нельзя"
                )
            elif report.blocked_by_rate_limit:
                report.shortfall_reason = (
                    f"источники ограничили частоту {report.blocked_by_rate_limit} раз; "
                    "ускорять сбор в обход лимитов запрещено"
                )
            elif report.blocked_by_secret:
                report.shortfall_reason = (
                    "часть источников недоступна без ключа (см. blocked_sources); "
                    "остальные собраны в разрешённом темпе"
                )
            else:
                report.shortfall_reason = (
                    f"за сутки легитимно изменилось {report.completed} связок при backlog "
                    f"{backlog}; недостающее — не изменившиеся у источника значения"
                )
        return report
