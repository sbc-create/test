"""Миграция 0007 — схема общего модуля комментариев.

Применяется ТОЛЬКО к изолированной тестовой базе. Production-миграция в этой
задаче запрещена, и модуль об этом не знает: он получает путь к базе снаружи
и работает с тем, что дали.

Почему отдельные таблицы, а не колонки в community_*. Комментарии и рейтинги —
разные продукты: у них разные флаги, разные kill switch, разные сроки выката и
разные последствия отказа. Общая таблица связала бы их инцидентами: остановка
комментариев гасила бы рейтинги, а миграция рейтингов блокировала бы запись
комментариев. Префикс cp_ и отдельный файл базы делают эту связь невозможной,
а не маловероятной.

Обратимость обязательна и проверяется тестом: DOWN снимает ровно то, что
поставил UP, и applied() после downgrade возвращает False.
"""

from __future__ import annotations

import datetime as dt
import sqlite3

from factory.comments_platform.schema import DOWN as SCHEMA_DOWN
from factory.comments_platform.schema import UP as SCHEMA_UP

VERSION = "0007"
DESCRIPTION = "shared comments platform schema (tenant-scoped, dark)"

UP = list(SCHEMA_UP)
DOWN = list(SCHEMA_DOWN) + ["DELETE FROM cp_schema_migrations WHERE version = '0007'"]


def upgrade(conn: sqlite3.Connection) -> None:
    for statement in UP:
        conn.execute(statement)
    conn.execute(
        "INSERT OR REPLACE INTO cp_schema_migrations(version, description, applied_at)"
        " VALUES (?,?,?)",
        (
            VERSION,
            DESCRIPTION,
            dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        ),
    )
    conn.commit()


def downgrade(conn: sqlite3.Connection) -> None:
    # Порядок в DOWN уже обратный: дети раньше родителей. Внешние ключи при
    # этом отключать не нужно, и отключать их не следует — если DROP падает на
    # ссылке, значит порядок неверен, и это дефект миграции, а не помеха.
    for statement in DOWN:
        conn.execute(statement)
    conn.commit()


def applied(conn: sqlite3.Connection) -> bool:
    try:
        row = conn.execute(
            "SELECT 1 FROM cp_schema_migrations WHERE version = ?", (VERSION,)
        ).fetchone()
    except sqlite3.OperationalError:
        return False
    return row is not None
