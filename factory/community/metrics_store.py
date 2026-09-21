"""Durable, inter-process metrics sink for community ratings.

COMMUNITY-RATINGS-07 found that ``monitor_once`` ran in its own process and
called ``metrics.snapshot()`` against a freshly-created, empty in-memory
counter set. Every traffic, error and latency field it published was therefore
structurally zero no matter what the gateway actually served — zeros that
looked like measurements.

This module is the fix. The gateway writes counters to a small SQLite file;
any other process — the monitor, the CLI, a test — reads the same file. A
reader that cannot reach the store reports ``UNMEASURED`` with a reason. It
never invents a zero.

Privacy: only counts are stored. Identity ids are never written; uniqueness is
tracked through a keyed HMAC of the identity, so the store can answer "how many
distinct visitors" without holding anything that identifies one.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

UNMEASURED = "UNMEASURED"

DEFAULT_STORE_PATH = Path(
    os.environ.get(
        "COMMUNITY_METRICS_STORE_PATH",
        "/srv/site-factory/repo/var/ratings/metrics.sqlite",
    )
)

#: Latency samples are a bounded ring — the store must not grow without bound.
MAX_LATENCY_SAMPLES = 5000

_lock = threading.RLock()
_conn_cache: dict[str, sqlite3.Connection] = {}

#: Writes the sink refused, counted in memory. A dropped write would otherwise
#: be indistinguishable from an event that never happened — the counter would
#: simply read low and look like quiet traffic. Readers surface this so a
#: broken sink is reported as a broken sink.
_dropped_writes = 0
_last_write_error: str | None = None


def _note_drop(exc: BaseException) -> None:
    global _dropped_writes, _last_write_error
    with _lock:
        _dropped_writes += 1
        _last_write_error = f"{type(exc).__name__}: {exc}"


def drop_stats() -> dict[str, Any]:
    with _lock:
        return {"dropped_writes": _dropped_writes, "last_write_error": _last_write_error}


def reset_drop_stats() -> None:
    global _dropped_writes, _last_write_error
    with _lock:
        _dropped_writes = 0
        _last_write_error = None


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _unique_pepper() -> bytes:
    """Key for the uniqueness HMAC. Never stored alongside the digests."""
    path = os.environ.get("COMMUNITY_METRICS_PEPPER_FILE", "").strip()
    if path and Path(path).is_file():
        raw = Path(path).read_bytes().strip()
        if raw:
            return raw
    env = os.environ.get("COMMUNITY_METRICS_PEPPER", "").strip()
    if env:
        return env.encode()
    return b"dev-only-metrics-pepper"


SCHEMA = (
    """CREATE TABLE IF NOT EXISTS counters (
        name       TEXT PRIMARY KEY,
        value      INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS unique_marks (
        kind        TEXT NOT NULL,
        token_hmac  TEXT NOT NULL,
        first_at    TEXT NOT NULL,
        PRIMARY KEY (kind, token_hmac)
    )""",
    """CREATE TABLE IF NOT EXISTS latency_samples (
        id  INTEGER PRIMARY KEY AUTOINCREMENT,
        ms  REAL NOT NULL,
        at  TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS meta (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )""",
)


class MetricsStoreUnavailable(RuntimeError):
    """The durable store could not be reached. Callers must report UNMEASURED."""


def _connect(path: Path, *, readonly: bool = False) -> sqlite3.Connection:
    if readonly:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        # The gateway is a ThreadingHTTPServer: every request runs on a new
        # thread and they all share this cached connection. Without
        # check_same_thread=False sqlite refuses the call, the write is dropped,
        # and — because metric failures must never break a user request — the
        # error is swallowed. The counter then reads low, which is exactly the
        # "silent zero" this module exists to prevent. Every use is serialised
        # under _lock, so sharing the connection is safe.
        conn = sqlite3.connect(str(path), timeout=10, check_same_thread=False)
        conn.execute("pragma journal_mode=wal")
        conn.execute("pragma busy_timeout=10000")
        conn.execute("pragma synchronous=normal")
        for stmt in SCHEMA:
            conn.execute(stmt)
        conn.commit()
    conn.row_factory = sqlite3.Row
    return conn


def _writer(path: Path | None = None) -> sqlite3.Connection:
    p = Path(path or DEFAULT_STORE_PATH)
    key = f"w:{p}"
    with _lock:
        conn = _conn_cache.get(key)
        if conn is None:
            conn = _connect(p, readonly=False)
            _conn_cache[key] = conn
        return conn


def reset_cache() -> None:
    """Drop cached connections — required when tests repoint the store path."""
    with _lock:
        for conn in _conn_cache.values():
            try:
                conn.close()
            except Exception:
                pass
        _conn_cache.clear()


# --------------------------------------------------------------------------
# write side (gateway process)
# --------------------------------------------------------------------------


def incr(name: str, n: int = 1, *, path: Path | None = None) -> bool:
    """Add ``n`` to a counter. Returns False if the store was unreachable.

    A failed metric write must never take down a user request, so every error
    is swallowed here — but it is reported through the return value so callers
    and tests can tell "not recorded" from "recorded zero".
    """
    try:
        conn = _writer(path)
        with _lock, conn:
            conn.execute(
                """INSERT INTO counters(name, value, updated_at) VALUES(?, ?, ?)
                   ON CONFLICT(name) DO UPDATE SET
                     value = value + excluded.value,
                     updated_at = excluded.updated_at""",
                (name, int(n), _utc()),
            )
        return True
    except Exception as exc:
        _note_drop(exc)
        return False


def mark_unique(kind: str, token: str, *, path: Path | None = None) -> bool:
    """Record that ``token`` was seen for ``kind`` — stored only as an HMAC."""
    if not token:
        return False
    try:
        digest = hmac.new(_unique_pepper(), f"{kind}|{token}".encode(), hashlib.sha256).hexdigest()
        conn = _writer(path)
        with _lock, conn:
            conn.execute(
                "INSERT OR IGNORE INTO unique_marks(kind, token_hmac, first_at) VALUES(?,?,?)",
                (kind, digest, _utc()),
            )
        return True
    except Exception as exc:
        _note_drop(exc)
        return False


def observe_latency_ms(ms: float, *, path: Path | None = None) -> bool:
    try:
        conn = _writer(path)
        with _lock, conn:
            conn.execute("INSERT INTO latency_samples(ms, at) VALUES(?,?)", (float(ms), _utc()))
            conn.execute(
                """DELETE FROM latency_samples WHERE id <= (
                     SELECT MAX(id) - ? FROM latency_samples)""",
                (MAX_LATENCY_SAMPLES,),
            )
        return True
    except Exception as exc:
        _note_drop(exc)
        return False


def set_meta(key: str, value: str, *, path: Path | None = None) -> bool:
    try:
        conn = _writer(path)
        with _lock, conn:
            conn.execute(
                """INSERT INTO meta(key, value) VALUES(?,?)
                   ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
                (key, str(value)),
            )
        return True
    except Exception as exc:
        _note_drop(exc)
        return False


# --------------------------------------------------------------------------
# read side (monitor / CLI / tests)
# --------------------------------------------------------------------------


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = int(round((len(ordered) - 1) * p))
    return ordered[idx]


def read_raw(path: Path | None = None) -> dict[str, Any]:
    """Read everything the store holds. Raises MetricsStoreUnavailable."""
    p = Path(path or DEFAULT_STORE_PATH)
    if not p.is_file():
        raise MetricsStoreUnavailable(f"metrics store missing at {p}")
    try:
        conn = _connect(p, readonly=True)
    except Exception as exc:  # pragma: no cover - depends on fs state
        raise MetricsStoreUnavailable(f"cannot open metrics store at {p}: {exc}") from exc
    try:
        counters = {r["name"]: int(r["value"]) for r in conn.execute("SELECT name, value FROM counters")}
        updated = [r["updated_at"] for r in conn.execute("SELECT updated_at FROM counters")]
        uniques = {
            r["kind"]: int(r["n"])
            for r in conn.execute("SELECT kind, COUNT(*) AS n FROM unique_marks GROUP BY kind")
        }
        lat = [float(r["ms"]) for r in conn.execute("SELECT ms FROM latency_samples")]
        meta = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM meta")}
    finally:
        conn.close()
    return {
        "counters": counters,
        "uniques": uniques,
        "latency_samples": lat,
        "meta": meta,
        "last_counter_update": max(updated) if updated else None,
        "store_path": str(p),
    }


#: Every metric the stage contract requires, mapped to the counter that backs
#: it. A name absent from the store has genuinely never been recorded, which is
#: reported as UNMEASURED rather than 0.
COUNTER_METRICS = {
    "session_bootstraps": "session_bootstraps",
    "eligible_cohort_impressions": "eligible_cohort_impressions",
    "widget_rendered": "widget_rendered",
    "cast_attempts": "cast_attempts",
    "accepted_casts": "cast_accepted",
    "updates": "update_accepted",
    "retracts": "retract_accepted",
    "rejected_writes": "write_4xx",
    "api_errors": "write_5xx",
    "rate_limit_violations": "rate_limited",
    "quarantine_events": "quarantined_votes",
    "csrf_denied": "csrf_denied",
    "origin_denied": "origin_denied",
    "cohort_denied": "cohort_denied",
    "cross_space_denied": "cross_space_denied",
    "invalid_rating_denied": "invalid_rating_denied",
    "identities_created": "identities_created",
    "preview_requests": "preview_requests",
}


def snapshot(
    *,
    path: Path | None = None,
    kill_switch_state: int | str = UNMEASURED,
    rollout_percent: int | str = UNMEASURED,
    db_derived: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Metric view for the monitor, with per-metric provenance.

    ``db_derived`` carries the metrics whose authority is the ratings ledger
    rather than the counter store (duplicate active votes, aggregate rebuild
    mismatches, preview/write mismatches). They are passed in so this module
    stays the transport and the ledger stays the source of truth.
    """
    captured_at = _utc()
    provenance: dict[str, Any] = {}
    out: dict[str, Any] = {}

    try:
        raw = read_raw(path)
        store_ok = True
        store_error = None
    except MetricsStoreUnavailable as exc:
        raw = {"counters": {}, "uniques": {}, "latency_samples": [], "meta": {}, "last_counter_update": None}
        store_ok = False
        store_error = str(exc)

    counters = raw["counters"]
    for public_name, counter_name in COUNTER_METRICS.items():
        if not store_ok:
            out[public_name] = UNMEASURED
            provenance[public_name] = {
                "source": "metrics_store",
                "status": UNMEASURED,
                "reason": store_error,
            }
        elif counter_name not in counters:
            out[public_name] = UNMEASURED
            provenance[public_name] = {
                "source": "metrics_store",
                "status": UNMEASURED,
                "reason": f"counter '{counter_name}' has never been recorded",
            }
        else:
            out[public_name] = counters[counter_name]
            provenance[public_name] = {
                "source": "metrics_store",
                "store_path": raw.get("store_path"),
                "status": "MEASURED",
                "window": "cumulative since store creation",
                "last_update": raw.get("last_counter_update"),
            }

    # Exposed visitors is a distinct count, not a sum of impressions.
    if not store_ok:
        out["exposed_visitors"] = UNMEASURED
        provenance["exposed_visitors"] = {"source": "metrics_store", "status": UNMEASURED, "reason": store_error}
    elif "exposed_visitor" not in raw["uniques"] and not counters.get("eligible_cohort_impressions"):
        out["exposed_visitors"] = UNMEASURED
        provenance["exposed_visitors"] = {
            "source": "metrics_store.unique_marks",
            "status": UNMEASURED,
            "reason": "no eligible impression has been recorded yet",
        }
    else:
        out["exposed_visitors"] = int(raw["uniques"].get("exposed_visitor", 0))
        provenance["exposed_visitors"] = {
            "source": "metrics_store.unique_marks",
            "status": "MEASURED",
            "window": "distinct identities, cumulative",
            "last_update": raw.get("last_counter_update"),
        }

    samples = raw["latency_samples"]
    if not store_ok:
        out["latency_p50_ms"] = UNMEASURED
        out["latency_p95_ms"] = UNMEASURED
        lat_prov = {"source": "metrics_store", "status": UNMEASURED, "reason": store_error}
    elif not samples:
        out["latency_p50_ms"] = UNMEASURED
        out["latency_p95_ms"] = UNMEASURED
        lat_prov = {
            "source": "metrics_store.latency_samples",
            "status": UNMEASURED,
            "reason": "no write request has been sampled",
        }
    else:
        out["latency_p50_ms"] = _percentile(samples, 0.50)
        out["latency_p95_ms"] = _percentile(samples, 0.95)
        lat_prov = {
            "source": "metrics_store.latency_samples",
            "status": "MEASURED",
            "window": f"last {len(samples)} sampled write requests (ring of {MAX_LATENCY_SAMPLES})",
            "last_update": raw.get("last_counter_update"),
        }
    provenance["latency_p50_ms"] = lat_prov
    provenance["latency_p95_ms"] = lat_prov

    for name, value in (db_derived or {}).items():
        out[name] = value
        provenance[name] = {
            "source": "ratings_ledger",
            "status": "MEASURED" if value != UNMEASURED else UNMEASURED,
            "window": "current database state",
            "last_update": captured_at,
        }
    for required in ("duplicate_active_votes", "preview_write_mismatches", "aggregate_rebuild_mismatches"):
        if required not in out:
            out[required] = UNMEASURED
            provenance[required] = {
                "source": "ratings_ledger",
                "status": UNMEASURED,
                "reason": "not supplied by the caller",
            }

    out["kill_switch_state"] = kill_switch_state
    provenance["kill_switch_state"] = {
        "source": "rollout_flags_file",
        "status": "MEASURED" if kill_switch_state != UNMEASURED else UNMEASURED,
        "last_update": captured_at,
    }
    out["rollout_percent"] = rollout_percent
    provenance["rollout_percent"] = {
        "source": "rollout_flags_file",
        "status": "MEASURED" if rollout_percent != UNMEASURED else UNMEASURED,
        "last_update": captured_at,
    }

    drops = drop_stats()
    if drops["dropped_writes"]:
        # Counters are known to be short by at least this many events, so the
        # numbers above are a floor, not a measurement. Say so.
        for name in list(out):
            if isinstance(out[name], int) and provenance.get(name, {}).get("status") == "MEASURED":
                provenance[name]["status"] = "PARTIAL"
                provenance[name]["reason"] = (
                    f"{drops['dropped_writes']} metric writes were refused by the "
                    f"sink ({drops['last_write_error']}); counts are a lower bound"
                )

    return {
        "captured_at": captured_at,
        "store_reachable": store_ok,
        "store_error": store_error,
        "dropped_writes_this_process": drops["dropped_writes"],
        "last_write_error": drops["last_write_error"],
        "store_path": raw.get("store_path", str(Path(path or DEFAULT_STORE_PATH))),
        "metrics": out,
        "provenance": provenance,
        "unmeasured": sorted(k for k, v in out.items() if v == UNMEASURED),
    }
