"""Migration 0004 — source absence / deferred retry (zero-score no-vote).

Isolated+canonical ratings DB only. Append-only absences; does not delete
observations or catalog rows.
"""

from __future__ import annotations

import datetime as dt
import sqlite3

VERSION = "0004"
DESCRIPTION = "rating_source_absence for zero-score/no-vote deferred retry"


UP = [
    """
    CREATE TABLE IF NOT EXISTS rating_source_absence (
        canonical_title_id  TEXT NOT NULL,
        source_key          TEXT NOT NULL,
        external_id         TEXT NOT NULL DEFAULT '',
        reason              TEXT NOT NULL,
        source_url          TEXT NOT NULL DEFAULT '',
        observed_at         TEXT NOT NULL,
        retry_after         TEXT NOT NULL,
        payload_digest      TEXT NOT NULL DEFAULT '',
        details_json        TEXT NOT NULL DEFAULT '{}',
        PRIMARY KEY (canonical_title_id, source_key)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_rsa_retry
        ON rating_source_absence(retry_after)
    """,
]

DOWN = [
    "DROP INDEX IF EXISTS ix_rsa_retry",
    "DROP TABLE IF EXISTS rating_source_absence",
    "DELETE FROM schema_migrations WHERE version = '0004'",
]


def upgrade(conn: sqlite3.Connection) -> None:
    for stmt in UP:
        conn.execute(stmt)
    conn.execute(
        "INSERT OR REPLACE INTO schema_migrations(version, description, applied_at) VALUES (?,?,?)",
        (VERSION, DESCRIPTION, dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")),
    )
    conn.commit()


def applied(conn: sqlite3.Connection) -> bool:
    try:
        row = conn.execute(
            "SELECT 1 FROM schema_migrations WHERE version=?", (VERSION,)
        ).fetchone()
    except sqlite3.OperationalError:
        return False
    return row is not None


def downgrade(conn: sqlite3.Connection) -> None:
    for stmt in DOWN:
        try:
            conn.execute(stmt)
        except sqlite3.OperationalError:
            pass
    conn.commit()
