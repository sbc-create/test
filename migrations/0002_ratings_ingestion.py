"""Миграция 0002 — ratings ingestion (append-only observations + queue).

Применяется ТОЛЬКО к изолированной SQLite (тесты / evidence / stage DB).
Production-БД этой миграцией на ЭТАПЕ 1 не затрагивается.
"""

from __future__ import annotations

import datetime as dt
import sqlite3

VERSION = "0002"
DESCRIPTION = "ratings ingestion: registry, mappings, observations, queue, runs"


UP = [
    """
    CREATE TABLE IF NOT EXISTS rating_sources (
        source_key              TEXT PRIMARY KEY,
        display_name            TEXT NOT NULL,
        canonical_origin        TEXT NOT NULL DEFAULT '',
        adapter_version         TEXT NOT NULL DEFAULT '',
        state                   TEXT NOT NULL,
        enabled                 INTEGER NOT NULL DEFAULT 0,
        score_scale             REAL NOT NULL DEFAULT 10.0,
        supports_vote_count     INTEGER NOT NULL DEFAULT 0,
        supports_distribution   INTEGER NOT NULL DEFAULT 0,
        max_rps                 REAL NOT NULL DEFAULT 2.0,
        max_requests_per_minute INTEGER NOT NULL DEFAULT 60,
        freshness_policy_json   TEXT NOT NULL DEFAULT '{}',
        legal_access_evidence   TEXT NOT NULL DEFAULT '',
        attribution_gate        TEXT NOT NULL DEFAULT '',
        last_schema_check       TEXT NOT NULL DEFAULT '',
        last_successful_fetch   TEXT NOT NULL DEFAULT '',
        health_state            TEXT NOT NULL DEFAULT 'UNKNOWN'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS title_source_mappings (
        canonical_title_id TEXT NOT NULL,
        source_key         TEXT NOT NULL,
        external_title_id  TEXT NOT NULL,
        external_url       TEXT NOT NULL DEFAULT '',
        mapping_method     TEXT NOT NULL,
        confidence         REAL NOT NULL DEFAULT 0.0,
        evidence           TEXT NOT NULL DEFAULT '',
        verified_at        TEXT NOT NULL DEFAULT '',
        state              TEXT NOT NULL,
        PRIMARY KEY (canonical_title_id, source_key),
        UNIQUE (source_key, external_title_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rating_observations (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        canonical_title_id TEXT NOT NULL,
        source_key         TEXT NOT NULL,
        external_id        TEXT NOT NULL,
        raw_score          REAL,
        source_scale       REAL NOT NULL,
        normalized_score   REAL,
        vote_count         INTEGER,
        score_distribution TEXT,
        source_updated_at  TEXT NOT NULL DEFAULT '',
        observed_at        TEXT NOT NULL,
        payload_sha256     TEXT NOT NULL,
        adapter_version    TEXT NOT NULL,
        provenance_url     TEXT NOT NULL DEFAULT '',
        mapping_method     TEXT NOT NULL,
        validation_state   TEXT NOT NULL,
        run_id             TEXT NOT NULL DEFAULT '',
        idempotency_key    TEXT NOT NULL,
        UNIQUE (idempotency_key)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_ro_title_source ON rating_observations(canonical_title_id, source_key)",
    "CREATE INDEX IF NOT EXISTS ix_ro_payload ON rating_observations(payload_sha256)",
    """
    CREATE TABLE IF NOT EXISTS rating_current (
        canonical_title_id TEXT NOT NULL,
        source_key         TEXT NOT NULL,
        observation_id     INTEGER,
        raw_score          REAL,
        normalized_score   REAL,
        vote_count         INTEGER,
        freshness          TEXT NOT NULL,
        observed_at        TEXT NOT NULL DEFAULT '',
        provenance_url     TEXT NOT NULL DEFAULT '',
        payload_sha256     TEXT NOT NULL DEFAULT '',
        adapter_version    TEXT NOT NULL DEFAULT '',
        external_id        TEXT NOT NULL DEFAULT '',
        PRIMARY KEY (canonical_title_id, source_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rating_ingestion_runs (
        run_id              TEXT PRIMARY KEY,
        source_key          TEXT NOT NULL,
        started_at          TEXT NOT NULL,
        finished_at         TEXT NOT NULL DEFAULT '',
        status              TEXT NOT NULL,
        dry_run             INTEGER NOT NULL DEFAULT 1,
        idempotency_key     TEXT NOT NULL UNIQUE,
        checkpoint_json     TEXT NOT NULL DEFAULT '{}',
        metrics_json        TEXT NOT NULL DEFAULT '{}',
        candidate_cap       INTEGER NOT NULL DEFAULT 0,
        success_target      INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rating_backfill_queue (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        canonical_title_id TEXT NOT NULL,
        source_key         TEXT NOT NULL,
        priority           INTEGER NOT NULL,
        priority_label     TEXT NOT NULL DEFAULT '',
        state              TEXT NOT NULL DEFAULT 'PENDING',
        enqueued_at        TEXT NOT NULL,
        available_at       TEXT NOT NULL DEFAULT '',
        claimed_by         TEXT NOT NULL DEFAULT '',
        claim_lease_until  TEXT NOT NULL DEFAULT '',
        attempts           INTEGER NOT NULL DEFAULT 0,
        last_error         TEXT NOT NULL DEFAULT '',
        UNIQUE (canonical_title_id, source_key)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_rbq_claim ON rating_backfill_queue(state, priority, available_at)",
    """
    CREATE TABLE IF NOT EXISTS rating_backfill_cursor (
        source_key   TEXT PRIMARY KEY,
        cursor_json  TEXT NOT NULL DEFAULT '{}',
        updated_at   TEXT NOT NULL DEFAULT ''
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rating_conflicts (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        canonical_title_id TEXT NOT NULL,
        source_key         TEXT NOT NULL,
        reason             TEXT NOT NULL,
        evidence_json      TEXT NOT NULL DEFAULT '{}',
        created_at         TEXT NOT NULL,
        resolved_at        TEXT NOT NULL DEFAULT '',
        state              TEXT NOT NULL DEFAULT 'OPEN'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rating_review_queue (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        canonical_title_id TEXT NOT NULL,
        source_key         TEXT NOT NULL,
        candidates_json    TEXT NOT NULL DEFAULT '[]',
        reason             TEXT NOT NULL,
        created_at         TEXT NOT NULL,
        state              TEXT NOT NULL DEFAULT 'PENDING'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rating_dead_letter (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        canonical_title_id TEXT NOT NULL,
        source_key         TEXT NOT NULL,
        run_id             TEXT NOT NULL DEFAULT '',
        error              TEXT NOT NULL,
        payload_json       TEXT NOT NULL DEFAULT '{}',
        created_at         TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version     TEXT PRIMARY KEY,
        description TEXT NOT NULL,
        applied_at  TEXT NOT NULL
    )
    """,
]

DOWN = [
    "DROP TABLE IF EXISTS rating_dead_letter",
    "DROP TABLE IF EXISTS rating_review_queue",
    "DROP TABLE IF EXISTS rating_conflicts",
    "DROP TABLE IF EXISTS rating_backfill_cursor",
    "DROP INDEX IF EXISTS ix_rbq_claim",
    "DROP TABLE IF EXISTS rating_backfill_queue",
    "DROP TABLE IF EXISTS rating_ingestion_runs",
    "DROP TABLE IF EXISTS rating_current",
    "DROP INDEX IF EXISTS ix_ro_payload",
    "DROP INDEX IF EXISTS ix_ro_title_source",
    "DROP TABLE IF EXISTS rating_observations",
    "DROP TABLE IF EXISTS title_source_mappings",
    "DROP TABLE IF EXISTS rating_sources",
    "DELETE FROM schema_migrations WHERE version = '0002'",
]


def upgrade(conn: sqlite3.Connection) -> None:
    for stmt in UP:
        conn.execute(stmt)
    conn.execute(
        "INSERT OR REPLACE INTO schema_migrations(version, description, applied_at) VALUES (?,?,?)",
        (VERSION, DESCRIPTION, dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")),
    )
    conn.commit()


def downgrade(conn: sqlite3.Connection) -> None:
    for stmt in DOWN:
        try:
            conn.execute(stmt)
        except sqlite3.OperationalError:
            pass
    conn.commit()


def applied(conn: sqlite3.Connection) -> bool:
    try:
        row = conn.execute(
            "SELECT 1 FROM schema_migrations WHERE version = ?", (VERSION,)
        ).fetchone()
    except sqlite3.OperationalError:
        return False
    return row is not None
