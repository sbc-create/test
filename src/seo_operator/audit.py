"""
Append-only audit log с хэш-цепочкой (GR-010).

Каждая запись содержит hash предыдущей. Разрыв цепочки => tamper detected.
Значения секретов в лог не попадают: redact() вычищает подозрительные поля до записи.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from . import config

GENESIS = "0" * 64

SECRET_KEY_PATTERN = re.compile(
    r"(secret|token|password|passwd|credential|api[_-]?key|oauth|private[_-]?key|authorization)",
    re.IGNORECASE,
)
SECRET_VALUE_PATTERN = re.compile(
    r"(ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|ya29\.[A-Za-z0-9_\-]{20,}|y0_[A-Za-z0-9_\-]{20,})"
)
REDACTED = "***REDACTED***"


def redact(value: Any) -> Any:
    """Рекурсивно вычищает секреты. Разрешены только *_ref ссылки."""
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if SECRET_KEY_PATTERN.search(str(k)) and not str(k).endswith("_ref"):
                out[k] = REDACTED
            else:
                out[k] = redact(v)
        return out
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    if isinstance(value, str):
        return SECRET_VALUE_PATTERN.sub(REDACTED, value)
    return value


@dataclass(frozen=True)
class AuditRecord:
    seq: int
    ts: str
    actor: str
    action: str
    site_id: str | None
    experiment_id: str | None
    payload: dict[str, Any]
    prev_hash: str
    hash: str


def _digest(seq: int, ts: str, actor: str, action: str, site_id: str | None,
            experiment_id: str | None, payload: dict, prev_hash: str) -> str:
    blob = json.dumps(
        {"seq": seq, "ts": ts, "actor": actor, "action": action, "site_id": site_id,
         "experiment_id": experiment_id, "payload": payload, "prev": prev_hash},
        sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class AuditLog:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (config.state_dir() / "audit.sqlite3")
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS audit (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                site_id TEXT,
                experiment_id TEXT,
                payload TEXT NOT NULL,
                prev_hash TEXT NOT NULL,
                hash TEXT NOT NULL UNIQUE
            );
            CREATE INDEX IF NOT EXISTS idx_audit_site ON audit(site_id);
            CREATE INDEX IF NOT EXISTS idx_audit_exp ON audit(experiment_id);
            -- GR-010: append-only на уровне БД, а не только в коде.
            CREATE TRIGGER IF NOT EXISTS audit_no_update
                BEFORE UPDATE ON audit
                BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS audit_no_delete
                BEFORE DELETE ON audit
                BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;
            """
        )
        self._conn.commit()

    def _last(self) -> sqlite3.Row | None:
        return self._conn.execute("SELECT * FROM audit ORDER BY seq DESC LIMIT 1").fetchone()

    def append(self, actor: str, action: str, payload: dict[str, Any],
               site_id: str | None = None, experiment_id: str | None = None) -> AuditRecord:
        last = self._last()
        seq = (last["seq"] + 1) if last else 1
        prev_hash = last["hash"] if last else GENESIS
        ts = datetime.now(timezone.utc).isoformat()
        clean = redact(payload)
        h = _digest(seq, ts, actor, action, site_id, experiment_id, clean, prev_hash)
        self._conn.execute(
            "INSERT INTO audit (seq, ts, actor, action, site_id, experiment_id, payload, prev_hash, hash)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (seq, ts, actor, action, site_id, experiment_id,
             json.dumps(clean, ensure_ascii=False, sort_keys=True), prev_hash, h),
        )
        self._conn.commit()
        return AuditRecord(seq, ts, actor, action, site_id, experiment_id, clean, prev_hash, h)

    def verify_chain(self) -> tuple[bool, str]:
        prev_hash = GENESIS
        for row in self._conn.execute("SELECT * FROM audit ORDER BY seq ASC"):
            payload = json.loads(row["payload"])
            expected = _digest(row["seq"], row["ts"], row["actor"], row["action"],
                               row["site_id"], row["experiment_id"], payload, prev_hash)
            if row["prev_hash"] != prev_hash:
                return False, f"seq={row['seq']}: разрыв prev_hash"
            if row["hash"] != expected:
                return False, f"seq={row['seq']}: hash не совпадает — запись изменена"
            prev_hash = row["hash"]
        return True, "цепочка целостна"

    def records(self, site_id: str | None = None, limit: int = 100) -> Iterator[AuditRecord]:
        if site_id:
            cur = self._conn.execute(
                "SELECT * FROM audit WHERE site_id=? ORDER BY seq DESC LIMIT ?", (site_id, limit))
        else:
            cur = self._conn.execute("SELECT * FROM audit ORDER BY seq DESC LIMIT ?", (limit,))
        for row in cur:
            yield AuditRecord(row["seq"], row["ts"], row["actor"], row["action"],
                              row["site_id"], row["experiment_id"], json.loads(row["payload"]),
                              row["prev_hash"], row["hash"])

    def close(self) -> None:
        self._conn.close()
