"""Migration 0005 — community ratings ledger + comments foundation.

ISOLATED / owner-gated only. Do NOT apply to production ratings.sqlite
without exact owner approval (site, artifact SHA, migration digest,
backup/restore path, change window).
"""

from __future__ import annotations

import sqlite3

VERSION = "0005"
DESCRIPTION = "community ratings ledger and comments foundation (dark)"

# Schema lives in factory.community.store.SCHEMA_SQL — apply via CommunityStore
# for isolated DBs. This module records migration metadata only when explicitly run.


UP_META = [
    """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version TEXT PRIMARY KEY,
        description TEXT NOT NULL,
        applied_at TEXT NOT NULL
    )
    """,
]


def apply_isolated(conn: sqlite3.Connection) -> dict:
    """Apply community schema to an isolated connection (not production)."""
    from factory.community.store import SCHEMA_SQL

    conn.executescript(SCHEMA_SQL)
    for stmt in UP_META:
        conn.execute(stmt)
    conn.execute(
        """INSERT OR REPLACE INTO schema_migrations(version, description, applied_at)
           VALUES (?, ?, datetime('now'))""",
        (VERSION, DESCRIPTION),
    )
    conn.execute(
        """INSERT OR REPLACE INTO community_schema_meta(key, value)
           VALUES ('migration', ?)""",
        (VERSION,),
    )
    return {"version": VERSION, "applied": True, "production": False}


def digest() -> str:
    import hashlib

    from factory.community.store import SCHEMA_SQL

    return hashlib.sha256((VERSION + SCHEMA_SQL).encode()).hexdigest()
