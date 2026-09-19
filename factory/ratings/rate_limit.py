"""Ограничитель частоты запросов с учётом RPS и минутного бюджета."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field


@dataclass
class RateLimiter:
    max_rps: float = 2.0
    max_per_minute: int = 60
    clock: callable = time.monotonic  # type: ignore[assignment]
    sleeper: callable = time.sleep  # type: ignore[assignment]
    _timestamps: deque[float] = field(default_factory=deque)
    _last_request: float = 0.0
    request_count: int = 0

    def wait(self) -> None:
        """Блокирует до разрешения следующего запроса. Безлимитных retries нет."""
        min_interval = 1.0 / self.max_rps if self.max_rps > 0 else 0.0
        while True:
            now = float(self.clock())
            # Drop timestamps older than 60s.
            while self._timestamps and now - self._timestamps[0] >= 60.0:
                self._timestamps.popleft()
            rps_wait = 0.0
            if min_interval and self._last_request:
                elapsed = now - self._last_request
                if elapsed < min_interval:
                    rps_wait = min_interval - elapsed
            minute_wait = 0.0
            if len(self._timestamps) >= self.max_per_minute:
                minute_wait = 60.0 - (now - self._timestamps[0])
            delay = max(rps_wait, minute_wait)
            if delay <= 0:
                break
            self.sleeper(delay)
        now = float(self.clock())
        self._last_request = now
        self._timestamps.append(now)
        self.request_count += 1

    def usage(self) -> dict:
        now = float(self.clock())
        while self._timestamps and now - self._timestamps[0] >= 60.0:
            self._timestamps.popleft()
        return {
            "request_count": self.request_count,
            "requests_last_minute": len(self._timestamps),
            "max_per_minute": self.max_per_minute,
            "max_rps": self.max_rps,
        }
