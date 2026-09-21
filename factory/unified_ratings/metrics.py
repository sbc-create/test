"""Метрики единого модуля оценок.

Пустой счётчик и отсутствие измерения — разные записи. ``record(0)``
означает «считали, вышло ноль»; ``unmeasured(reason)`` означает «не
считали» и требует причины. Разница не косметическая: график, на котором
недоступный источник показывает ноль ошибок, выглядит как здоровый
источник, и именно так пропускают отказ.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from factory.unified_ratings.store import UnifiedStore

MEASURED = "MEASURED"
UNMEASURED = "UNMEASURED"

#: Полный список метрик модуля. Отсутствие метрики в отчёте — тоже факт,
#: поэтому список объявлен здесь, а не собирается из того, что записалось.
METRIC_NAMES: tuple[str, ...] = (
    "source_requests",
    "source_errors",
    "source_rate_limits",
    "imported",
    "updated",
    "unchanged",
    "rejected",
    "pending_review",
    "match_confidence",
    "ingestion_latency_ms",
    "checkpoint_age_seconds",
    "votes_created",
    "votes_updated",
    "votes_retracted",
    "duplicate_requests",
    "rate_limit_violations",
    "aggregate_rebuild_mismatches",
    "db_errors",
    "api_latency_p50_ms",
    "api_latency_p95_ms",
    "widget_rendered",
    "write_success",
    "write_failure",
)


@dataclass(frozen=True)
class MetricSample:
    metric: str
    state: str
    value: float | None
    labels: dict[str, Any]
    reason: str
    observed_at: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "state": self.state,
            "value": self.value,
            "labels": self.labels,
            "reason": self.reason,
            "observed_at": self.observed_at,
        }


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class MetricsRecorder:
    def __init__(self, store: UnifiedStore, *, run_id: str = "") -> None:
        self.store = store
        self.run_id = run_id

    def record(
        self, metric: str, value: float, *, labels: dict[str, Any] | None = None
    ) -> MetricSample:
        return self._write(metric, MEASURED, float(value), labels or {}, "")

    def unmeasured(
        self, metric: str, reason: str, *, labels: dict[str, Any] | None = None
    ) -> MetricSample:
        if not reason:
            raise ValueError("неизмеренная метрика обязана назвать причину")
        return self._write(metric, UNMEASURED, None, labels or {}, reason)

    def _write(
        self, metric: str, state: str, value: float | None, labels: dict[str, Any], reason: str
    ) -> MetricSample:
        if metric not in METRIC_NAMES:
            raise ValueError(f"метрика не объявлена в METRIC_NAMES: {metric}")
        sample = MetricSample(metric, state, value, labels, reason, _now())
        with self.store.write_tx() as conn:
            conn.execute(
                """INSERT INTO unified_metrics(
                       metric, labels_json, state, value, reason, observed_at, run_id)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    metric,
                    json.dumps(labels, ensure_ascii=False, sort_keys=True),
                    state,
                    value,
                    reason,
                    sample.observed_at,
                    self.run_id,
                ),
            )
        return sample

    # ------------------------------------------------------------------

    def snapshot(self, *, run_id: str | None = None) -> dict[str, Any]:
        """Сводка по всем объявленным метрикам.

        Метрика, которую никто не записал, попадает в отчёт как
        UNMEASURED с причиной, а не как ноль.
        """
        where = "WHERE run_id = ?" if run_id else ""
        params = (run_id,) if run_id else ()
        rows = self.store.query(
            f"""SELECT metric, state, value, reason, observed_at FROM unified_metrics
                {where} ORDER BY metric, metric_id""",
            params,
        )
        collected: dict[str, list[Any]] = {}
        for row in rows:
            collected.setdefault(row["metric"], []).append(row)

        out: dict[str, Any] = {}
        for name in METRIC_NAMES:
            samples = collected.get(name)
            if not samples:
                out[name] = {
                    "state": UNMEASURED,
                    "value": None,
                    "reason": "метрика не записывалась в этом прогоне",
                }
                continue
            measured = [s for s in samples if s["state"] == MEASURED]
            if not measured:
                out[name] = {
                    "state": UNMEASURED,
                    "value": None,
                    "reason": samples[-1]["reason"] or "измерение не выполнялось",
                }
                continue
            out[name] = {
                "state": MEASURED,
                "value": sum(float(s["value"] or 0.0) for s in measured),
                "samples": len(measured),
                "last_observed_at": measured[-1]["observed_at"],
            }
        return out
