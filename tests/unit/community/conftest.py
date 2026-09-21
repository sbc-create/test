"""Test isolation for the community ratings metrics store.

``factory.community.metrics`` mirrors every counter into a durable SQLite sink
whose default path is the production one, so that the monitor — a different
process — can read what the gateway wrote. That default makes any test which
exercises the facade write synthetic counters straight into production
telemetry, where they are indistinguishable from real visitor traffic.

This fixture is autouse for the whole package: every test in it gets its own
store, and the production path is never touched by a test run.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from factory.community import metrics, metrics_store

#: The path that must never be written while tests run.
PRODUCTION_STORE = Path("/srv/site-factory/repo/var/ratings/metrics.sqlite")


@pytest.fixture(autouse=True)
def _isolated_metrics_store(tmp_path, monkeypatch):
    store = tmp_path / "metrics-isolated.sqlite"
    monkeypatch.setattr(metrics_store, "DEFAULT_STORE_PATH", store)
    metrics_store.reset_cache()
    metrics_store.reset_drop_stats()
    metrics.reset_for_tests()
    try:
        yield store
    finally:
        metrics_store.reset_cache()
        metrics_store.reset_drop_stats()
        metrics.reset_for_tests()
