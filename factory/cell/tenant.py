"""Локальные данные сайта: комментарии, голоса, личности.

Эти данные принадлежат сайту и живут на его сервере. Центр их не хранит и не
нужен для того, чтобы принять новый комментарий: недоступность фабрики, Git или
старого хоста не должна мешать посетителю ответить на чужой отзыв.

Изоляция здесь — не соглашение об именовании. База открывается под конкретный
`site_id`, он же записан внутри базы, и несовпадение останавливает работу до
первого запроса. Подменённый манифест не открывает чужие данные: проверка
сравнивает запрошенный сайт с тем, что записано в самой базе, а не с тем, что
сказал вызывающий.

Снимок снимается через SQLite Online Backup API. Обычное копирование файла
работающей базы даёт снимок в середине транзакции — и восстанавливается он
ровно один раз из трёх, причём всегда не тот, что нужен.

Расположение базы намеренно вне каталога релиза: смена релиза не должна
затрагивать данные, а откат кода — возвращать вчерашние комментарии.
"""
from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

MODERATION_PENDING = "pending"
MODERATION_APPROVED = "approved"
MODERATION_REJECTED = "rejected"
MODERATION_STATES = (MODERATION_PENDING, MODERATION_APPROVED, MODERATION_REJECTED)

VOTE_MIN = 1
VOTE_MAX = 10


class TenantError(RuntimeError):
    pass


class CrossTenantAccess(TenantError):
    """Попытка прочитать или изменить данные другого сайта."""


class InvalidVote(TenantError):
    pass


class WritesFrozen(TenantError):
    """Запись остановлена на время переноса последней дельты.

    Окно короткое и касается только этого сайта. Существует оно ровно затем,
    чтобы два сервера не писали одновременно: одного переключения DNS для этого
    недостаточно — старый адрес живёт в кэшах ещё долго.
    """


def freeze_marker(db_path: Path) -> Path:
    return Path(str(db_path) + ".freeze")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


SCHEMA = """
CREATE TABLE IF NOT EXISTS tenant_identity (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS identities (
    identity_id TEXT PRIMARY KEY,
    site_id     TEXT NOT NULL,
    display_name TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS comments (
    comment_id   TEXT PRIMARY KEY,
    site_id      TEXT NOT NULL,
    title_uuid   TEXT NOT NULL,
    parent_id    TEXT REFERENCES comments(comment_id),
    identity_id  TEXT NOT NULL REFERENCES identities(identity_id),
    body         TEXT NOT NULL,
    status       TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    moderated_by TEXT,
    moderated_at TEXT
);
CREATE INDEX IF NOT EXISTS comments_by_title ON comments(title_uuid, status);
CREATE INDEX IF NOT EXISTS comments_by_parent ON comments(parent_id);

CREATE TABLE IF NOT EXISTS votes (
    site_id     TEXT NOT NULL,
    title_uuid  TEXT NOT NULL,
    identity_id TEXT NOT NULL REFERENCES identities(identity_id),
    score       INTEGER NOT NULL CHECK (score BETWEEN 1 AND 10),
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    PRIMARY KEY (title_uuid, identity_id)
);

CREATE TABLE IF NOT EXISTS audit_local (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id    TEXT NOT NULL,
    action     TEXT NOT NULL,
    subject    TEXT NOT NULL,
    actor      TEXT NOT NULL,
    at         TEXT NOT NULL,
    detail     TEXT
);
"""

#: Таблицы, которые переносятся и сверяются при переезде. Порядок важен: ссылки
#: восстанавливаются после того, на что ссылаются.
TRANSFERABLE_TABLES = ("identities", "comments", "votes", "audit_local")


@dataclass(frozen=True)
class Comment:
    comment_id: str
    site_id: str
    title_uuid: str
    parent_id: str | None
    identity_id: str
    body: str
    status: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class Vote:
    site_id: str
    title_uuid: str
    identity_id: str
    score: int
    created_at: str
    updated_at: str


