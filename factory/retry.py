"""Retry только для явно временных ошибок.

Ошибки конфигурации, лицензии, прав и авторизации не ретраятся — бесконечная
попытка не превращает отсутствующий вход в присутствующий.
"""
from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from factory.errors import FactoryError

T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 4
    base_delay: float = 1.0
    max_delay: float = 30.0
    jitter: float = 0.25

    def delay_for(self, attempt: int, rng: random.Random | None = None) -> float:
        """attempt начинается с 1. Экспонента с ограничением и джиттером."""
        rng = rng or random
        raw = min(self.base_delay * (2 ** (attempt - 1)), self.max_delay)
        return max(0.0, raw * (1 + rng.uniform(-self.jitter, self.jitter)))


DEFAULT_POLICY = RetryPolicy()


class RetryExhausted(RuntimeError):
    def __init__(self, attempts: int, last: BaseException) -> None:
        super().__init__(f"Исчерпано попыток: {attempts}. Последняя ошибка: {last}")
        self.attempts = attempts
        self.last = last


def is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, FactoryError):
        return exc.retryable
    return isinstance(exc, TimeoutError | ConnectionError | OSError)


def run_with_retry(
    fn: Callable[[], T],
    *,
    policy: RetryPolicy = DEFAULT_POLICY,
    sleep: Callable[[float], None] = time.sleep,
    rng: random.Random | None = None,
    on_retry: Callable[[int, BaseException, float], None] | None = None,
) -> T:
    last: BaseException | None = None
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return fn()
        except BaseException as exc:  # noqa: BLE001 — классифицируем ниже
            last = exc
            if not is_retryable(exc) or attempt == policy.max_attempts:
                raise
            delay = policy.delay_for(attempt, rng)
            if on_retry:
                on_retry(attempt, exc, delay)
            sleep(delay)
    raise RetryExhausted(policy.max_attempts, last or RuntimeError("unknown"))
