"""Собственное хранилище food-daily: исходные записи, факты, материалы,
версии, задания, журнал. Отдельный файл SQLite только этого сайта —
никакой общей таблицы с другими сайтами, поэтому site_id здесь не
единственная граница изоляции, а дополнительная проверка.

Инварианты:
* версия материала неизменяема; правка — новая версия с parent_version;
* запись версии с устаревшей базой → VersionConflict (оптимистичная блокировка);
* повтор задания с тем же idempotency_key возвращает прежнее задание;
* откат — новая версия, равная по содержимому выбранной старой, а не удаление.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

SITE_ID = "food-daily"
SCHEMA_VERSION = 1

DDL = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sources (
  host TEXT PRIMARY KEY, base_url TEXT NOT NULL, terms_url TEXT, terms_status TEXT NOT NULL,
  terms_note TEXT, retention_days INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS records (
  record_id TEXT PRIMARY KEY, site_id TEXT NOT NULL, host TEXT NOT NULL, source_url TEXT NOT NULL UNIQUE,
  final_url TEXT, canonical_url TEXT, http_status INTEGER, fetched_at TEXT NOT NULL,
  content_hash TEXT, parser_version TEXT, extracted_with TEXT, complete INTEGER NOT NULL DEFAULT 0,
  facts_json TEXT, remarks_json TEXT NOT NULL DEFAULT '[]', private_path TEXT, retention_until TEXT,
  dedupe_key TEXT, status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS content (
  content_id TEXT PRIMARY KEY, site_id TEXT NOT NULL, kind TEXT NOT NULL, slug TEXT NOT NULL UNIQUE,
  dedupe_key TEXT NOT NULL UNIQUE, current_version INTEGER NOT NULL DEFAULT 0,
  review_status TEXT NOT NULL, reviewer TEXT, cooking_status TEXT NOT NULL,
  publish_status TEXT NOT NULL, created_at TEXT NOT NULL, published_at TEXT, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS versions (
  content_id TEXT NOT NULL, recipe_version INTEGER NOT NULL, schema_version INTEGER NOT NULL,
  parent_version INTEGER, payload_json TEXT NOT NULL, payload_hash TEXT NOT NULL,
  source_ids_json TEXT NOT NULL, producer_json TEXT NOT NULL, created_at TEXT NOT NULL,
  created_by TEXT NOT NULL, reason TEXT NOT NULL,
  PRIMARY KEY (content_id, recipe_version)
);
CREATE TABLE IF NOT EXISTS jobs (
  job_id TEXT PRIMARY KEY, site_id TEXT NOT NULL, kind TEXT NOT NULL, content_id TEXT,
  dedupe_key TEXT NOT NULL, idempotency_key TEXT NOT NULL UNIQUE, base_version INTEGER,
  input_hash TEXT NOT NULL, status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, export_path TEXT, response_hash TEXT,
  error TEXT, cost_json TEXT
);
CREATE TABLE IF NOT EXISTS media (
  media_id TEXT PRIMARY KEY, site_id TEXT NOT NULL, content_id TEXT NOT NULL, recipe_version INTEGER NOT NULL,
  kind TEXT NOT NULL, status TEXT NOT NULL, provider TEXT, model TEXT, provider_job_id TEXT,
  rights_json TEXT NOT NULL, cost_json TEXT, path TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  note TEXT
);
CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL,
  content_id TEXT, recipe_version INTEGER, detail_json TEXT NOT NULL
);
"""

REVIEW = ("ai_draft", "editor_approved", "editor_rejected")
COOKING = ("not_cooked", "cooked_by_editor")
PUBLISH = ("hidden", "preview", "published")


