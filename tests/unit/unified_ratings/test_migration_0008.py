"""Миграция 0008: отдельный счётчик «источник не знает тайтл»."""

from __future__ import annotations

import sqlite3

from factory.unified_ratings.migration_loader import (
    load_all,
    load_migration_0007,
    load_migration_0008,
)


def columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]


def test_column_is_added_once(tmp_path):
    db = tmp_path / "m8.sqlite"
    conn = sqlite3.connect(str(db))
    load_migration_0007().apply(conn)
    first = load_migration_0008().apply(conn)
    assert first["column_added"] is True
    assert "not_found" in columns(conn, "unified_import_runs")

    second = load_migration_0008().apply(conn)
    assert second["first_apply"] is False
    assert second["column_added"] is False
    assert columns(conn, "unified_import_runs").count("not_found") == 1
    conn.close()


def test_downgrade_keeps_collected_counts(tmp_path):
    """Откат снимает отметку, но не выбрасывает уже собранные числа."""
    db = tmp_path / "m8-down.sqlite"
    conn = sqlite3.connect(str(db))
    for module in load_all():
        module.apply(conn)
    conn.execute(
        """INSERT INTO unified_import_runs(run_id, source_key, started_at, status, not_found)
           VALUES ('r1','kitsu','now','OK', 7)"""
    )
    conn.commit()

    result = load_migration_0008().downgrade(conn)
    assert result["column_kept"] is True
    assert load_migration_0008().applied(conn) is False
    assert conn.execute("SELECT not_found FROM unified_import_runs").fetchone()[0] == 7
    conn.close()


def test_existing_rows_default_to_zero(tmp_path):
    db = tmp_path / "m8-default.sqlite"
    conn = sqlite3.connect(str(db))
    load_migration_0007().apply(conn)
    conn.execute(
        "INSERT INTO unified_import_runs(run_id, source_key, started_at, status)"
        " VALUES ('old','anilist','then','OK')"
    )
    conn.commit()
    load_migration_0008().apply(conn)
    assert conn.execute("SELECT not_found FROM unified_import_runs WHERE run_id='old'").fetchone()[0] == 0
    conn.close()


def test_store_reports_schema_only_when_every_migration_is_applied(tmp_path):
    from factory.unified_ratings.store import UnifiedStore

    store = UnifiedStore(tmp_path / "full.sqlite")
    assert store.has_schema() is True
    load_migration_0008().downgrade(store.conn)
    assert store.has_schema() is False, "частично применённая схема не является применённой"
    store.close()
