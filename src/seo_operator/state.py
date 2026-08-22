"""
Durable state вне чата: очередь джобов, локи, наблюдения, эксперименты, снапшоты.

Разговор Claude НЕ является планировщиком или базой. Всё состояние — здесь.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id TEXT NOT NULL,
    source TEXT NOT NULL,
    metric TEXT NOT NULL,
    dimension TEXT,
    value REAL,
    observed_date TEXT NOT NULL,
    collected_at TEXT NOT NULL,
    timezone TEXT NOT NULL,
    source_window TEXT NOT NULL,
    data_freshness TEXT NOT NULL,
    completeness REAL NOT NULL,
    raw TEXT,
    UNIQUE(site_id, source, metric, dimension, observed_date)
);
CREATE INDEX IF NOT EXISTS idx_obs_site_date ON observations(site_id, observed_date);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_key TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL,
    site_id TEXT,
    payload TEXT NOT NULL,
    status TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 5,
    next_run_at TEXT NOT NULL,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status, next_run_at);

CREATE TABLE IF NOT EXISTS locks (
    name TEXT PRIMARY KEY,
    holder TEXT NOT NULL,
    acquired_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS experiments (
    id TEXT PRIMARY KEY,
    site_id TEXT NOT NULL,
    page_type TEXT,
    query_cohort TEXT,
    hypothesis TEXT NOT NULL,
    evidence TEXT NOT NULL,
    primary_variable TEXT NOT NULL,
    secondary_changes TEXT,
    baseline_start TEXT NOT NULL,
    baseline_end TEXT NOT NULL,
    control_cohort TEXT,
    started_at TEXT,
    ends_at TEXT,
    primary_kpi TEXT NOT NULL,
    guardrails TEXT NOT NULL,
    min_sample TEXT NOT NULL,
    stop_loss TEXT NOT NULL,
    rollback_payload TEXT,
    before_snapshot TEXT,
    audit_refs TEXT,
    status TEXT NOT NULL,
    result TEXT,
    confidence REAL,
    confounders TEXT,
    decision TEXT,
    learned_rule_candidate TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_exp_site_status ON experiments(site_id, status);

CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment_id TEXT,
    site_id TEXT NOT NULL,
    target TEXT NOT NULL,
    before TEXT NOT NULL,
    after TEXT,
    rollback_payload TEXT NOT NULL,
    created_at TEXT NOT NULL,
    rolled_back_at TEXT
);

CREATE TABLE IF NOT EXISTS incidents (
    id TEXT PRIMARY KEY,
    site_id TEXT NOT NULL,
    condition_id TEXT NOT NULL,
    severity TEXT NOT NULL,
    detail TEXT NOT NULL,
    status TEXT NOT NULL,
    opened_at TEXT NOT NULL,
    closed_at TEXT,
    evidence TEXT
);

CREATE TABLE IF NOT EXISTS blockers (
    fingerprint TEXT PRIMARY KEY,
    site_id TEXT,
    kind TEXT NOT NULL,
    detail TEXT NOT NULL,
    request TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    reported INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS quota_usage (
    source TEXT NOT NULL,
    site_id TEXT NOT NULL,
    usage_date TEXT NOT NULL,
    used INTEGER NOT NULL DEFAULT 0,
    budget INTEGER NOT NULL,
    PRIMARY KEY (source, site_id, usage_date)
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Job:
    job_key: str
    kind: str
    payload: dict[str, Any]
    site_id: str | None = None
    max_attempts: int = 5


class Store:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (config.state_dir() / "state.sqlite3")
        self._conn = sqlite3.connect(self.path, timeout=30.0)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    # ---------------- observations ----------------

    def record_observation(self, *, site_id: str, source: str, metric: str, value: float | None,
                           observed_date: str, timezone_name: str, source_window: str,
                           data_freshness: str, completeness: float,
                           dimension: str | None = None, raw: dict | None = None) -> None:
        """Идемпотентно. Повторный сбор того же дня обновляет completeness/value."""
        self._conn.execute(
            """INSERT INTO observations
               (site_id, source, metric, dimension, value, observed_date, collected_at,
                timezone, source_window, data_freshness, completeness, raw)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(site_id, source, metric, dimension, observed_date)
               DO UPDATE SET value=excluded.value, collected_at=excluded.collected_at,
                             completeness=excluded.completeness, data_freshness=excluded.data_freshness,
                             raw=excluded.raw""",
            (site_id, source, metric, dimension, value, observed_date, _now(), timezone_name,
             source_window, data_freshness, completeness,
             json.dumps(raw, ensure_ascii=False) if raw else None),
        )
        self._conn.commit()

    def observations(self, site_id: str, metric: str, since: str | None = None,
                     min_completeness: float = 0.0) -> list[sqlite3.Row]:
        sql = ("SELECT * FROM observations WHERE site_id=? AND metric=? AND completeness>=?")
        args: list[Any] = [site_id, metric, min_completeness]
        if since:
            sql += " AND observed_date >= ?"
            args.append(since)
        sql += " ORDER BY observed_date ASC"
        return list(self._conn.execute(sql, args))

    # ---------------- jobs ----------------

    def enqueue(self, job: Job, run_at: str | None = None) -> bool:
        """Идемпотентно по job_key: повторная постановка того же джоба — no-op."""
        try:
            self._conn.execute(
                """INSERT INTO jobs (job_key, kind, site_id, payload, status, next_run_at,
                                     max_attempts, created_at, updated_at)
                   VALUES (?,?,?,?,'pending',?,?,?,?)""",
                (job.job_key, job.kind, job.site_id, json.dumps(job.payload, ensure_ascii=False),
                 run_at or _now(), job.max_attempts, _now(), _now()),
            )
            self._conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def claim_job(self) -> sqlite3.Row | None:
        row = self._conn.execute(
            "SELECT * FROM jobs WHERE status='pending' AND next_run_at<=? ORDER BY next_run_at LIMIT 1",
            (_now(),),
        ).fetchone()
        if not row:
            return None
        self._conn.execute("UPDATE jobs SET status='running', updated_at=? WHERE id=?", (_now(), row["id"]))
        self._conn.commit()
        return row

    def complete_job(self, job_id: int) -> None:
        self._conn.execute("UPDATE jobs SET status='done', updated_at=? WHERE id=?", (_now(), job_id))
        self._conn.commit()

    def fail_job(self, job_id: int, error: str, transient: bool) -> str:
        """
        Retry только для transient (сеть/5xx/квота). Auth/rights/policy/schema —
        сразу в quarantine: бесконечный retry ничего не чинит.
        """
        row = self._conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        attempts = row["attempts"] + 1
        if not transient or attempts >= row["max_attempts"]:
            status = "quarantined"
            next_run = _now()
        else:
            status = "pending"
            backoff = min(2 ** attempts, 900)
            jitter = (hash(row["job_key"]) % 30) / 10.0
            next_run = (datetime.now(timezone.utc) + timedelta(seconds=backoff + jitter)).isoformat()
        self._conn.execute(
            "UPDATE jobs SET status=?, attempts=?, last_error=?, next_run_at=?, updated_at=? WHERE id=?",
            (status, attempts, error[:2000], next_run, _now(), job_id),
        )
        self._conn.commit()
        return status

    def quarantined_jobs(self) -> list[sqlite3.Row]:
        return list(self._conn.execute("SELECT * FROM jobs WHERE status='quarantined'"))

    def pending_job_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) c FROM jobs WHERE status='pending'").fetchone()["c"]

    # ---------------- locks ----------------

    @contextmanager
    def lock(self, name: str, ttl_seconds: int = 1800, holder: str | None = None) -> Iterator[bool]:
        """Per-site / per-cohort / global-deploy локи. Истёкшие захватываются заново."""
        holder = holder or f"pid:{os.getpid()}"
        now = datetime.now(timezone.utc)
        expires = (now + timedelta(seconds=ttl_seconds)).isoformat()
        acquired = False
        try:
            self._conn.execute("DELETE FROM locks WHERE expires_at < ?", (now.isoformat(),))
            self._conn.execute(
                "INSERT INTO locks (name, holder, acquired_at, expires_at) VALUES (?,?,?,?)",
                (name, holder, now.isoformat(), expires),
            )
            self._conn.commit()
            acquired = True
            yield True
        except sqlite3.IntegrityError:
            yield False
        finally:
            if acquired:
                self._conn.execute("DELETE FROM locks WHERE name=? AND holder=?", (name, holder))
                self._conn.commit()

    # ---------------- quota ----------------

    def consume_quota(self, source: str, site_id: str, budget: int, amount: int = 1) -> bool:
        today = datetime.now(timezone.utc).date().isoformat()
        self._conn.execute(
            "INSERT OR IGNORE INTO quota_usage (source, site_id, usage_date, used, budget) VALUES (?,?,?,0,?)",
            (source, site_id, today, budget),
        )
        row = self._conn.execute(
            "SELECT used FROM quota_usage WHERE source=? AND site_id=? AND usage_date=?",
            (source, site_id, today)).fetchone()
        if row["used"] + amount > budget:
            return False
        self._conn.execute(
            "UPDATE quota_usage SET used=used+? WHERE source=? AND site_id=? AND usage_date=?",
            (amount, source, site_id, today))
        self._conn.commit()
        return True

    # ---------------- blockers ----------------

    def record_blocker(self, fingerprint: str, kind: str, detail: str,
                       request: dict[str, Any], site_id: str | None = None) -> bool:
        """Возвращает True если блокер новый (нужно включить в отчёт)."""
        existing = self._conn.execute(
            "SELECT fingerprint FROM blockers WHERE fingerprint=?", (fingerprint,)).fetchone()
        if existing:
            self._conn.execute("UPDATE blockers SET last_seen=? WHERE fingerprint=?", (_now(), fingerprint))
            self._conn.commit()
            return False
        self._conn.execute(
            "INSERT INTO blockers (fingerprint, site_id, kind, detail, request, first_seen, last_seen)"
            " VALUES (?,?,?,?,?,?,?)",
            (fingerprint, site_id, kind, detail, json.dumps(request, ensure_ascii=False), _now(), _now()))
        self._conn.commit()
        return True

    def unreported_blockers(self) -> list[sqlite3.Row]:
        return list(self._conn.execute("SELECT * FROM blockers WHERE reported=0 ORDER BY first_seen"))

    def mark_blockers_reported(self) -> None:
        self._conn.execute("UPDATE blockers SET reported=1 WHERE reported=0")
        self._conn.commit()

    # ---------------- snapshots ----------------

    def save_snapshot(self, *, site_id: str, target: str, before: dict, rollback_payload: dict,
                      experiment_id: str | None = None) -> int:
        cur = self._conn.execute(
            "INSERT INTO snapshots (experiment_id, site_id, target, before, rollback_payload, created_at)"
            " VALUES (?,?,?,?,?,?)",
            (experiment_id, site_id, target, json.dumps(before, ensure_ascii=False),
             json.dumps(rollback_payload, ensure_ascii=False), _now()))
        self._conn.commit()
        return cur.lastrowid

    def set_snapshot_after(self, snapshot_id: int, after: dict) -> None:
        self._conn.execute("UPDATE snapshots SET after=? WHERE id=?",
                           (json.dumps(after, ensure_ascii=False), snapshot_id))
        self._conn.commit()

    def snapshots_for(self, experiment_id: str) -> list[sqlite3.Row]:
        return list(self._conn.execute(
            "SELECT * FROM snapshots WHERE experiment_id=? AND rolled_back_at IS NULL ORDER BY id DESC",
            (experiment_id,)))

    def mark_rolled_back(self, snapshot_id: int) -> None:
        self._conn.execute("UPDATE snapshots SET rolled_back_at=? WHERE id=?", (_now(), snapshot_id))
        self._conn.commit()

    # ---------------- incidents ----------------

    def open_incident(self, incident_id: str, site_id: str, condition_id: str,
                      severity: str, detail: str, evidence: dict | None = None) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO incidents (id, site_id, condition_id, severity, detail, status, opened_at, evidence)"
            " VALUES (?,?,?,?,?,'open',?,?)",
            (incident_id, site_id, condition_id, severity, detail, _now(),
             json.dumps(evidence or {}, ensure_ascii=False)))
        self._conn.commit()

    def open_incidents(self, site_id: str | None = None) -> list[sqlite3.Row]:
        if site_id:
            return list(self._conn.execute(
                "SELECT * FROM incidents WHERE status='open' AND site_id=?", (site_id,)))
        return list(self._conn.execute("SELECT * FROM incidents WHERE status='open'"))

    def close_incident(self, incident_id: str) -> None:
        self._conn.execute("UPDATE incidents SET status='closed', closed_at=? WHERE id=?",
                           (_now(), incident_id))
        self._conn.commit()

    # ---------------- raw access for experiments module ----------------

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    def close(self) -> None:
        self._conn.close()
