"""Degraded-mode controller for Qwen postmod SLA (goal §14)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SlaConfig:
    target_latency_sec: int = 120
    degraded_threshold_sec: int = 300
    critical_oldest_sec: int = 600
    queue_depth_degraded: int = 50
    schema_mismatch_rate_degraded: float = 0.25


@dataclass
class DegradedController:
    sla: SlaConfig = field(default_factory=SlaConfig)
    circuit_open: bool = False
    stop_worker: bool = False
    _schema_mismatch: int = 0
    _total_decisions: int = 0
    _provider_errors: int = 0

    def record_success(self) -> None:
        self._total_decisions += 1

    def record_schema_mismatch(self) -> None:
        self._schema_mismatch += 1
        self._total_decisions += 1

    def record_provider_error(self) -> None:
        self._provider_errors += 1

    @property
    def schema_mismatch_rate(self) -> float:
        if self._total_decisions <= 0:
            return 0.0
        return self._schema_mismatch / float(self._total_decisions)

    def should_accept_as_degraded(
        self,
        queue_depth: int,
        oldest_age: float,
        circuit_open: bool | None = None,
        schema_mismatch_rate: float | None = None,
    ) -> bool:
        """When True, new comments must go to PENDING_MODERATION_DEGRADED (not public)."""
        open_circuit = self.circuit_open if circuit_open is None else circuit_open
        mismatch = (
            self.schema_mismatch_rate
            if schema_mismatch_rate is None
            else schema_mismatch_rate
        )
        if open_circuit:
            return True
        if oldest_age >= self.sla.critical_oldest_sec:
            return True
        if oldest_age >= self.sla.degraded_threshold_sec:
            return True
        if queue_depth >= self.sla.queue_depth_degraded:
            return True
        if mismatch >= self.sla.schema_mismatch_rate_degraded and self._total_decisions >= 4:
            return True
        return False

    def initial_status_for_new_comment(
        self,
        *,
        queue_depth: int = 0,
        oldest_age: float = 0.0,
    ) -> str:
        from factory.community.comments import states

        if self.should_accept_as_degraded(queue_depth, oldest_age):
            return states.PENDING_MODERATION_DEGRADED
        return states.PUBLISHED_UNREVIEWED

    def snapshot(self) -> dict[str, Any]:
        return {
            "sla": {
                "target_latency_sec": self.sla.target_latency_sec,
                "degraded_threshold_sec": self.sla.degraded_threshold_sec,
                "critical_oldest_sec": self.sla.critical_oldest_sec,
                "queue_depth_degraded": self.sla.queue_depth_degraded,
            },
            "circuit_open": self.circuit_open,
            "stop_worker": self.stop_worker,
            "schema_mismatch_rate": self.schema_mismatch_rate,
            "provider_errors": self._provider_errors,
        }
