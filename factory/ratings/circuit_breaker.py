"""Source circuit breaker: 401/403/schema drift open the circuit."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


@dataclass
class CircuitBreaker:
    threshold: int = 5
    cooldown_sec: float = 300.0
    clock: Any = time.monotonic
    failures: int = 0
    opened_at: float = 0.0
    reason: str = ""
    hard_open: bool = False  # 401/403/schema drift — не закрывается по cooldown без reset

    def record_success(self) -> None:
        if not self.hard_open:
            self.failures = 0
            self.opened_at = 0.0
            self.reason = ""

    def record_failure(self, reason: str = "", *, hard: bool = False) -> None:
        self.failures += 1
        self.reason = reason or self.reason
        if hard:
            self.hard_open = True
            self.opened_at = float(self.clock())
        elif self.failures >= self.threshold:
            self.opened_at = float(self.clock())

    def is_open(self) -> bool:
        if self.hard_open:
            return True
        if not self.opened_at:
            return False
        if float(self.clock()) - self.opened_at > self.cooldown_sec:
            # Soft reopen for probe; keep failures near threshold.
            self.opened_at = 0.0
            self.failures = max(0, self.threshold - 1)
            return False
        return True

    def reset(self) -> None:
        self.failures = 0
        self.opened_at = 0.0
        self.reason = ""
        self.hard_open = False

    def as_dict(self) -> dict:
        return {
            "open": self.is_open(),
            "hard_open": self.hard_open,
            "failures": self.failures,
            "reason": self.reason,
            "threshold": self.threshold,
            "cooldown_sec": self.cooldown_sec,
        }
