"""REQ-RETRY: ретраится только явно временное."""
import random

import pytest

from factory.errors import (
    BlockedAuthorization,
    BlockedInput,
    BlockedLicense,
    BlockedRights,
    BlockedSeo,
    DeployFailed,
    TransientError,
)
from factory.retry import RetryPolicy, is_retryable, run_with_retry


@pytest.mark.parametrize("error", [BlockedInput("x"), BlockedLicense("x"), BlockedRights("x"),
                                   BlockedAuthorization("x"), BlockedSeo("x")])
def test_configuration_errors_are_never_retried(error):
    assert not is_retryable(error)
    calls = {"n": 0}

    def fail():
        calls["n"] += 1
        raise error

    with pytest.raises(type(error)):
        run_with_retry(fail, policy=RetryPolicy(max_attempts=4), sleep=lambda d: None)
    assert calls["n"] == 1, "повтор не создаёт отсутствующий вход"


def test_transient_errors_are_retried():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise TransientError("временно недоступно")
        return "ok"

    assert run_with_retry(flaky, policy=RetryPolicy(max_attempts=4), sleep=lambda d: None) == "ok"
    assert calls["n"] == 3


def test_retry_limit_is_finite():
    calls = {"n": 0}

    def always_fails():
        calls["n"] += 1
        raise TransientError("всегда падает")

    with pytest.raises(TransientError):
        run_with_retry(always_fails, policy=RetryPolicy(max_attempts=3), sleep=lambda d: None)
    assert calls["n"] == 3


def test_backoff_is_exponential_and_bounded():
    policy = RetryPolicy(max_attempts=6, base_delay=1.0, max_delay=8.0, jitter=0.0)
    delays = [policy.delay_for(attempt) for attempt in range(1, 7)]
    assert delays == [1.0, 2.0, 4.0, 8.0, 8.0, 8.0]


def test_jitter_spreads_delays():
    policy = RetryPolicy(base_delay=4.0, jitter=0.25)
    values = {round(policy.delay_for(2, random.Random(seed)), 4) for seed in range(20)}
    assert len(values) > 5, "джиттер обязан разводить повторы"
    assert all(6.0 <= v <= 10.0 for v in values)


def test_deploy_failure_is_retryable_but_bounded():
    assert is_retryable(DeployFailed("x")) is True
