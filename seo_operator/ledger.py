"""
Action Ledger — журнал всех действий и гипотез (ТЗ §3.1, §4).

Без этого журнала анализ «что выросло после чего» невозможен: изменение,
которого нет в журнале, будет приписано сезонности или алгоритму. Поэтому
запись создаётся ДО выполнения действия и закрывается результатом после.

Журнал неизменяем в части уже записанного: правки идут новыми записями.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable, Sequence

from .statuses import Confidence, ExperimentOutcome, Status

SCHEMA = """
CREATE TABLE IF NOT EXISTS actions (
    action_id TEXT PRIMARY KEY,
    site_id TEXT NOT NULL,
    urls TEXT NOT NULL,
    cluster TEXT,
    action_type TEXT NOT NULL,
    hypothesis TEXT NOT NULL,
    expected_effect TEXT NOT NULL,
    baseline TEXT NOT NULL,
    success_criterion TEXT NOT NULL,
    failure_criterion TEXT NOT NULL,
    stop_criterion TEXT NOT NULL,
    risk TEXT NOT NULL,
    rollback_plan TEXT NOT NULL,
    control_group TEXT,
    executor TEXT NOT NULL,
    commit_sha TEXT,
    release_id TEXT,
    planned_at TEXT NOT NULL,
    executed_at TEXT,
    evaluate_after TEXT NOT NULL,
    status TEXT NOT NULL,
    outcome TEXT,
    outcome_confidence TEXT,
    outcome_detail TEXT,
    outcome_recorded_at TEXT,
    requires_manual_approval INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_actions_site ON actions(site_id);
CREATE INDEX IF NOT EXISTS idx_actions_eval ON actions(evaluate_after, status);
CREATE INDEX IF NOT EXISTS idx_actions_exec ON actions(executed_at);

-- Записанное действие не переписывается задним числом: правка = новая запись.
CREATE TABLE IF NOT EXISTS action_amendments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_id TEXT NOT NULL REFERENCES actions(action_id),
    field TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    reason TEXT NOT NULL,
    amended_at TEXT NOT NULL
);
"""

# Поля, которые нельзя менять после исполнения: иначе гипотеза подгоняется под результат.
FROZEN_AFTER_EXECUTION = frozenset({
    "hypothesis", "expected_effect", "baseline", "success_criterion",
    "failure_criterion", "stop_criterion", "control_group",
})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Action:
    action_id: str
    site_id: str
    urls: list[str]
    action_type: str
    hypothesis: str
    expected_effect: str
    baseline: dict[str, Any]
    success_criterion: str
    failure_criterion: str
    stop_criterion: str
    risk: str
    rollback_plan: str
    executor: str
    evaluate_after: str
    cluster: str | None = None
    control_group: list[str] = field(default_factory=list)
    commit_sha: str | None = None
    release_id: str | None = None
    planned_at: str = field(default_factory=_now)
    executed_at: str | None = None
    status: str = Status.READY.value
    outcome: str | None = None
    outcome_confidence: str | None = None
    outcome_detail: str | None = None
    requires_manual_approval: bool = False


class IncompleteAction(ValueError):
    """Действие без гипотезы, baseline или критериев в журнал не попадает."""


class LedgerImmutable(ValueError):
    """Попытка переписать исполненное действие."""


def new_action_id(site_id: str, seq: int, today: date | None = None) -> str:
    today = today or date.today()
    return f"ACT-{today:%Y%m%d}-{site_id}-{seq:04d}"


class ActionLedger:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    # ---------------- запись ----------------

    def next_sequence(self, site_id: str, today: date | None = None) -> int:
        today = today or date.today()
        prefix = f"ACT-{today:%Y%m%d}-{site_id}-"
        row = self._conn.execute("SELECT COUNT(*) c FROM actions WHERE action_id LIKE ?",
                                 (prefix + "%",)).fetchone()
        return row["c"] + 1

    @staticmethod
    def validate(action: Action) -> None:
        required = {
            "hypothesis": action.hypothesis, "expected_effect": action.expected_effect,
            "success_criterion": action.success_criterion,
            "failure_criterion": action.failure_criterion,
            "stop_criterion": action.stop_criterion, "risk": action.risk,
            "rollback_plan": action.rollback_plan, "evaluate_after": action.evaluate_after,
        }
        missing = [k for k, v in required.items() if not (v or "").strip()]
        if missing:
            raise IncompleteAction(
                f"{action.action_id}: не заданы обязательные поля {missing} — "
                "действие без критериев оценить нельзя, поэтому оно не записывается.")
        if not action.baseline:
            raise IncompleteAction(f"{action.action_id}: пустой baseline — сравнивать будет не с чем.")
        if not action.urls:
            raise IncompleteAction(f"{action.action_id}: не указан ни один URL.")
        try:
            date.fromisoformat(action.evaluate_after)
        except ValueError as exc:
            raise IncompleteAction(f"{action.action_id}: evaluate_after не дата: {exc}") from exc

    def record(self, action: Action) -> Action:
        """Запись планируемого действия. Вызывается ДО исполнения."""
        self.validate(action)
        self._conn.execute(
            """INSERT INTO actions (action_id, site_id, urls, cluster, action_type, hypothesis,
                expected_effect, baseline, success_criterion, failure_criterion, stop_criterion,
                risk, rollback_plan, control_group, executor, commit_sha, release_id,
                planned_at, executed_at, evaluate_after, status, requires_manual_approval)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (action.action_id, action.site_id, json.dumps(action.urls, ensure_ascii=False),
             action.cluster, action.action_type, action.hypothesis, action.expected_effect,
             json.dumps(action.baseline, ensure_ascii=False), action.success_criterion,
             action.failure_criterion, action.stop_criterion, action.risk, action.rollback_plan,
             json.dumps(action.control_group, ensure_ascii=False), action.executor,
             action.commit_sha, action.release_id, action.planned_at, action.executed_at,
             action.evaluate_after, action.status, int(action.requires_manual_approval)))
        self._conn.commit()
        return action

    def mark_executed(self, action_id: str, commit_sha: str | None,
                      release_id: str | None, executed_at: str | None = None) -> None:
        """Каждое изменение связывается с commit/release ID (ТЗ §15)."""
        self._conn.execute(
            "UPDATE actions SET executed_at=?, commit_sha=?, release_id=?, status=? "
            "WHERE action_id=?",
            (executed_at or _now(), commit_sha, release_id, Status.RUNNING.value, action_id))
        self._conn.commit()

    def amend(self, action_id: str, field_name: str, new_value: str, reason: str) -> None:
        """Правка записи. После исполнения ключевые поля заморожены."""
        row = self.get(action_id)
        if row is None:
            raise KeyError(action_id)
        if row["executed_at"] and field_name in FROZEN_AFTER_EXECUTION:
            raise LedgerImmutable(
                f"{action_id}: поле '{field_name}' заморожено после исполнения — "
                "иначе гипотезу можно подогнать под полученный результат.")
        if field_name not in {c[1] for c in self._conn.execute("PRAGMA table_info(actions)")}:
            raise ValueError(f"неизвестное поле: {field_name}")
        old = row[field_name]
        self._conn.execute(
            "INSERT INTO action_amendments (action_id, field, old_value, new_value, reason, amended_at)"
            " VALUES (?,?,?,?,?,?)",
            (action_id, field_name, str(old), new_value, reason, _now()))
        self._conn.execute(f"UPDATE actions SET {field_name}=? WHERE action_id=?",
                           (new_value, action_id))
        self._conn.commit()

    def close(self, action_id: str, outcome: ExperimentOutcome,
              confidence: Confidence, detail: str) -> None:
        """Исход фиксируется навсегда. Неудачи не скрываются (ТЗ §5, шаг 7)."""
        status = Status.ROLLED_BACK.value if outcome is ExperimentOutcome.ROLLED_BACK \
            else Status.READY.value
        self._conn.execute(
            "UPDATE actions SET outcome=?, outcome_confidence=?, outcome_detail=?, "
            "outcome_recorded_at=?, status=? WHERE action_id=?",
            (outcome.value, confidence.value, detail, _now(), status, action_id))
        self._conn.commit()

    # ---------------- чтение ----------------

    def get(self, action_id: str) -> sqlite3.Row | None:
        return self._conn.execute("SELECT * FROM actions WHERE action_id=?", (action_id,)).fetchone()

    def due_for_evaluation(self, today: date | None = None) -> list[sqlite3.Row]:
        today = today or date.today()
        return list(self._conn.execute(
            "SELECT * FROM actions WHERE outcome IS NULL AND executed_at IS NOT NULL "
            "AND evaluate_after <= ? ORDER BY evaluate_after", (today.isoformat(),)))

    def actions_in_window(self, site_id: str, start: date, end: date) -> list[sqlite3.Row]:
        """
        Действия, предшествовавшие изменению метрики. Это вход для анализа §5 шаг 3:
        без него любая корреляция остаётся беспризорной.
        """
        return list(self._conn.execute(
            "SELECT * FROM actions WHERE site_id=? AND executed_at IS NOT NULL "
            "AND date(executed_at) BETWEEN ? AND ? ORDER BY executed_at",
            (site_id, start.isoformat(), end.isoformat())))

    def outcomes_summary(self) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT outcome, COUNT(*) c FROM actions WHERE outcome IS NOT NULL GROUP BY outcome")
        summary = {o.value: 0 for o in ExperimentOutcome}
        summary["OPEN"] = self._conn.execute(
            "SELECT COUNT(*) c FROM actions WHERE outcome IS NULL").fetchone()["c"]
        for row in rows:
            summary[row["outcome"]] = row["c"]
        return summary

    def measurable_share(self) -> float | None:
        """
        Доля экспериментов с измеримым результатом (KPI оператора, ТЗ §15).
        INCONCLUSIVE и INVALIDATED измеримыми не считаются.
        """
        closed = self._conn.execute(
            "SELECT COUNT(*) c FROM actions WHERE outcome IS NOT NULL").fetchone()["c"]
        if not closed:
            return None
        measurable = self._conn.execute(
            "SELECT COUNT(*) c FROM actions WHERE outcome IN ('WIN','LOSS','NEUTRAL')").fetchone()["c"]
        return round(measurable / closed, 3)

    def amendments(self, action_id: str) -> list[sqlite3.Row]:
        return list(self._conn.execute(
            "SELECT * FROM action_amendments WHERE action_id=? ORDER BY id", (action_id,)))
