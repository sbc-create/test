"""Миграция 0008 — отделить «источник не знает тайтл» от отказа.

``failed`` означало две разные вещи сразу: источник не ответил и источник
ответил «такого тайтла у меня нет». Первое — отказ, который должен
останавливать переход к массовому сбору; второе — обычный и ожидаемый
исход, у Kitsu он случается на каждом сотом тайтле. Пока они считались
вместе, один не найденный тайтл ронял ворота источника целиком.

Только добавление колонки. Существующие строки получают 0 — и это
честно: в них отсутствие тайтла действительно учтено в ``failed``, а
переписывать задним числом то, чего мы не измеряли, нельзя.
"""

from __future__ import annotations

import sqlite3
import time
from typing import Any

VERSION = "0008"
DESCRIPTION = "unified_import_runs.not_found — отдельный счётчик отсутствия тайтла у источника"

COLUMN = "not_found"
TABLE = "unified_import_runs"


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row[1] == column for row in rows)


def apply(conn: sqlite3.Connection) -> dict[str, Any]:
    started = time.monotonic()
    conn.execute("PRAGMA busy_timeout=10000")
    added = False
    if not _has_column(conn, TABLE, COLUMN):
        conn.execute(f"ALTER TABLE {TABLE} ADD COLUMN {COLUMN} INTEGER NOT NULL DEFAULT 0")
        added = True
    row = conn.execute(
        "SELECT 1 FROM schema_migrations WHERE version = ?", (VERSION,)
    ).fetchone()
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
        "column_added": added,
        "destructive": False,
        "duration_ms": int((time.monotonic() - started) * 1000),
    }


def applied(conn: sqlite3.Connection) -> bool:
    try:
        row = conn.execute(
            "SELECT 1 FROM schema_migrations WHERE version = ?", (VERSION,)
        ).fetchone()
    except sqlite3.OperationalError:
        return False
    return row is not None


def downgrade(conn: sqlite3.Connection) -> dict[str, Any]:
    """Колонка не удаляется.

    SQLite умеет ``DROP COLUMN`` начиная с 3.35, но снятие колонки со
    счётчиком означает потерю уже собранных значений, а откат этой
    миграции нужен только чтобы вернуться к прежнему коду — он колонку
    просто не читает. Поэтому откат снимает отметку и оставляет данные.
    """
    conn.execute("DELETE FROM schema_migrations WHERE version = ?", (VERSION,))
    conn.commit()
    return {"version": VERSION, "rolled_back": True, "column_kept": True}
