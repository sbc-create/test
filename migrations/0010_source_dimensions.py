"""Миграция 0010 — покритериальные оценки источника отдельными измерениями.

AMD Online публикует, кроме общей оценки, отдельные оценки сюжета,
персонажей, рисовки и озвучки. Класть их в ту же колонку, что и общую,
нельзя: «9.7 за рисовку» и «9.7 за произведение» — разные утверждения, и
смешав их однажды, различить обратно уже не получится.

Только добавление таблицы. Общая оценка остаётся там же, где была, и
сводная оценка по-прежнему считается только по ней: измерение — не
оценка произведения.
"""

from __future__ import annotations

import contextlib
import sqlite3
import time
from typing import Any

VERSION = "0010"
DESCRIPTION = "unified_source_dimensions — покритериальные оценки источников"

UP: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS unified_source_dimensions (
        title_id         TEXT NOT NULL,
        source_key       TEXT NOT NULL,
        dimension        TEXT NOT NULL,
        label            TEXT NOT NULL DEFAULT '',
        raw_value        TEXT,
        source_scale_max TEXT NOT NULL,
        normalized_value TEXT,
        validation_state TEXT NOT NULL,
        fetched_at       TEXT NOT NULL,
        adapter_version  TEXT NOT NULL DEFAULT '',
        PRIMARY KEY (title_id, source_key, dimension)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_usd_source ON unified_source_dimensions(source_key, dimension)",
    """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version     TEXT PRIMARY KEY,
        description TEXT NOT NULL,
        applied_at  TEXT NOT NULL
    )
    """,
]

DOWN: list[str] = [
    "DROP INDEX IF EXISTS ix_usd_source",
    "DROP TABLE IF EXISTS unified_source_dimensions",
    "DELETE FROM schema_migrations WHERE version = '0010'",
]

OWNED_TABLES: tuple[str, ...] = ("unified_source_dimensions",)


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
        return (
            conn.execute(
                "SELECT 1 FROM schema_migrations WHERE version=?", (VERSION,)
            ).fetchone()
            is not None
        )
    except sqlite3.OperationalError:
        return False
