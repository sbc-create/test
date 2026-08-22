"""Data quality gate.

The gate exists to stop one specific failure: a source that is silently absent
becoming a row of zeros in a management report. Zero clicks and "we could not
measure clicks" look identical in a chart and mean opposite things, so the gate
refuses to emit a metric it cannot source.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from seo_operator.datasources.base import Availability


class GateResult(str, Enum):
    PASS = "pass"
    DEGRADED = "degraded"
    FAIL = "fail"


@dataclass
class QualityReport:
    result: GateResult
    available: list[str] = field(default_factory=list)
    unavailable: dict[str, str] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)

    @property
    def can_publish_metrics(self) -> bool:
        """Only a PASS or DEGRADED gate may emit metrics, and only for the
        sources listed in ``available``."""
        return self.result is not GateResult.FAIL

    def to_dict(self) -> dict:
        return {
            "result": self.result.value,
            "available": sorted(self.available),
            "unavailable": dict(sorted(self.unavailable.items())),
            "reasons": list(self.reasons),
        }


# Sources without which a run cannot claim to measure search performance.
CRITICAL_SOURCES = frozenset({"google_search_console", "yandex_webmaster"})


def evaluate(probes: dict[str, Availability]) -> QualityReport:
    available = [name for name, a in probes.items() if a.usable]
    unavailable = {name: a.detail for name, a in probes.items() if not a.usable}

    reasons: list[str] = []
    if not available:
        reasons.append("ни один источник данных не доступен — метрики не могут быть измерены")
        return QualityReport(GateResult.FAIL, available, unavailable, reasons)

    missing_critical = sorted(CRITICAL_SOURCES - set(available))
    if len(missing_critical) == len(CRITICAL_SOURCES):
        reasons.append(
            "недоступны все источники поисковой статистики "
            f"({', '.join(missing_critical)}) — показы, клики, CTR и позиции измерить нечем"
        )
        return QualityReport(GateResult.FAIL, available, unavailable, reasons)

    if missing_critical:
        reasons.append(f"частично недоступны: {', '.join(missing_critical)}")
        return QualityReport(GateResult.DEGRADED, available, unavailable, reasons)

    if unavailable:
        reasons.append(f"вспомогательные источники недоступны: {', '.join(sorted(unavailable))}")
        return QualityReport(GateResult.DEGRADED, available, unavailable, reasons)

    return QualityReport(GateResult.PASS, available, unavailable, reasons)


class MetricRedactionError(RuntimeError):
    """Raised when code tries to publish a metric with no usable source."""


def guard_metric(name: str, value, report: QualityReport, source: str):
    """Return ``value`` only if ``source`` was actually available.

    Otherwise return the explicit marker ``None`` together with a reason. This
    is what keeps "не измерено" distinct from "ноль" all the way into the report.
    """
    if source in report.available:
        return value
    raise MetricRedactionError(
        f"метрика {name!r} запрошена, но источник {source!r} недоступен: "
        f"{report.unavailable.get(source, 'причина не указана')}"
    )


def safe_metric(name: str, value, report: QualityReport, source: str):
    """Non-raising variant: returns ``('не измерено', reason)`` instead."""
    try:
        return {"value": guard_metric(name, value, report, source), "measured": True}
    except MetricRedactionError as exc:
        return {"value": None, "measured": False, "reason": str(exc)}
