"""Migration 0006 — expand-only community ledger + display projection on ratings DB.

Production-safe: CREATE IF NOT EXISTS only. No DROP/ALTER destructive.
Comments tables created dark (flags remain 0). Idempotent replay = no-op.
"""

from __future__ import annotations

import sqlite3
import time
from typing import Any

VERSION = "0006"
DESCRIPTION = "community ratings ledger display projection flags (expand-only)"

# Reuse community schema from Stage01 store
from factory.community.store import SCHEMA_SQL  # noqa: E402

UP_EXTRA = [
    """
    CREATE TABLE IF NOT EXISTS community_feature_flags (
        flag TEXT PRIMARY KEY,
        value INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL DEFAULT ''
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS community_display_projection (
        rating_space_id TEXT NOT NULL,
        subject_id TEXT NOT NULL,
        display_kind TEXT NOT NULL,
        source_key TEXT NOT NULL DEFAULT '',
        score_normalized REAL,
        vote_count INTEGER,
        label TEXT NOT NULL DEFAULT '',
        permission_status TEXT NOT NULL,
        mapping_status TEXT NOT NULL,
        policy_version TEXT NOT NULL,
        lineage_json TEXT NOT NULL DEFAULT '{}',
        artifact_digest TEXT NOT NULL DEFAULT '',
        active INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (rating_space_id, subject_id, display_kind, source_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS community_import_quarantine (
        quarantine_id TEXT PRIMARY KEY,
        source_key TEXT NOT NULL,
        external_id TEXT NOT NULL DEFAULT '',
        reason_code TEXT NOT NULL,
        payload_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS community_audit_log (
        audit_id TEXT PRIMARY KEY,
        actor TEXT NOT NULL,
        action TEXT NOT NULL,
        target_type TEXT NOT NULL,
        target_id TEXT NOT NULL,
        reason_code TEXT NOT NULL DEFAULT '',
        payload_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL
    )
    """,
]

DEFAULT_FLAGS = [
    ("RATINGS_PUBLIC_READ_ANIMEDIA", 0),
    ("RATINGS_PUBLIC_READ_YUMMY", 0),
    ("RATINGS_NATIVE_WRITE_ANIMEDIA", 0),
    ("RATINGS_NATIVE_WRITE_YUMMY", 0),
    ("RATINGS_ADMIN_READ_ENABLED", 0),
    ("RATINGS_ADMIN_MODERATION_WRITE_ENABLED", 0),
    ("COMMENTS_ENABLED", 0),
    ("COMMENTS_PUBLICATION_ENABLED", 0),
    ("COMMENTS_SEO_RENDERING_ENABLED", 0),
    ("COMMENTS_PUBLIC_ROUTES_ENABLED", 0),
    ("COMMENTS_ADMIN_ENABLED", 0),
]


def _busy_timeout(conn: sqlite3.Connection, ms: int = 5000) -> None:
    conn.execute(f"PRAGMA busy_timeout={ms}")


def apply(conn: sqlite3.Connection) -> dict[str, Any]:
    """Apply expand-only migration. Safe to call twice."""
    t0 = time.monotonic()
    _busy_timeout(conn)
    # executescript auto-commits; run DDL outside an explicit txn wrapper
    try:
        conn.executescript(SCHEMA_SQL)
        for stmt in UP_EXTRA:
            conn.execute(stmt)
        row = conn.execute(
            "SELECT 1 FROM schema_migrations WHERE version=?", (VERSION,)
        ).fetchone()
        if not row:
            conn.execute(
                """INSERT INTO schema_migrations(version, description, applied_at)
                   VALUES (?, ?, datetime('now'))""",
                (VERSION, DESCRIPTION),
            )
            first = True
        else:
            first = False
        for flag, value in DEFAULT_FLAGS:
            conn.execute(
                """INSERT OR IGNORE INTO community_feature_flags(flag, value, updated_at)
                   VALUES (?, ?, datetime('now'))""",
                (flag, value),
            )
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        return {
            "version": VERSION,
            "first_apply": first,
            "duration_ms": elapsed_ms,
            "destructive": False,
        }
    except Exception:
        raise


def apply_path(db_path: str) -> dict[str, Any]:
    conn = sqlite3.connect(db_path, timeout=30.0, isolation_level=None)
    try:
        return apply(conn)
    finally:
        conn.close()
