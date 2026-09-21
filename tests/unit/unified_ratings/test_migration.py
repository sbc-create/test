"""Миграция 0007: только расширение, повторяемость, обратимость.

Проверка идёт на копии реальной production-схемы: миграция, проверенная
на пустой базе, ничего не говорит о базе, в которой уже лежат данные и
работает виджет.
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from factory.unified_ratings.migration_loader import load_migration_0007
from factory.unified_ratings.store import UnifiedStore

PRODUCTION_DB = Path("/srv/site-factory/repo/var/ratings/ratings.sqlite")

#: Таблицы, от которых зависят работающий gateway и подготовленный 1% canary.
CANARY_TABLES = (
    "community_votes",
    "community_vote_events",
    "community_aggregates",
    "community_feature_flags",
    "community_display_projection",
    "rating_current",
    "rating_observations",
    "title_source_mappings",
    "rating_sources",
)


@pytest.fixture
def migration():
    return load_migration_0007()


@pytest.fixture
def production_copy(tmp_path: Path) -> Path:
    """Копия боевой базы, приведённая к состоянию «до 0007».

    Оригинал открывается только на чтение. На копии выполняется откат
    0007, потому что боевая база могла быть уже мигрирована, и тест,
    который это предполагает, перестаёт проверять миграцию ровно после
    первого успешного применения — а проверять её нужно и на базе, где
    её ещё нет, и на базе, где она уже есть.
    """
    if not PRODUCTION_DB.is_file():
        pytest.skip("production ratings.sqlite недоступна в этом окружении")
    destination = tmp_path / "production_copy.sqlite"
    source = sqlite3.connect(f"file:{PRODUCTION_DB}?mode=ro", uri=True)
    try:
        target = sqlite3.connect(str(destination))
        with target:
            source.backup(target)
        target.close()
    finally:
        source.close()
    conn = sqlite3.connect(str(destination))
    load_migration_0007().downgrade(conn)
    conn.close()
    return destination


def test_applying_to_an_already_migrated_production_copy_changes_nothing(
    production_copy, migration
):
    """Повторное применение на боевой схеме — no-op, а не ошибка."""
    conn = sqlite3.connect(str(production_copy))
    migration.apply(conn)
    conn.close()
    before = table_names(production_copy)
    counts_before = row_counts(production_copy, CANARY_TABLES)

    conn = sqlite3.connect(str(production_copy))
    second = migration.apply(conn)
    conn.close()

    assert second["first_apply"] is False
    assert table_names(production_copy) == before
    assert row_counts(production_copy, CANARY_TABLES) == counts_before


def table_names(path: Path) -> set[str]:
    conn = sqlite3.connect(str(path))
    try:
        return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()


def row_counts(path: Path, tables: tuple[str, ...]) -> dict[str, int]:
    conn = sqlite3.connect(str(path))
    try:
        out = {}
        for table in tables:
            try:
                out[table] = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            except sqlite3.OperationalError:
                out[table] = -1
        return out
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# применение
# ---------------------------------------------------------------------------


def test_migration_creates_every_declared_table(tmp_path, migration):
    db = tmp_path / "fresh.sqlite"
    conn = sqlite3.connect(str(db))
    result = migration.apply(conn)
    conn.close()
    assert result["first_apply"] is True
    assert result["destructive"] is False
    created = table_names(db)
    for table in migration.OWNED_TABLES:
        assert table in created


def test_reapplying_the_migration_is_a_no_op(tmp_path, migration):
    db = tmp_path / "twice.sqlite"
    conn = sqlite3.connect(str(db))
    migration.apply(conn)
    before = table_names(db)
    second = migration.apply(conn)
    conn.close()
    assert second["first_apply"] is False
    assert table_names(db) == before


def test_migration_is_recorded_in_schema_migrations(tmp_path, migration):
    db = tmp_path / "recorded.sqlite"
    conn = sqlite3.connect(str(db))
    migration.apply(conn)
    row = conn.execute("SELECT * FROM schema_migrations WHERE version='0007'").fetchone()
    conn.close()
    assert row is not None


# ---------------------------------------------------------------------------
# откат
# ---------------------------------------------------------------------------


def test_downgrade_removes_only_its_own_tables(tmp_path, migration):
    db = tmp_path / "rollback.sqlite"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE somebody_elses (id INTEGER PRIMARY KEY)")
    conn.execute("INSERT INTO somebody_elses(id) VALUES (1)")
    conn.commit()
    migration.apply(conn)
    migration.downgrade(conn)
    remaining = table_names(db)
    for table in migration.OWNED_TABLES:
        assert table not in remaining
    assert "somebody_elses" in remaining
    assert conn.execute("SELECT COUNT(*) FROM somebody_elses").fetchone()[0] == 1
    assert migration.applied(conn) is False
    conn.close()


def test_downgrade_of_an_unapplied_migration_does_not_raise(tmp_path, migration):
    conn = sqlite3.connect(str(tmp_path / "never.sqlite"))
    migration.downgrade(conn)
    conn.close()


def test_apply_downgrade_apply_cycle_is_stable(tmp_path, migration):
    db = tmp_path / "cycle.sqlite"
    conn = sqlite3.connect(str(db))
    migration.apply(conn)
    first = table_names(db)
    migration.downgrade(conn)
    migration.apply(conn)
    assert table_names(db) == first
    conn.close()


# ---------------------------------------------------------------------------
# на копии production
# ---------------------------------------------------------------------------


def test_migration_on_a_production_copy_adds_only_new_tables(production_copy, migration):
    before = table_names(production_copy)
    counts_before = row_counts(production_copy, CANARY_TABLES)

    conn = sqlite3.connect(str(production_copy))
    migration.apply(conn)
    conn.close()

    after = table_names(production_copy)
    assert before <= after, "миграция удалила существующую таблицу"
    assert after - before == set(migration.OWNED_TABLES)
    assert row_counts(production_copy, CANARY_TABLES) == counts_before, (
        "миграция изменила количество строк в таблицах работающего виджета"
    )


def test_rollback_on_a_production_copy_restores_the_previous_shape(production_copy, migration):
    before = table_names(production_copy)
    counts_before = row_counts(production_copy, CANARY_TABLES)

    conn = sqlite3.connect(str(production_copy))
    migration.apply(conn)
    migration.downgrade(conn)
    conn.close()

    assert table_names(production_copy) == before
    assert row_counts(production_copy, CANARY_TABLES) == counts_before


def test_existing_canary_queries_still_work_after_the_migration(production_copy, migration):
    """Старый gateway читает те же таблицы теми же запросами."""
    conn = sqlite3.connect(str(production_copy))
    conn.row_factory = sqlite3.Row
    baseline = {
        "flags": conn.execute("SELECT flag, value FROM community_feature_flags").fetchall(),
        "aggregates": conn.execute(
            "SELECT rating_space_id, subject_id, vote_sum, vote_count FROM community_aggregates"
        ).fetchall(),
        "current": conn.execute(
            "SELECT canonical_title_id, source_key, normalized_score FROM rating_current"
        ).fetchall(),
    }
    migration.apply(conn)
    after = {
        "flags": conn.execute("SELECT flag, value FROM community_feature_flags").fetchall(),
        "aggregates": conn.execute(
            "SELECT rating_space_id, subject_id, vote_sum, vote_count FROM community_aggregates"
        ).fetchall(),
        "current": conn.execute(
            "SELECT canonical_title_id, source_key, normalized_score FROM rating_current"
        ).fetchall(),
    }
    conn.close()
    for key in baseline:
        assert [tuple(r) for r in baseline[key]] == [tuple(r) for r in after[key]], (
            f"запрос старого gateway к {key} после миграции вернул другое"
        )


def test_backup_restores_byte_identical(tmp_path, production_copy):
    """Бэкап, из которого нельзя восстановиться, бэкапом не является."""
    backup = tmp_path / "backup.sqlite"
    shutil.copy2(production_copy, backup)
    conn = sqlite3.connect(str(production_copy))
    load_migration_0007().apply(conn)
    conn.close()
    assert backup.read_bytes() != production_copy.read_bytes()

    restored = tmp_path / "restored.sqlite"
    shutil.copy2(backup, restored)
    assert restored.read_bytes() == backup.read_bytes()
    conn = sqlite3.connect(str(restored))
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    conn.close()
    assert integrity == "ok"


# ---------------------------------------------------------------------------
# ограничения схемы
# ---------------------------------------------------------------------------


def test_schema_refuses_an_editorial_score_outside_one_to_ten(store):
    with pytest.raises(sqlite3.IntegrityError), store.write_tx() as conn:
        conn.execute(
                """INSERT INTO unified_editorial_ratings(
                       title_id, scope_kind, scope_id, score, status, author_id, author_role,
                       created_at, updated_at)
                   VALUES ('nova:x','global','',11,'ACTIVE','a','content_editor','now','now')"""
            )


def test_schema_refuses_an_impossible_aggregate(store):
    with pytest.raises(sqlite3.IntegrityError), store.write_tx() as conn:
        conn.execute(
                """INSERT INTO unified_user_aggregates(
                       scope_kind, scope_id, title_id, dimension, vote_sum, vote_count,
                       recomputed_at)
                   VALUES ('tenant','yummy','nova:x','overall', 500, 10, 'now')"""
            )


def test_schema_refuses_an_unknown_link_status(store):
    with pytest.raises(sqlite3.IntegrityError), store.write_tx() as conn:
        conn.execute(
                """INSERT INTO unified_source_links(
                       title_id, source_key, external_id, match_method, confidence, status,
                       created_at, updated_at)
                   VALUES ('nova:x','anilist','1','exact_external_id',1.0,'probably','n','n')"""
            )


def test_one_external_id_cannot_be_accepted_for_two_titles(store):
    with store.write_tx() as conn:
        conn.execute(
            """INSERT INTO unified_source_links(
                   title_id, source_key, external_id, match_method, confidence, status,
                   created_at, updated_at)
               VALUES ('nova:a','anilist','1','exact_external_id',1.0,'exact','n','n')"""
        )
    with pytest.raises(sqlite3.IntegrityError), store.write_tx() as conn:
        conn.execute(
                """INSERT INTO unified_source_links(
                       title_id, source_key, external_id, match_method, confidence, status,
                       created_at, updated_at)
                   VALUES ('nova:b','anilist','1','exact_external_id',1.0,'exact','n','n')"""
            )


def test_competing_candidates_may_coexist_while_unresolved(store):
    """Ограничение уникальности не мешает конфликту лежать в очереди."""
    with store.write_tx() as conn:
        conn.execute(
            """INSERT INTO unified_source_links(
                   title_id, source_key, external_id, match_method, confidence, status,
                   created_at, updated_at)
               VALUES ('nova:a','anilist','7','exact_external_id',0.0,'conflict','n','n')"""
        )
        conn.execute(
            """INSERT INTO unified_source_links(
                   title_id, source_key, external_id, match_method, confidence, status,
                   created_at, updated_at)
               VALUES ('nova:b','anilist','7','fuzzy_candidate',0.9,'pending','n','n')"""
        )
    assert store.count("unified_source_links") == 2


def test_store_never_silently_targets_production(monkeypatch, tmp_path):
    """Путь к БД передаётся явно; подстановки по умолчанию в тестах нет."""
    monkeypatch.setenv("UNIFIED_RATINGS_DB_PATH", str(tmp_path / "explicit.sqlite"))
    from factory.unified_ratings.store import default_db_path

    assert default_db_path() == tmp_path / "explicit.sqlite"
    store = UnifiedStore(tmp_path / "explicit.sqlite")
    assert store.db_path != PRODUCTION_DB
    store.close()