class VersionConflict(RuntimeError):
    pass


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(self.path.parent, 0o700)
        self.db = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript(DDL)
        self.db.execute("INSERT OR IGNORE INTO meta VALUES ('site_id', ?)", (SITE_ID,))
        self.db.execute("INSERT OR IGNORE INTO meta VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))
        owner = self.db.execute("SELECT value FROM meta WHERE key='site_id'").fetchone()[0]
        if owner != SITE_ID:
            raise PermissionError(f"хранилище принадлежит сайту {owner!r}, а не {SITE_ID!r}")

    @contextmanager
    def tx(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield self.db
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def audit(self, actor: str, action: str, *, content_id=None, version=None, **detail) -> None:
        self.db.execute(
            "INSERT INTO audit (at, actor, action, content_id, recipe_version, detail_json) VALUES (?,?,?,?,?,?)",
            (now(), actor, action, content_id, version, json.dumps(detail, ensure_ascii=False)),
        )

    # ---- материалы и версии ------------------------------------------
    def ensure_content(self, *, content_id: str, slug: str, dedupe_key: str, kind: str = "recipe") -> sqlite3.Row:
        row = self.db.execute("SELECT * FROM content WHERE dedupe_key=?", (dedupe_key,)).fetchone()
        if row:
            return row
        t = now()
        self.db.execute(
            "INSERT INTO content VALUES (?,?,?,?,?,0,'ai_draft',NULL,'not_cooked','hidden',?,NULL,?)",
            (content_id, SITE_ID, kind, slug, dedupe_key, t, t),
        )
        return self.db.execute("SELECT * FROM content WHERE content_id=?", (content_id,)).fetchone()

    def add_version(
        self,
        content_id: str,
        payload: dict,
        *,
        base_version: int,
        source_ids: list[str],
        producer: dict,
        actor: str,
        reason: str,
    ) -> int:
        """Новая версия при совпадении базы; иначе VersionConflict. Тот же
        payload поверх текущей версии — no-op (возвращает текущую)."""
        with self.tx():
            row = self.db.execute("SELECT current_version FROM content WHERE content_id=?", (content_id,)).fetchone()
            if row is None:
                raise KeyError(content_id)
            cur = row["current_version"]
            h = digest(payload)
            if cur:
                last = self.db.execute(
                    "SELECT payload_hash FROM versions WHERE content_id=? AND recipe_version=?",
                    (content_id, cur),
                ).fetchone()
                if last and last["payload_hash"] == h:
                    return cur
            if base_version != cur:
                conflict = cur
            else:
                conflict = None
                new = cur + 1
                self.db.execute(
                    "INSERT INTO versions VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        content_id,
                        new,
                        SCHEMA_VERSION,
                        cur or None,
                        json.dumps(payload, ensure_ascii=False),
                        h,
                        json.dumps(source_ids),
                        json.dumps(producer, ensure_ascii=False),
                        now(),
                        actor,
                        reason,
                    ),
                )
                # любая новая версия снимает редакторское одобрение: проверялась другая
                self.db.execute(
                    "UPDATE content SET current_version=?, review_status='ai_draft', reviewer=NULL, "
                    "updated_at=? WHERE content_id=?",
                    (new, now(), content_id),
                )
                self.audit(
                    actor,
                    "version_added",
                    content_id=content_id,
                    version=new,
                    reason=reason,
                    payload_hash=h,
                )
        if conflict is not None:
            # журнал конфликта пишется ВНЕ отменённой транзакции, иначе откат стирает и его
            self.audit(
                actor,
                "version_conflict",
                content_id=content_id,
                version=conflict,
                base_version=base_version,
            )
            raise VersionConflict(f"{content_id}: база {base_version}, текущая {conflict}")
        return new

    def rollback(self, content_id: str, to_version: int, *, actor: str) -> int:
        old = self.db.execute(
            "SELECT * FROM versions WHERE content_id=? AND recipe_version=?",
            (content_id, to_version),
        ).fetchone()
        if not old:
            raise KeyError(f"{content_id} v{to_version}")
        cur = self.current(content_id)["current_version"]
        payload = json.loads(old["payload_json"])
        payload["_rollback_of"] = to_version
        return self.add_version(
            content_id,
            payload,
            base_version=cur,
            source_ids=json.loads(old["source_ids_json"]),
            producer={"kind": "rollback", "from_version": to_version},
            actor=actor,
            reason=f"откат к v{to_version}",
        )

    def set_publish(self, content_id: str, status: str, *, actor: str) -> None:
        assert status in PUBLISH
        with self.tx():
            t = now()
            self.db.execute(
                "UPDATE content SET publish_status=?, published_at=COALESCE(published_at, CASE WHEN ? IN "
                "('preview','published') THEN ? END), updated_at=? WHERE content_id=?",
                (status, status, t, t, content_id),
            )
            self.audit(actor, "publish_status", content_id=content_id, status=status)

    def set_review(self, content_id: str, status: str, *, reviewer: str, version: int, note: str = "") -> None:
        assert status in REVIEW
        with self.tx():
            cur = self.current(content_id)["current_version"]
            if version != cur:
                raise VersionConflict(f"проверялась v{version}, текущая v{cur}")
            self.db.execute(
                "UPDATE content SET review_status=?, reviewer=?, updated_at=? WHERE content_id=?",
                (status, reviewer, now(), content_id),
            )
            self.audit(reviewer, "review", content_id=content_id, version=version, status=status, note=note)

    def current(self, content_id: str) -> sqlite3.Row:
        return self.db.execute("SELECT * FROM content WHERE content_id=?", (content_id,)).fetchone()

    def version(self, content_id: str, v: int | None = None) -> dict | None:
        if v is None:
            v = self.current(content_id)["current_version"]
        row = self.db.execute(
            "SELECT * FROM versions WHERE content_id=? AND recipe_version=?", (content_id, v)
        ).fetchone()
        return dict(row) if row else None

    def versions(self, content_id: str) -> list[dict]:
        return [
            dict(r)
            for r in self.db.execute(
                "SELECT recipe_version, parent_version, payload_hash, producer_json, created_at, created_by, reason "
                "FROM versions WHERE content_id=? ORDER BY recipe_version",
                (content_id,),
            )
        ]

    def audit_for(self, content_id: str) -> list[dict]:
        return [dict(r) for r in self.db.execute("SELECT * FROM audit WHERE content_id=? ORDER BY id", (content_id,))]
