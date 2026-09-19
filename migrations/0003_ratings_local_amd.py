"""Миграция 0003 — AMD baseline, local votes, combined projection, daily ledger.

Только isolated SQLite. Production на Stage 2 не применяется.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import sqlite3

VERSION = "0003"
DESCRIPTION = "amd local votes combined daily ratings"


UP = [
    # Extend observations with component scores / permission / quality (nullable columns)
    """
    ALTER TABLE rating_observations ADD COLUMN component_scores TEXT
    """,
    """
    ALTER TABLE rating_observations ADD COLUMN permission_version TEXT NOT NULL DEFAULT ''
    """,
    """
    ALTER TABLE rating_observations ADD COLUMN quality_flags TEXT NOT NULL DEFAULT '[]'
    """,
    """
    ALTER TABLE rating_observations ADD COLUMN source_url TEXT NOT NULL DEFAULT ''
    """,
    """
    ALTER TABLE rating_current ADD COLUMN component_scores TEXT
    """,
    """
    ALTER TABLE rating_current ADD COLUMN quality_flags TEXT NOT NULL DEFAULT '[]'
    """,
    """
    ALTER TABLE rating_current ADD COLUMN degraded INTEGER NOT NULL DEFAULT 0
    """,
    # Local vote events (append-only audit)
    """
    CREATE TABLE IF NOT EXISTS rating_vote_event (
        event_id           TEXT PRIMARY KEY,
        request_id         TEXT NOT NULL DEFAULT '',
        idempotency_key    TEXT NOT NULL,
        canonical_title_id TEXT NOT NULL,
        voter_subject_id   TEXT NOT NULL,
        scope              TEXT NOT NULL,
        site_id            TEXT NOT NULL DEFAULT '',
        action             TEXT NOT NULL,
        old_score          INTEGER,
        new_score          INTEGER,
        moderation_status  TEXT NOT NULL,
        reason             TEXT NOT NULL DEFAULT '',
        created_at         TEXT NOT NULL,
        formula_version    TEXT NOT NULL DEFAULT '',
        payload_digest     TEXT NOT NULL DEFAULT '',
        UNIQUE (idempotency_key)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_rve_title ON rating_vote_event(canonical_title_id)",
    (
        "CREATE INDEX IF NOT EXISTS ix_rve_voter "
        "ON rating_vote_event(voter_subject_id, canonical_title_id)"
    ),
    """
    CREATE TABLE IF NOT EXISTS rating_vote_current (
        canonical_title_id TEXT NOT NULL,
        voter_subject_id   TEXT NOT NULL,
        scope              TEXT NOT NULL,
        site_id            TEXT NOT NULL DEFAULT '',
        score              INTEGER NOT NULL CHECK (score >= 1 AND score <= 10),
        state              TEXT NOT NULL,
        created_at         TEXT NOT NULL,
        updated_at         TEXT NOT NULL,
        PRIMARY KEY (canonical_title_id, voter_subject_id, scope, site_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rating_local_aggregate (
        canonical_title_id   TEXT NOT NULL,
        scope                TEXT NOT NULL,
        site_id              TEXT NOT NULL DEFAULT '',
        accepted_vote_count  INTEGER NOT NULL DEFAULT 0 CHECK (accepted_vote_count >= 0),
        accepted_vote_sum    INTEGER NOT NULL DEFAULT 0,
        average_score        TEXT,
        updated_at           TEXT NOT NULL,
        digest               TEXT NOT NULL,
        PRIMARY KEY (canonical_title_id, scope, site_id),
        CHECK (accepted_vote_sum >= accepted_vote_count),
        CHECK (accepted_vote_sum <= accepted_vote_count * 10)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rating_combined_projection (
        canonical_title_id     TEXT NOT NULL,
        scope                  TEXT NOT NULL DEFAULT 'NETWORK',
        site_id                TEXT NOT NULL DEFAULT '',
        amd_score              TEXT,
        amd_vote_count         INTEGER,
        baseline_weight        INTEGER NOT NULL DEFAULT 0,
        local_vote_count       INTEGER NOT NULL DEFAULT 0,
        local_vote_sum         INTEGER NOT NULL DEFAULT 0,
        combined_raw           TEXT,
        combined_ui            TEXT,
        state                  TEXT NOT NULL,
        formula_version        TEXT NOT NULL,
        quality_flags          TEXT NOT NULL DEFAULT '[]',
        rotation_score         TEXT,
        rotation_algorithm     TEXT NOT NULL DEFAULT '',
        updated_at             TEXT NOT NULL,
        PRIMARY KEY (canonical_title_id, scope, site_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ratings_daily_run (
        run_id                 TEXT PRIMARY KEY,
        report_date            TEXT NOT NULL,
        timezone               TEXT NOT NULL DEFAULT 'Europe/Moscow',
        cutoff_start           TEXT NOT NULL,
        cutoff_end             TEXT NOT NULL,
        code_sha               TEXT NOT NULL DEFAULT '',
        catalog_digest         TEXT NOT NULL DEFAULT '',
        candidate_digest       TEXT NOT NULL DEFAULT '',
        config_digest          TEXT NOT NULL DEFAULT '',
        formula_version        TEXT NOT NULL DEFAULT '',
        rotation_algorithm     TEXT NOT NULL DEFAULT '',
        mode                   TEXT NOT NULL DEFAULT '',
        status                 TEXT NOT NULL DEFAULT '',
        metrics_json           TEXT NOT NULL DEFAULT '{}',
        created_at             TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ratings_daily_outcome (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id             TEXT NOT NULL,
        canonical_title_id TEXT NOT NULL,
        source_key         TEXT NOT NULL DEFAULT '',
        result             TEXT NOT NULL,
        primary_reason     TEXT NOT NULL DEFAULT '',
        secondary_reasons  TEXT NOT NULL DEFAULT '[]',
        newly_covered      INTEGER NOT NULL DEFAULT 0,
        UNIQUE (run_id, canonical_title_id, source_key)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_rdo_run ON ratings_daily_outcome(run_id)",
    """
    CREATE TABLE IF NOT EXISTS rating_idempotency (
        idempotency_key TEXT PRIMARY KEY,
        payload_digest  TEXT NOT NULL,
        response_json   TEXT NOT NULL,
        created_at      TEXT NOT NULL
    )
    """,
]

# ALTER may fail if column exists on re-apply — handled in upgrade()
DOWN = [
    "DROP TABLE IF EXISTS rating_idempotency",
    "DROP INDEX IF EXISTS ix_rdo_run",
    "DROP TABLE IF EXISTS ratings_daily_outcome",
    "DROP TABLE IF EXISTS ratings_daily_run",
    "DROP TABLE IF EXISTS rating_combined_projection",
    "DROP TABLE IF EXISTS rating_local_aggregate",
    "DROP TABLE IF EXISTS rating_vote_current",
    "DROP INDEX IF EXISTS ix_rve_voter",
    "DROP INDEX IF EXISTS ix_rve_title",
    "DROP TABLE IF EXISTS rating_vote_event",
    "DELETE FROM schema_migrations WHERE version = '0003'",
]


def upgrade(conn: sqlite3.Connection) -> None:
    for stmt in UP:
        try:
            conn.execute(stmt)
        except sqlite3.OperationalError as exc:
            msg = str(exc).lower()
            if "duplicate column" in msg or "already exists" in msg:
                continue
            raise
    conn.execute(
        "INSERT OR REPLACE INTO schema_migrations(version, description, applied_at) VALUES (?,?,?)",
        (VERSION, DESCRIPTION, dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")),
    )
    conn.commit()


def downgrade(conn: sqlite3.Connection) -> None:
    for stmt in DOWN:
        with contextlib.suppress(sqlite3.OperationalError):
            conn.execute(stmt)
    conn.commit()


def applied(conn: sqlite3.Connection) -> bool:
    try:
        row = conn.execute(
            "SELECT 1 FROM schema_migrations WHERE version = ?", (VERSION,)
        ).fetchone()
    except sqlite3.OperationalError:
        return False
    return row is not None
