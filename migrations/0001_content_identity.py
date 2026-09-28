"""Миграция 0001 — хранение ContentIdentity.

Применяется ТОЛЬКО к изолированной тестовой базе. Ни production-БД, ни
Redis, ни CMS этой миграцией не затрагиваются: задача запрещает запись в
production, и модуль об этом не знает — он получает путь к базе снаружи и
работает с тем, что дали.

Обратимость обязательна и проверяется тестом. Необратимая миграция — это
решение, которое нельзя отменить, а первое же применение нового резолвера к
живым данным обязано иметь путь назад.

Таблица отдельная, а не колонки в существующей. Причина не в чистоте:
идентичность пересчитывается целиком при смене версии резолвера, и отдельная
таблица позволяет пересчитать её, не трогая каталог, а при откате — просто
удалить, не восстанавливая прежние значения чужих колонок.
"""

from __future__ import annotations

import sqlite3

VERSION = "0001"
DESCRIPTION = "content_identity и rating_discovery"

UP = [
    """
    CREATE TABLE IF NOT EXISTS content_identity (
        internal_entity_id TEXT PRIMARY KEY,
        schema_version     TEXT NOT NULL,
        provider_asset_id  TEXT NOT NULL DEFAULT '',
        content_kind       TEXT NOT NULL DEFAULT 'UNKNOWN',
        is_animation       INTEGER,
        displayed_title    TEXT NOT NULL DEFAULT '',
        original_title     TEXT NOT NULL DEFAULT '',
        alternative_titles TEXT NOT NULL DEFAULT '[]',
        release_year       INTEGER,
        release_date       TEXT NOT NULL DEFAULT '',
        country            TEXT NOT NULL DEFAULT '',
        language           TEXT NOT NULL DEFAULT '',
        -- NULL, а не 0: ноль означает «идёт нисколько» и уходит в разметку
        -- как PT0M. Ограничение делает подмену невозможной, а не осуждаемой.
        duration           INTEGER CHECK (duration IS NULL OR duration > 0),
        episode_count      INTEGER CHECK (episode_count IS NULL OR episode_count > 0),
        season_number      INTEGER,
        external_ids       TEXT NOT NULL DEFAULT '{}',
        source_refs        TEXT NOT NULL DEFAULT '[]',
        identity_status    TEXT NOT NULL,
        mapping_method     TEXT NOT NULL,
        mapping_confidence REAL NOT NULL DEFAULT 0.0,
        conflict_state     TEXT NOT NULL DEFAULT '[]',
        resolved_at        TEXT NOT NULL DEFAULT '',
        payload_hash       TEXT NOT NULL DEFAULT '',
        resolver_version   TEXT NOT NULL DEFAULT ''
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_ci_kind ON content_identity(content_kind)",
    "CREATE INDEX IF NOT EXISTS ix_ci_status ON content_identity(identity_status)",
    "CREATE INDEX IF NOT EXISTS ix_ci_asset ON content_identity(provider_asset_id)",
    """
    CREATE TABLE IF NOT EXISTS rating_discovery (
        internal_entity_id     TEXT PRIMARY KEY,
        external_source        TEXT NOT NULL DEFAULT '',
        external_entity_id     TEXT NOT NULL DEFAULT '',
        rating_eligibility     TEXT NOT NULL,
        rating_state           TEXT NOT NULL,
        numeric_rating_present INTEGER NOT NULL DEFAULT 0,
        vote_count_present     INTEGER NOT NULL DEFAULT 0,
        captured_at            TEXT NOT NULL DEFAULT '',
        blocker                TEXT NOT NULL DEFAULT '',
        recommended_next_source TEXT NOT NULL DEFAULT ''
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_rd_state ON rating_discovery(rating_state)",
    """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version     TEXT PRIMARY KEY,
        description TEXT NOT NULL,
        applied_at  TEXT NOT NULL
    )
    """,
]

DOWN = [
    "DROP INDEX IF EXISTS ix_rd_state",
    "DROP TABLE IF EXISTS rating_discovery",
    "DROP INDEX IF EXISTS ix_ci_asset",
    "DROP INDEX IF EXISTS ix_ci_status",
    "DROP INDEX IF EXISTS ix_ci_kind",
    "DROP TABLE IF EXISTS content_identity",
    "DELETE FROM schema_migrations WHERE version = '0001'",
]


def upgrade(conn: sqlite3.Connection) -> None:
    import datetime as dt

    for запрос in UP:
        conn.execute(запрос)
    conn.execute(
        "INSERT OR REPLACE INTO schema_migrations(version, description, applied_at)"
        " VALUES (?,?,?)",
        (VERSION, DESCRIPTION, dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")),
    )
    conn.commit()


def downgrade(conn: sqlite3.Connection) -> None:
    for запрос in DOWN:
        conn.execute(запрос)
    conn.commit()


def applied(conn: sqlite3.Connection) -> bool:
    try:
        строка = conn.execute(
            "SELECT 1 FROM schema_migrations WHERE version = ?", (VERSION,)
        ).fetchone()
    except sqlite3.OperationalError:
        return False
    return строка is not None


def upsert_identity(conn: sqlite3.Connection, identity) -> None:
    """Запись идентичности. Повторный вызов не создаёт дубль — по ключу."""
    import json

    d = identity.as_dict()
    conn.execute(
        """INSERT INTO content_identity (
            internal_entity_id, schema_version, provider_asset_id, content_kind,
            is_animation, displayed_title, original_title, alternative_titles,
            release_year, release_date, country, language, duration,
            episode_count, season_number, external_ids, source_refs,
            identity_status, mapping_method, mapping_confidence, conflict_state,
            resolved_at, payload_hash, resolver_version)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(internal_entity_id) DO UPDATE SET
            content_kind=excluded.content_kind,
            is_animation=excluded.is_animation,
            displayed_title=excluded.displayed_title,
            release_year=excluded.release_year,
            duration=excluded.duration,
            external_ids=excluded.external_ids,
            identity_status=excluded.identity_status,
            mapping_method=excluded.mapping_method,
            mapping_confidence=excluded.mapping_confidence,
            conflict_state=excluded.conflict_state,
            resolved_at=excluded.resolved_at,
            payload_hash=excluded.payload_hash,
            resolver_version=excluded.resolver_version""",
        (
            d["internalEntityId"],
            d["schemaVersion"],
            d["providerAssetId"],
            d["contentKind"],
            None if d["isAnimation"] is None else int(d["isAnimation"]),
            d["displayedTitle"],
            d["originalTitle"],
            json.dumps(d["alternativeTitles"], ensure_ascii=False),
            d["releaseYear"],
            d["releaseDate"],
            d["country"],
            d["language"],
            d["duration"],
            d["episodeCount"],
            d["seasonNumber"],
            json.dumps(d["externalIds"], ensure_ascii=False),
            json.dumps(d["sourceRefs"], ensure_ascii=False),
            d["identityStatus"],
            d["mappingMethod"],
            d["mappingConfidence"],
            json.dumps(d["conflictState"], ensure_ascii=False),
            d["resolvedAt"],
            d["payloadHash"],
            d["resolverVersion"],
        ),
    )
