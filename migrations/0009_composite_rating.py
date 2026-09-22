"""Миграция 0009 — сводная оценка и аудит версии формулы.

Только добавление таблиц. Сводная оценка хранится отдельно от трёх
остальных видов и рядом с версией формулы, которой посчитана: значение
без версии формулы невозможно перепроверить, а «пересчитали по-новому»
и «источник изменился» становятся неразличимы.

Ключ включает ``formula_version``, поэтому новая версия формулы не
затирает предыдущие значения — их можно сравнить, прежде чем
переключать интерфейс.
"""

from __future__ import annotations

import contextlib
import sqlite3
import time
from typing import Any

VERSION = "0009"
DESCRIPTION = "composite_external_rating и аудит версии формулы"

UP: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS unified_composite_ratings (
        title_id         TEXT NOT NULL,
        formula_version  TEXT NOT NULL,
        state            TEXT NOT NULL,
        value            TEXT,
        source_count     INTEGER NOT NULL DEFAULT 0,
        sources_json     TEXT NOT NULL DEFAULT '[]',
        confidence       TEXT NOT NULL DEFAULT 'UNKNOWN',
        freshness_status TEXT NOT NULL DEFAULT 'UNKNOWN',
        calculated_at    TEXT NOT NULL,
        PRIMARY KEY (title_id, formula_version),
        CHECK (source_count >= 0)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_ucr_state ON unified_composite_ratings(state, formula_version)",
    """
    CREATE TABLE IF NOT EXISTS unified_composite_formula_audit (
        audit_id        INTEGER PRIMARY KEY AUTOINCREMENT,
        formula_version TEXT NOT NULL,
        weights_json    TEXT NOT NULL,
        min_sources     INTEGER NOT NULL,
        actor           TEXT NOT NULL,
        rationale       TEXT NOT NULL DEFAULT '',
        created_at      TEXT NOT NULL
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

DOWN: list[str] = [
    "DROP TABLE IF EXISTS unified_composite_formula_audit",
    "DROP INDEX IF EXISTS ix_ucr_state",
    "DROP TABLE IF EXISTS unified_composite_ratings",
    "DELETE FROM schema_migrations WHERE version = '0009'",
]

OWNED_TABLES: tuple[str, ...] = (
    "unified_composite_ratings",
    "unified_composite_formula_audit",
)


def apply(conn: sqlite3.Connection) -> dict[str, Any]:
    started = time.monotonic()
    conn.execute("PRAGMA busy_timeout=10000")
    for stmt in UP:
        conn.execute(stmt)
    row = conn.execute("SELECT 1 FROM schema_migrations WHERE version=?", (VERSION,)).fetchone()
    first_apply = row is None
    if first_apply:
        conn.execute(
            "INSERT INTO schema_migrations(version, description, applied_at) VALUES (?,?,?)",
            (VERSION, DESCRIPTION, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
        )
    conn.commit()
    return {
        "version": VERSION,
        "first_apply": first_apply,
        "destructive": False,
        "duration_ms": int((time.monotonic() - started) * 1000),
        "tables": list(OWNED_TABLES),
    }


def downgrade(conn: sqlite3.Connection) -> dict[str, Any]:
    for stmt in DOWN:
        with contextlib.suppress(sqlite3.OperationalError):
            conn.execute(stmt)
    conn.commit()
    return {"version": VERSION, "rolled_back": True}


def applied(conn: sqlite3.Connection) -> bool:
    try:
        row = conn.execute(
            "SELECT 1 FROM schema_migrations WHERE version=?", (VERSION,)
        ).fetchone()
    except sqlite3.OperationalError:
        return False
    return row is not None
