"""Доступ к БД единого модуля оценок.

Соединение на поток, WAL, ``busy_timeout`` и ``BEGIN IMMEDIATE`` на каждой
записи. Последнее важнее, чем кажется: в SQLite отложенная транзакция берёт
блокировку записи в момент первого INSERT, а не BEGIN, поэтому два процесса,
одновременно пересчитывающих агрегат, успевают прочитать одно и то же
состояние и один из них получает SQLITE_BUSY уже после того, как принял
решение на устаревших данных.
"""

from __future__ import annotations

import contextlib
import os
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

DEFAULT_BUSY_TIMEOUT_MS = 10_000


def default_db_path() -> Path:
    """Каноническая production-БД, если она доступна; иначе БД worktree."""
    env = os.environ.get("UNIFIED_RATINGS_DB_PATH")
    if env:
        return Path(env)
    from factory.ratings.prod_db import resolve_canonical_db

    return Path(resolve_canonical_db())


class UnifiedStore:
    """Хранилище единого модуля оценок.

    Экземпляр можно передавать между потоками: соединение создаётся лениво
    для каждого потока отдельно. Общий объект соединения между потоками не
    используется вовсе, поэтому ``check_same_thread`` остаётся включённым и
    продолжает ловить ошибку, а не прятать её.
    """

    def __init__(
        self,
        db_path: Path | str | None = None,
        *,
        busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
        apply_migration: bool = True,
    ) -> None:
        self.db_path = Path(db_path) if db_path is not None else default_db_path()
        self.busy_timeout_ms = busy_timeout_ms
        self._local = threading.local()
        self._migration_lock = threading.Lock()
        if apply_migration:
            self.ensure_schema()

    # ------------------------------------------------------------------
    # соединения
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), timeout=self.busy_timeout_ms / 1000.0)
        conn.row_factory = sqlite3.Row
        conn.execute(f"PRAGMA busy_timeout={self.busy_timeout_ms}")
        conn.execute("PRAGMA foreign_keys=ON")
        # БД может быть открыта только на чтение — режим журнала тогда
        # менять нельзя, и это не повод падать на чтении.
        with contextlib.suppress(sqlite3.OperationalError):
            conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=FULL")
        return conn

    @property
    def conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = self._connect()
            self._local.conn = conn
        return conn

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    # ------------------------------------------------------------------
    # схема
    # ------------------------------------------------------------------

    def ensure_schema(self) -> dict[str, Any]:
        with self._migration_lock:
            from factory.unified_ratings.migration_loader import load_migration_0007

            module = load_migration_0007()
            return module.apply(self.conn)

    def has_schema(self) -> bool:
        from factory.unified_ratings.migration_loader import load_migration_0007

        return load_migration_0007().applied(self.conn)

    # ------------------------------------------------------------------
    # транзакции
    # ------------------------------------------------------------------

    @contextmanager
    def write_tx(self) -> Iterator[sqlite3.Connection]:
        """Немедленная транзакция записи. Откат при любом исключении."""
        conn = self.conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
        except BaseException:
            conn.rollback()
            raise
        else:
            conn.commit()

    # ------------------------------------------------------------------
    # чтение
    # ------------------------------------------------------------------

    def query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        return list(self.conn.execute(sql, params))

    def query_one(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        return self.conn.execute(sql, params).fetchone()

    def count(self, table: str, where: str = "", params: tuple = ()) -> int:
        clause = f" WHERE {where}" if where else ""
        return int(self.conn.execute(f'SELECT COUNT(*) FROM "{table}"{clause}', params).fetchone()[0])

    def table_names(self) -> list[str]:
        return [
            r[0]
            for r in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        ]
