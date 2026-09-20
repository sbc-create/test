"""PII-free community ratings metrics (in-memory + optional daily dump)."""

from __future__ import annotations

import json
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_lock = threading.RLock()
_counters: dict[str, int] = defaultdict(int)
_latencies_ms: list[float] = []
_MAX_LAT = 5000


def incr(name: str, n: int = 1) -> None:
    with _lock:
        _counters[name] += n


def observe_latency_ms(ms: float) -> None:
    with _lock:
        _latencies_ms.append(float(ms))
        if len(_latencies_ms) > _MAX_LAT:
            del _latencies_ms[: len(_latencies_ms) - _MAX_LAT]


def _percentile(sorted_vals: list[float], p: float) -> float | None:
    if not sorted_vals:
        return None
    idx = int(round((len(sorted_vals) - 1) * p))
    return sorted_vals[idx]


def snapshot(*, kill_switch_state: int = 0, rollout_percent: int = 0) -> dict[str, Any]:
    with _lock:
        lats = sorted(_latencies_ms)
        counts = dict(_counters)
    return {
        "widget_impressions": counts.get("widget_impressions", 0),
        "eligible_widget_impressions": counts.get("eligible_widget_impressions", 0),
        "write_attempts": counts.get("write_attempts", 0),
        "cast_accepted": counts.get("cast_accepted", 0),
        "update_accepted": counts.get("update_accepted", 0),
        "retract_accepted": counts.get("retract_accepted", 0),
        "rate_limited": counts.get("rate_limited", 0),
        "cohort_denied": counts.get("cohort_denied", 0),
        "csrf_denied": counts.get("csrf_denied", 0),
        "origin_denied": counts.get("origin_denied", 0),
        "invalid_rating_denied": counts.get("invalid_rating_denied", 0),
        "unknown_title_denied": counts.get("unknown_title_denied", 0),
        "cross_space_denied": counts.get("cross_space_denied", 0),
        "quarantined_votes": counts.get("quarantined_votes", 0),
        "active_native_votes": counts.get("active_native_votes", 0),
        "aggregate_rebuild_mismatches": counts.get("aggregate_rebuild_mismatches", 0),
        "db_busy_errors": counts.get("db_busy_errors", 0),
        "write_4xx": counts.get("write_4xx", 0),
        "write_5xx": counts.get("write_5xx", 0),
        "write_latency_p50": _percentile(lats, 0.50),
        "write_latency_p95": _percentile(lats, 0.95),
        "kill_switch_state": kill_switch_state,
        "rollout_percent": rollout_percent,
        "identities_created": counts.get("identities_created", 0),
        "captured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def dump_daily(path: Path, **kwargs: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = snapshot(**kwargs)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def reset_for_tests() -> None:
    with _lock:
        _counters.clear()
        _latencies_ms.clear()
