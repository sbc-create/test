"""Миграция 0007 — единый модуль оценок 1–10.

Только расширение: CREATE TABLE/INDEX IF NOT EXISTS. Ни DROP, ни ALTER, ни
переименования. Существующие таблицы рейтингов и голосов не изменяются, и
старый виджет с gateway продолжают читать ровно те же ``rating_current``,
``community_votes`` и ``community_aggregates``, что и до миграции.

Три вида оценок разнесены по трём независимым таблицам:

* ``unified_external_snapshots`` / ``unified_external_current`` — внешние;
* ``community_votes`` (существующая, Stage 05–08) — пользовательские;
* ``unified_editorial_ratings`` — редакционные.

Общей таблицы «оценка» нет намеренно. Пока у трёх видов одна таблица с
колонкой ``kind``, любая ошибка в ``WHERE`` превращает редакционную оценку в
пользовательскую; при трёх таблицах такой ошибки не существует.

Повторное применение — no-op. Откат ``downgrade`` удаляет только таблицы
этой миграции и не трогает ничего из 0001–0006.
"""

from __future__ import annotations

import contextlib
import sqlite3
import time
from typing import Any

VERSION = "0007"
DESCRIPTION = (
    "unified ratings 1-10: titles, source links, external snapshots, editorial, aggregates"
)