class TenantStore:
    """Хранилище одного сайта. Другого сайта для него не существует."""

    def __init__(self, site_id: str, path: Path) -> None:
        if not site_id:
            raise TenantError("хранилище без site_id не открывается")
        self.site_id = site_id
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(str(self.path), isolation_level=None,
                                           check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        # WAL: читатель не блокирует писателя. Комментарий принимается, пока
        # страница отдаётся, а не после неё.
        self._connection.execute("PRAGMA journal_mode = WAL")
        self._connection.executescript(SCHEMA)
        self._bind_identity()

    # ------------------------------------------------------------- изоляция
    def _bind_identity(self) -> None:
        row = self._connection.execute(
            "SELECT value FROM tenant_identity WHERE key = 'site_id'").fetchone()
        if row is None:
            self._connection.execute(
                "INSERT INTO tenant_identity (key, value) VALUES ('site_id', ?)",
                (self.site_id,))
            self._connection.execute(
                "INSERT OR REPLACE INTO tenant_identity (key, value) VALUES "
                "('schema_version', ?)", (str(SCHEMA_VERSION),))
            return
        if row["value"] != self.site_id:
            # Тот самый случай подменённого манифеста: имя сайта пришло снаружи,
            # а в базе записано своё. Верим базе.
            raise CrossTenantAccess(
                f"база принадлежит сайту {row['value']}, а открыть её просят как "
                f"{self.site_id}: чужие данные не открываются по названию"
            )

    def _guard(self, site_id: str | None) -> None:
        if site_id is not None and site_id != self.site_id:
            raise CrossTenantAccess(
                f"обращение к сайту {site_id} через хранилище {self.site_id}"
            )

    def _check_not_frozen(self) -> None:
        marker = freeze_marker(self.path)
        if marker.exists():
            raise WritesFrozen(
                f"{self.site_id}: запись остановлена на время переноса "
                f"({marker.read_text(encoding='utf-8').strip()})"
            )

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        self._check_not_frozen()
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            yield self._connection
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        else:
            self._connection.execute("COMMIT")

    def close(self) -> None:
        self._connection.close()

    # ------------------------------------------------------------- личности
    def add_identity(self, identity_id: str, display_name: str, *,
                     site_id: str | None = None) -> str:
        self._guard(site_id)
        with self.transaction() as db:
            db.execute(
                "INSERT OR IGNORE INTO identities (identity_id, site_id, display_name, "
                "created_at) VALUES (?,?,?,?)",
                (identity_id, self.site_id, display_name, utc_now()))
        return identity_id

    def identities(self) -> list[dict[str, Any]]:
        rows = self._connection.execute(
            "SELECT * FROM identities WHERE site_id = ? ORDER BY identity_id",
            (self.site_id,)).fetchall()
        return [dict(r) for r in rows]

    # ---------------------------------------------------------- комментарии
    def add_comment(self, *, title_uuid: str, identity_id: str, body: str,
                    parent_id: str | None = None, site_id: str | None = None,
                    status: str = MODERATION_PENDING,
                    comment_id: str | None = None) -> Comment:
        self._guard(site_id)
        if status not in MODERATION_STATES:
            raise TenantError(f"неизвестный статус модерации: {status}")
        if not body.strip():
            raise TenantError("пустой комментарий не сохраняется")
        now = utc_now()
        cid = comment_id or hashlib.sha256(
            f"{self.site_id}|{title_uuid}|{identity_id}|{now}|{body}".encode()
        ).hexdigest()[:24]
        if parent_id:
            parent = self._connection.execute(
                "SELECT site_id FROM comments WHERE comment_id = ?", (parent_id,)).fetchone()
            if parent is None:
                raise TenantError(f"ответ на несуществующий комментарий {parent_id}")
            if parent["site_id"] != self.site_id:
                raise CrossTenantAccess("ответ на комментарий другого сайта")
        with self.transaction() as db:
            db.execute(
                "INSERT INTO comments (comment_id, site_id, title_uuid, parent_id, "
                "identity_id, body, status, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (cid, self.site_id, title_uuid, parent_id, identity_id, body,
                 status, now, now))
            db.execute(
                "INSERT INTO audit_local (site_id, action, subject, actor, at, detail) "
                "VALUES (?,?,?,?,?,?)",
                (self.site_id, "comment.create", cid, identity_id, now, status))
        return self.comment(cid)

    def edit_comment(self, comment_id: str, *, body: str, actor: str) -> Comment:
        existing = self.comment(comment_id)
        if not body.strip():
            raise TenantError("пустой комментарий не сохраняется")
        now = utc_now()
        with self.transaction() as db:
            db.execute(
                "UPDATE comments SET body = ?, updated_at = ?, status = ? "
                "WHERE comment_id = ? AND site_id = ?",
                (body, now, MODERATION_PENDING, comment_id, self.site_id))
            db.execute(
                "INSERT INTO audit_local (site_id, action, subject, actor, at, detail) "
                "VALUES (?,?,?,?,?,?)",
                (self.site_id, "comment.edit", comment_id, actor, now,
                 f"был статус {existing.status}"))
        return self.comment(comment_id)

    def moderate(self, comment_id: str, *, status: str, actor: str) -> Comment:
        if status not in (MODERATION_APPROVED, MODERATION_REJECTED):
            raise TenantError(f"модерация ставит approved или rejected, не {status}")
        self.comment(comment_id)
        now = utc_now()
        with self.transaction() as db:
            db.execute(
                "UPDATE comments SET status = ?, moderated_by = ?, moderated_at = ?, "
                "updated_at = ? WHERE comment_id = ? AND site_id = ?",
                (status, actor, now, now, comment_id, self.site_id))
            db.execute(
                "INSERT INTO audit_local (site_id, action, subject, actor, at, detail) "
                "VALUES (?,?,?,?,?,?)",
                (self.site_id, "comment.moderate", comment_id, actor, now, status))
        return self.comment(comment_id)

    def comment(self, comment_id: str) -> Comment:
        row = self._connection.execute(
            "SELECT * FROM comments WHERE comment_id = ? AND site_id = ?",
            (comment_id, self.site_id)).fetchone()
        if row is None:
            raise TenantError(f"комментария {comment_id} нет на сайте {self.site_id}")
        return Comment(comment_id=row["comment_id"], site_id=row["site_id"],
                       title_uuid=row["title_uuid"], parent_id=row["parent_id"],
                       identity_id=row["identity_id"], body=row["body"],
                       status=row["status"], created_at=row["created_at"],
                       updated_at=row["updated_at"])

    def comments(self, *, title_uuid: str | None = None, status: str | None = None,
                 site_id: str | None = None) -> list[Comment]:
        self._guard(site_id)
        sql = "SELECT * FROM comments WHERE site_id = ?"
        params: list[Any] = [self.site_id]
        if title_uuid:
            sql += " AND title_uuid = ?"
            params.append(title_uuid)
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY created_at, comment_id"
        rows = self._connection.execute(sql, params).fetchall()
        return [self.comment(r["comment_id"]) for r in rows]

    # ------------------------------------------------------------- голоса
    def vote(self, *, title_uuid: str, identity_id: str, score: int,
             site_id: str | None = None) -> Vote:
        self._guard(site_id)
        if not isinstance(score, int) or isinstance(score, bool):
            raise InvalidVote("оценка — целое число от 1 до 10")
        if not VOTE_MIN <= score <= VOTE_MAX:
            raise InvalidVote(f"оценка {score} вне диапазона {VOTE_MIN}–{VOTE_MAX}")
        now = utc_now()
        with self.transaction() as db:
            db.execute(
                "INSERT INTO votes (site_id, title_uuid, identity_id, score, "
                "created_at, updated_at) VALUES (?,?,?,?,?,?) "
                "ON CONFLICT(title_uuid, identity_id) DO UPDATE SET "
                "score = excluded.score, updated_at = excluded.updated_at",
                (self.site_id, title_uuid, identity_id, score, now, now))
            db.execute(
                "INSERT INTO audit_local (site_id, action, subject, actor, at, detail) "
                "VALUES (?,?,?,?,?,?)",
                (self.site_id, "vote.cast", title_uuid, identity_id, now, str(score)))
        row = self._connection.execute(
            "SELECT * FROM votes WHERE title_uuid = ? AND identity_id = ? AND site_id = ?",
            (title_uuid, identity_id, self.site_id)).fetchone()
        return Vote(site_id=row["site_id"], title_uuid=row["title_uuid"],
                    identity_id=row["identity_id"], score=row["score"],
                    created_at=row["created_at"], updated_at=row["updated_at"])

    def user_rating(self, title_uuid: str) -> dict[str, Any]:
        """Пользовательская оценка сайта. Внешние рейтинги сюда не примешиваются."""
        row = self._connection.execute(
            "SELECT COUNT(*) AS votes, AVG(score) AS average FROM votes "
            "WHERE title_uuid = ? AND site_id = ?",
            (title_uuid, self.site_id)).fetchone()
        return {
            "title_uuid": title_uuid,
            "votes": row["votes"],
            "average": round(row["average"], 2) if row["average"] is not None else None,
            "kind": "user",
        }

    # ------------------------------------------------------------- снимки
    def snapshot(self, destination: Path) -> Path:
        """Согласованный снимок работающей базы через Online Backup API."""
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        target = sqlite3.connect(str(destination))
        try:
            with target:
                self._connection.backup(target)
        finally:
            target.close()
        return destination

    def integrity_ok(self) -> bool:
        row = self._connection.execute("PRAGMA integrity_check").fetchone()
        return row[0] == "ok"

    def row_counts(self) -> dict[str, int]:
        return {
            table: self._connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE site_id = ?",  # noqa: S608
                (self.site_id,)).fetchone()[0]
            for table in TRANSFERABLE_TABLES
        }

    def checksum(self) -> str:
        """Контрольная сумма переносимых данных.

        Считается по значениям, а не по файлу: файл базы отличается побайтно
        после каждого VACUUM, а данные при этом те же, и сравнивать файлы значит
        получать расхождение там, где его нет.
        """
        digest = hashlib.sha256()
        for table in TRANSFERABLE_TABLES:
            columns = [r["name"] for r in self._connection.execute(
                f"PRAGMA table_info({table})").fetchall()]
            # audit_local.seq — автоинкремент; на новой стороне он свой, и
            # включать его в сумму значит гарантировать расхождение.
            columns = [c for c in columns if c != "seq"]
            order = ", ".join(columns)
            rows = self._connection.execute(
                f"SELECT {order} FROM {table} WHERE site_id = ? ORDER BY {order}",  # noqa: S608
                (self.site_id,)).fetchall()
            digest.update(table.encode())
            for row in rows:
                digest.update(repr(tuple(row)).encode())
        return f"sha256:{digest.hexdigest()}"

    def export_rows(self) -> dict[str, list[dict[str, Any]]]:
        """Выгрузка только своего сайта. Чужие строки в пакет не попадают."""
        out: dict[str, list[dict[str, Any]]] = {}
        for table in TRANSFERABLE_TABLES:
            rows = self._connection.execute(
                f"SELECT * FROM {table} WHERE site_id = ?",  # noqa: S608
                (self.site_id,)).fetchall()
            out[table] = [dict(r) for r in rows]
        return out

    def import_rows(self, payload: dict[str, list[dict[str, Any]]], *,
                    expected_site_id: str) -> dict[str, int]:
        """Приём выгрузки. Чужой site_id не принимается даже в одной строке."""
        if expected_site_id != self.site_id:
            raise CrossTenantAccess(
                f"выгрузка объявлена для {expected_site_id}, хранилище — {self.site_id}")
        imported: dict[str, int] = {}
        with self.transaction() as db:
            for table in TRANSFERABLE_TABLES:
                rows = payload.get(table) or []
                count = 0
                for row in rows:
                    if row.get("site_id") != self.site_id:
                        raise CrossTenantAccess(
                            f"в выгрузке строка сайта {row.get('site_id')}, "
                            f"а ставится {self.site_id}")
                    data = {k: v for k, v in row.items() if k != "seq"}
                    cols = ", ".join(data)
                    marks = ", ".join("?" for _ in data)
                    db.execute(
                        f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({marks})",  # noqa: S608
                        tuple(data.values()))
                    count += 1
                imported[table] = count
        return imported


def open_store(site_id: str, path: Path) -> TenantStore:
    return TenantStore(site_id, path)


def restore(snapshot: Path, destination: Path, *, expected_site_id: str) -> TenantStore:
    """Восстановить базу из снимка и убедиться, что это данные нужного сайта."""
    snapshot = Path(snapshot)
    if not snapshot.exists():
        raise TenantError(f"снимка нет: {snapshot}")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(str(snapshot))
    target = sqlite3.connect(str(destination))
    try:
        with target:
            source.backup(target)
    finally:
        source.close()
        target.close()
    store = TenantStore(expected_site_id, destination)
    if not store.integrity_ok():
        raise TenantError(f"восстановленная база {destination} не проходит integrity_check")
    return store
