"""Experiment lifecycle: propose, canary, observe, decide, keep or roll back.

The decision rule is deliberately conservative. An experiment is kept only when
the data is mature enough to distinguish a real effect from noise; anything
else is rolled back. "No verdict yet" and "no effect" both lead to *not*
keeping the change, because leaving an unproven edit in place accumulates
unexplained drift across a portfolio.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum

from seo_operator.audit import Change, new_id, utcnow


class Phase(str, Enum):
    PROPOSED = "proposed"
    DRY_RUN = "dry_run"
    CANARY = "canary"
    OBSERVING = "observing"
    KEPT = "kept"
    ROLLED_BACK = "rolled_back"
    ABORTED = "aborted"


class Verdict(str, Enum):
    KEEP = "keep"
    ROLLBACK = "rollback"
    CONTINUE = "continue"
    INSUFFICIENT_DATA = "insufficient_data"


# Canary limits. A change may reach at most this share of a site's pages, and
# at most this many sites, before it has earned a verdict.
MAX_CANARY_PAGE_SHARE = 0.10
MAX_CANARY_SITES = 1
MIN_OBSERVATION_DAYS = 14
MIN_IMPRESSIONS_FOR_VERDICT = 1000
# Effect thresholds, expressed as relative change against the control.
KEEP_THRESHOLD = 0.05  # +5% or better on the primary metric
ROLLBACK_THRESHOLD = -0.03  # -3% or worse triggers an immediate revert


class CanaryScopeError(ValueError):
    """Raised when a proposed rollout exceeds the canary limits."""


@dataclass
class Observation:
    """One measurement window for an experiment."""

    days_elapsed: int
    impressions: int
    primary_metric_delta: float  # relative, e.g. 0.08 == +8%
    guardrail_breached: bool = False
    note: str = ""


@dataclass
class Experiment:
    hypothesis: str
    site_id: str
    primary_metric: str
    experiment_id: str = field(default_factory=lambda: new_id("exp"))
    phase: Phase = Phase.PROPOSED
    created_at: str = field(default_factory=utcnow)
    changes: list[Change] = field(default_factory=list)
    scope_pages: int = 0
    site_total_pages: int = 0
    applicability: str = ""
    history: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.hypothesis:
            raise ValueError("эксперимент без гипотезы не измерим")
        if not self.primary_metric:
            raise ValueError("не задана первичная метрика")

    @property
    def page_share(self) -> float:
        if self.site_total_pages <= 0:
            return 0.0
        return self.scope_pages / self.site_total_pages

    def validate_canary_scope(self, sites_touched: int = 1) -> None:
        if sites_touched > MAX_CANARY_SITES:
            raise CanaryScopeError(
                f"canary затрагивает {sites_touched} сайтов, разрешён {MAX_CANARY_SITES}"
            )
        if self.page_share > MAX_CANARY_PAGE_SHARE:
            raise CanaryScopeError(
                f"canary покрывает {self.page_share:.1%} страниц, "
                f"максимум {MAX_CANARY_PAGE_SHARE:.0%}"
            )

    def record(self, event: str, detail: str = "") -> None:
        self.history.append({"at": utcnow(), "event": event, "detail": detail})

    def rollback_payloads(self) -> list[dict]:
        """Undo instructions for every change, newest first."""
        return [c.rollback_payload for c in reversed(self.changes)]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["phase"] = self.phase.value
        data["changes"] = [c.to_record() for c in self.changes]
        data["page_share"] = round(self.page_share, 4)
        return data


def decide(observation: Observation) -> tuple[Verdict, str]:
    """Decide the fate of an experiment from one observation window."""
    if observation.guardrail_breached:
        return Verdict.ROLLBACK, "нарушен guardrail — немедленный откат"

    if observation.primary_metric_delta <= ROLLBACK_THRESHOLD:
        return (
            Verdict.ROLLBACK,
            f"ухудшение {observation.primary_metric_delta:.1%} "
            f"хуже порога {ROLLBACK_THRESHOLD:.0%}",
        )

    if observation.days_elapsed < MIN_OBSERVATION_DAYS:
        return (
            Verdict.CONTINUE,
            f"прошло {observation.days_elapsed} из {MIN_OBSERVATION_DAYS} дней наблюдения",
        )

    if observation.impressions < MIN_IMPRESSIONS_FOR_VERDICT:
        return (
            Verdict.INSUFFICIENT_DATA,
            f"{observation.impressions} показов < {MIN_IMPRESSIONS_FOR_VERDICT} — "
            "выборка не позволяет отличить эффект от шума",
        )

    if observation.primary_metric_delta >= KEEP_THRESHOLD:
        return (
            Verdict.KEEP,
            f"улучшение {observation.primary_metric_delta:.1%} "
            f"выше порога {KEEP_THRESHOLD:.0%} при достаточной выборке",
        )

    return (
        Verdict.ROLLBACK,
        f"эффект {observation.primary_metric_delta:.1%} не достиг порога "
        f"{KEEP_THRESHOLD:.0%} — недоказанное изменение не остаётся",
    )