UP: list[str] = [
    # ------------------------------------------------------------------
    # 1. Канонический тайтл
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS unified_titles (
        title_id            TEXT PRIMARY KEY,
        content_kind        TEXT NOT NULL DEFAULT 'UNKNOWN',
        title_ru            TEXT NOT NULL DEFAULT '',
        title_original      TEXT NOT NULL DEFAULT '',
        alt_titles_json     TEXT NOT NULL DEFAULT '[]',
        release_year        INTEGER CHECK (release_year IS NULL OR release_year > 1800),
        season_number       INTEGER CHECK (season_number IS NULL OR season_number >= 0),
        episode_count       INTEGER CHECK (episode_count IS NULL OR episode_count > 0),
        external_ids_json   TEXT NOT NULL DEFAULT '{}',
        catalog_source      TEXT NOT NULL DEFAULT '',
        catalog_revision    TEXT NOT NULL DEFAULT '',
        created_at          TEXT NOT NULL,
        updated_at          TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_ut_year ON unified_titles(release_year)",
    "CREATE INDEX IF NOT EXISTS ix_ut_kind ON unified_titles(content_kind)",
    # Связь канонического тайтла с площадкой. Одна строка — один subject на
    # одном tenant; именно она позволяет голосу с сайта найти title_id, не
    # доверяя tenant, пришедшему из интерфейса.
    """
    CREATE TABLE IF NOT EXISTS unified_title_tenant_map (
        tenant_id     TEXT NOT NULL,
        subject_id    TEXT NOT NULL,
        title_id      TEXT NOT NULL,
        profile_id    TEXT NOT NULL DEFAULT '',
        created_at    TEXT NOT NULL,
        PRIMARY KEY (tenant_id, subject_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_uttm_title ON unified_title_tenant_map(title_id)",

    # ------------------------------------------------------------------
    # 2. Связь с внешними источниками
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS unified_source_links (
        title_id       TEXT NOT NULL,
        source_key     TEXT NOT NULL,
        external_id    TEXT NOT NULL,
        source_url     TEXT NOT NULL DEFAULT '',
        match_method   TEXT NOT NULL,
        confidence     REAL NOT NULL DEFAULT 0.0
                       CHECK (confidence >= 0.0 AND confidence <= 1.0),
        status         TEXT NOT NULL
                       CHECK (status IN ('exact','reviewed','pending','rejected','conflict')),
        verified_by    TEXT NOT NULL DEFAULT '',
        verified_at    TEXT NOT NULL DEFAULT '',
        evidence_json  TEXT NOT NULL DEFAULT '{}',
        created_at     TEXT NOT NULL,
        updated_at     TEXT NOT NULL,
        PRIMARY KEY (title_id, source_key)
    )
    """,
    # Один внешний идентификатор не может принадлежать двум тайтлам среди
    # принятых связей. Отклонённые и конфликтные из ограничения исключены:
    # именно там конкурирующие кандидаты и должны лежать рядом.
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_usl_external_accepted
        ON unified_source_links(source_key, external_id)
        WHERE status IN ('exact','reviewed')
    """,
    "CREATE INDEX IF NOT EXISTS ix_usl_status ON unified_source_links(status, source_key)",

    # ------------------------------------------------------------------
    # 3. Снимок внешнего рейтинга (append-only)
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS unified_external_snapshots (
        snapshot_id        INTEGER PRIMARY KEY AUTOINCREMENT,
        title_id           TEXT NOT NULL,
        source_key         TEXT NOT NULL,
        external_id        TEXT NOT NULL,
        raw_score          TEXT,
        source_scale_min   TEXT NOT NULL,
        source_scale_max   TEXT NOT NULL,
        normalization_formula TEXT NOT NULL,
        normalized_score   TEXT,
        vote_count         INTEGER CHECK (vote_count IS NULL OR vote_count >= 0),
        user_count         INTEGER CHECK (user_count IS NULL OR user_count >= 0),
        source_rating_date TEXT NOT NULL DEFAULT '',
        fetched_at         TEXT NOT NULL,
        source_updated_at  TEXT NOT NULL DEFAULT '',
        adapter_version    TEXT NOT NULL,
        raw_payload_sha256 TEXT NOT NULL,
        content_hash       TEXT NOT NULL,
        validation_state   TEXT NOT NULL,
        rejection_reason   TEXT NOT NULL DEFAULT '',
        provenance_json    TEXT NOT NULL DEFAULT '{}',
        prev_snapshot_id   INTEGER,
        run_id             TEXT NOT NULL DEFAULT '',
        FOREIGN KEY (prev_snapshot_id) REFERENCES unified_external_snapshots(snapshot_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_ues_title_source"
    " ON unified_external_snapshots(title_id, source_key)",
    "CREATE INDEX IF NOT EXISTS ix_ues_run ON unified_external_snapshots(run_id)",
    "CREATE INDEX IF NOT EXISTS ix_ues_content ON unified_external_snapshots(content_hash)",
    # Текущее принятое значение. ``last_checked_at`` отделён от
    # ``fetched_at``: источник, у которого ничего не изменилось, обновляет
    # время проверки и не создаёт новую версию.
    """
    CREATE TABLE IF NOT EXISTS unified_external_current (
        title_id           TEXT NOT NULL,
        source_key         TEXT NOT NULL,
        snapshot_id        INTEGER NOT NULL,
        raw_score          TEXT,
        source_scale_max   TEXT NOT NULL,
        normalized_score   TEXT,
        vote_count         INTEGER,
        user_count         INTEGER,
        content_hash       TEXT NOT NULL,
        validation_state   TEXT NOT NULL,
        fetched_at         TEXT NOT NULL,
        last_checked_at    TEXT NOT NULL,
        unchanged_streak   INTEGER NOT NULL DEFAULT 0,
        provenance_url     TEXT NOT NULL DEFAULT '',
        adapter_version    TEXT NOT NULL DEFAULT '',
        PRIMARY KEY (title_id, source_key),
        FOREIGN KEY (snapshot_id) REFERENCES unified_external_snapshots(snapshot_id)
    )
    """,

    # ------------------------------------------------------------------
    # 4. Редакционная оценка
    # ------------------------------------------------------------------
    # scope_kind global|tenant. Глобальная и площадочная оценки — разные
    # строки: одна не затирает другую, и снятие площадочной не возвращает
    # тайтл к чужому значению незаметно.
    """
    CREATE TABLE IF NOT EXISTS unified_editorial_ratings (
        title_id       TEXT NOT NULL,
        scope_kind     TEXT NOT NULL CHECK (scope_kind IN ('global','tenant')),
        scope_id       TEXT NOT NULL DEFAULT '',
        score          INTEGER CHECK (score IS NULL OR (score >= 1 AND score <= 10)),
        status         TEXT NOT NULL CHECK (status IN ('ACTIVE','WITHDRAWN')),
        author_id      TEXT NOT NULL,
        author_role    TEXT NOT NULL,
        rationale      TEXT NOT NULL DEFAULT '',
        created_at     TEXT NOT NULL,
        updated_at     TEXT NOT NULL,
        withdrawn_at   TEXT NOT NULL DEFAULT '',
        revision       INTEGER NOT NULL DEFAULT 1,
        PRIMARY KEY (title_id, scope_kind, scope_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS unified_editorial_audit (
        audit_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        title_id      TEXT NOT NULL,
        scope_kind    TEXT NOT NULL,
        scope_id      TEXT NOT NULL DEFAULT '',
        action        TEXT NOT NULL CHECK (action IN ('SET','UPDATE','WITHDRAW','RESTORE')),
        old_score     INTEGER,
        new_score     INTEGER,
        actor_id      TEXT NOT NULL,
        actor_role    TEXT NOT NULL,
        rationale     TEXT NOT NULL DEFAULT '',
        batch_id      TEXT NOT NULL DEFAULT '',
        created_at    TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_uea_title ON unified_editorial_audit(title_id, created_at)",
    "CREATE INDEX IF NOT EXISTS ix_uea_actor ON unified_editorial_audit(actor_id, created_at)",

    # ------------------------------------------------------------------
    # 5. Агрегат пользовательских оценок
    # ------------------------------------------------------------------
    # scope tenant|network. Общий сетевой агрегат хранится отдельной
    # строкой, а не выводится сложением площадочных на лету: смешивание
    # двух аудиторий — решение о представлении, и оно должно быть видно
    # в данных, а не спрятано в SELECT.
    """
    CREATE TABLE IF NOT EXISTS unified_user_aggregates (
        scope_kind        TEXT NOT NULL CHECK (scope_kind IN ('tenant','network')),
        scope_id          TEXT NOT NULL DEFAULT '',
        title_id          TEXT NOT NULL,
        dimension         TEXT NOT NULL DEFAULT 'overall',
        vote_sum          INTEGER NOT NULL DEFAULT 0 CHECK (vote_sum >= 0),
        vote_count        INTEGER NOT NULL DEFAULT 0 CHECK (vote_count >= 0),
        average_score     TEXT,
        distribution_json TEXT NOT NULL DEFAULT '{}',
        checksum          TEXT NOT NULL DEFAULT '',
        aggregate_version INTEGER NOT NULL DEFAULT 0,
        recomputed_at     TEXT NOT NULL,
        PRIMARY KEY (scope_kind, scope_id, title_id, dimension),
        CHECK (vote_sum >= vote_count),
        CHECK (vote_sum <= vote_count * 10)
    )
    """,

    # ------------------------------------------------------------------
    # 6. Журнал импорта
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS unified_import_runs (
        run_id            TEXT PRIMARY KEY,
        source_key        TEXT NOT NULL,
        stage             TEXT NOT NULL DEFAULT '',
        started_at        TEXT NOT NULL,
        finished_at       TEXT NOT NULL DEFAULT '',
        status            TEXT NOT NULL,
        dry_run           INTEGER NOT NULL DEFAULT 1,
        cursor_in         TEXT NOT NULL DEFAULT '',
        cursor_out        TEXT NOT NULL DEFAULT '',
        next_checkpoint   TEXT NOT NULL DEFAULT '',
        requested         INTEGER NOT NULL DEFAULT 0,
        received          INTEGER NOT NULL DEFAULT 0,
        exact_match       INTEGER NOT NULL DEFAULT 0,
        pending_match     INTEGER NOT NULL DEFAULT 0,
        rejected          INTEGER NOT NULL DEFAULT 0,
        inserted          INTEGER NOT NULL DEFAULT 0,
        updated           INTEGER NOT NULL DEFAULT 0,
        unchanged         INTEGER NOT NULL DEFAULT 0,
        failed            INTEGER NOT NULL DEFAULT 0,
        rate_limited      INTEGER NOT NULL DEFAULT 0,
        retries           INTEGER NOT NULL DEFAULT 0,
        code_version      TEXT NOT NULL DEFAULT '',
        adapter_version   TEXT NOT NULL DEFAULT '',
        notes             TEXT NOT NULL DEFAULT ''
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_uir_source ON unified_import_runs(source_key, started_at)",

    # ------------------------------------------------------------------
    # 7. Очередь ручной проверки сопоставлений
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS unified_review_queue (
        review_id       INTEGER PRIMARY KEY AUTOINCREMENT,
        title_id        TEXT NOT NULL,
        source_key      TEXT NOT NULL,
        reason_code     TEXT NOT NULL,
        candidates_json TEXT NOT NULL DEFAULT '[]',
        detail          TEXT NOT NULL DEFAULT '',
        status          TEXT NOT NULL DEFAULT 'PENDING'
                        CHECK (status IN ('PENDING','ACCEPTED','REJECTED')),
        created_at      TEXT NOT NULL,
        resolved_at     TEXT NOT NULL DEFAULT '',
        resolved_by     TEXT NOT NULL DEFAULT '',
        run_id          TEXT NOT NULL DEFAULT ''
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_urq_status ON unified_review_queue(status, source_key)",
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_urq_open
        ON unified_review_queue(title_id, source_key, reason_code)
        WHERE status = 'PENDING'
    """,

    # ------------------------------------------------------------------
    # 8. Адаптивное расписание
    # ------------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS unified_schedule_state (
        title_id          TEXT NOT NULL,
        source_key        TEXT NOT NULL,
        tier              TEXT NOT NULL,
        interval_hours    INTEGER NOT NULL,
        next_due_at       TEXT NOT NULL,
        last_checked_at   TEXT NOT NULL DEFAULT '',
        last_changed_at   TEXT NOT NULL DEFAULT '',
        unchanged_streak  INTEGER NOT NULL DEFAULT 0,
        failure_streak    INTEGER NOT NULL DEFAULT 0,
        paused_until      TEXT NOT NULL DEFAULT '',
        pause_reason      TEXT NOT NULL DEFAULT '',
        PRIMARY KEY (title_id, source_key)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_uss_due ON unified_schedule_state(source_key, next_due_at)",

    # ------------------------------------------------------------------
    # 9. Метрики
    # ------------------------------------------------------------------
    # ``state`` отличает измеренный ноль от неизмеренного: MEASURED со
    # значением 0 означает «считали, вышло ноль», UNMEASURED означает
    # «не считали», и в отчёт они попадают по-разному.
    """
    CREATE TABLE IF NOT EXISTS unified_metrics (
        metric_id   INTEGER PRIMARY KEY AUTOINCREMENT,
        metric      TEXT NOT NULL,
        labels_json TEXT NOT NULL DEFAULT '{}',
        state       TEXT NOT NULL CHECK (state IN ('MEASURED','UNMEASURED')),
        value       REAL,
        reason      TEXT NOT NULL DEFAULT '',
        observed_at TEXT NOT NULL,
        run_id      TEXT NOT NULL DEFAULT ''
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_um_metric ON unified_metrics(metric, observed_at)",

    """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version     TEXT PRIMARY KEY,
        description TEXT NOT NULL,
        applied_at  TEXT NOT NULL
    )
    """,
]

DOWN: list[str] = [
    "DROP TABLE IF EXISTS unified_metrics",
    "DROP TABLE IF EXISTS unified_schedule_state",
    "DROP TABLE IF EXISTS unified_review_queue",
    "DROP TABLE IF EXISTS unified_import_runs",
    "DROP TABLE IF EXISTS unified_user_aggregates",
    "DROP TABLE IF EXISTS unified_editorial_audit",
    "DROP TABLE IF EXISTS unified_editorial_ratings",
    "DROP TABLE IF EXISTS unified_external_current",
    "DROP TABLE IF EXISTS unified_external_snapshots",
    "DROP TABLE IF EXISTS unified_source_links",
    "DROP TABLE IF EXISTS unified_title_tenant_map",
    "DROP TABLE IF EXISTS unified_titles",
    "DELETE FROM schema_migrations WHERE version = '0007'",
]

#: Таблицы, создаваемые этой миграцией. Используется тестами отката и
#: проверкой того, что миграция не трогает чужие таблицы.
OWNED_TABLES: tuple[str, ...] = (
    "unified_titles",
    "unified_title_tenant_map",
    "unified_source_links",
    "unified_external_snapshots",
    "unified_external_current",
    "unified_editorial_ratings",
    "unified_editorial_audit",
    "unified_user_aggregates",
    "unified_import_runs",
    "unified_review_queue",
    "unified_schedule_state",
    "unified_metrics",
)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def apply(conn: sqlite3.Connection) -> dict[str, Any]:
    """Применить миграцию. Повторный вызов безопасен и ничего не меняет."""
    started = time.monotonic()
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA foreign_keys=ON")
    for stmt in UP:
        conn.execute(stmt)
    row = conn.execute(
        "SELECT 1 FROM schema_migrations WHERE version = ?", (VERSION,)
    ).fetchone()
    first_apply = row is None
    if first_apply:
        conn.execute(
            "INSERT INTO schema_migrations(version, description, applied_at) VALUES (?,?,?)",
            (VERSION, DESCRIPTION, _now()),
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
    """Удалить только таблицы 0007. Данные 0001–0006 не затрагиваются."""
    conn.execute("PRAGMA busy_timeout=10000")
    for stmt in DOWN:
        # Таблицы могло не быть вовсе — откат неприменённой миграции
        # обязан оставаться успешным, а не падать на первом DROP.
        with contextlib.suppress(sqlite3.OperationalError):
            conn.execute(stmt)
    conn.commit()
    return {"version": VERSION, "rolled_back": True}


def applied(conn: sqlite3.Connection) -> bool:
    try:
        row = conn.execute(
            "SELECT 1 FROM schema_migrations WHERE version = ?", (VERSION,)
        ).fetchone()
    except sqlite3.OperationalError:
        return False
    return row is not None


def apply_path(db_path: str) -> dict[str, Any]:
    conn = sqlite3.connect(db_path, timeout=30.0)
    try:
        return apply(conn)
    finally:
        conn.close()
