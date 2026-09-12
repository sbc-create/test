"""Хранилище ChangeSet: единственное, транзакционное, с исходящим ящиком.

Одно хранилище на весь контур. Второе немедленно поставило бы вопрос, какое
из них право, и ответа на него не существует — поэтому его просто нет.

Состояние меняется ТОЛЬКО через `применить_переход`, и в той же транзакции
пишется запись исходящего ящика. Разделить их значило бы допустить состояние,
о котором журнал аудита не узнает: изменение прошло, событие потерялось, и
восстановить историю уже неоткуда.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from . import model as M

БД_ПО_УМОЛЧАНИЮ = "/srv/site-factory/changeset-store/changesets.sqlite3"

СХЕМА = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS changeset (
  changeset_id      TEXT PRIMARY KEY,
  schema_version    TEXT NOT NULL,
  status            TEXT NOT NULL,
  version           INTEGER NOT NULL DEFAULT 1,
  resource_type     TEXT NOT NULL,
  resource_id       TEXT NOT NULL,
  operation_type    TEXT NOT NULL,
  target_site_ids   TEXT NOT NULL,
  canary_site_ids   TEXT NOT NULL DEFAULT '[]',
  producer_service  TEXT NOT NULL,
  actor_id          TEXT NOT NULL,
  actor_type        TEXT NOT NULL,
  idempotency_key   TEXT NOT NULL,
  correlation_id    TEXT NOT NULL,
  causation_id      TEXT,
  base_registry_version     INTEGER,
  expected_resource_fingerprint TEXT,
  requested_change  TEXT NOT NULL,
  risk_class        TEXT,
  policy_version    TEXT,
  plan_hash         TEXT,
  expires_at        TEXT,
  dry_run_result    TEXT,
  verification_plan TEXT,
  rollback_plan     TEXT,
  approval          TEXT,
  evidence_refs     TEXT NOT NULL DEFAULT '[]',
  failure_reason    TEXT,
  created_at        TEXT NOT NULL,
  updated_at        TEXT NOT NULL,
  UNIQUE (producer_service, idempotency_key)
);

CREATE TABLE IF NOT EXISTS changeset_target (
  changeset_id  TEXT NOT NULL REFERENCES changeset(changeset_id),
  site_id       TEXT NOT NULL,
  is_canary     INTEGER NOT NULL DEFAULT 0,
  state         TEXT NOT NULL DEFAULT 'PENDING',
  before_fingerprint TEXT,
  after_fingerprint  TEXT,
  attempts      INTEGER NOT NULL DEFAULT 0,
  detail        TEXT,
  updated_at    TEXT NOT NULL,
  PRIMARY KEY (changeset_id, site_id)
);

CREATE TABLE IF NOT EXISTS changeset_transition (
  seq            INTEGER PRIMARY KEY AUTOINCREMENT,
  changeset_id   TEXT NOT NULL REFERENCES changeset(changeset_id),
  action         TEXT NOT NULL,
  from_status    TEXT NOT NULL,
  to_status      TEXT NOT NULL,
  actor_id       TEXT NOT NULL,
  actor_role     TEXT NOT NULL,
  reason         TEXT,
  before_fingerprint TEXT,
  after_fingerprint  TEXT,
  correlation_id TEXT NOT NULL,
  causation_id   TEXT,
  occurred_at    TEXT NOT NULL
);

-- Замок целей. Строка существует, пока набор изменений активен: два
-- изменения одного ресурса на одном сайте одновременно недопустимы.
CREATE TABLE IF NOT EXISTS changeset_lock (
  lock_scope    TEXT PRIMARY KEY,
  changeset_id  TEXT NOT NULL,
  acquired_at   TEXT NOT NULL
);

-- Аренда исполнителя с маркером ограждения. Номер только растёт: исполнитель
-- со старым маркером не может применить изменение, даже если он ожил и
-- считает себя единственным.
CREATE TABLE IF NOT EXISTS changeset_lease (
  changeset_id  TEXT PRIMARY KEY,
  worker_id     TEXT NOT NULL,
  fencing_token INTEGER NOT NULL,
  expires_at    REAL NOT NULL,
  heartbeat_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS fencing_counter (
  scope   TEXT PRIMARY KEY,
  value   INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS changeset_outbox (
  seq            INTEGER PRIMARY KEY AUTOINCREMENT,
  changeset_id   TEXT NOT NULL,
  event_type     TEXT NOT NULL,
  idempotency_key TEXT NOT NULL UNIQUE,
  payload        TEXT NOT NULL,
  created_at     TEXT NOT NULL,
  published_at   TEXT,
  attempts       INTEGER NOT NULL DEFAULT 0,
  last_error     TEXT
);

CREATE TABLE IF NOT EXISTS changeset_dlq (
  seq          INTEGER PRIMARY KEY AUTOINCREMENT,
  changeset_id TEXT,
  event_type   TEXT,
  error_code   TEXT NOT NULL,
  reason       TEXT,
  attempts     INTEGER NOT NULL,
  payload      TEXT,
  created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS cs_status ON changeset(status);
CREATE INDEX IF NOT EXISTS cs_outbox_pending
  ON changeset_outbox(published_at) WHERE published_at IS NULL;

-- Прямая запись статуса запрещена на уровне БД. Состояние меняет только
-- машина переходов, и обойти её, дописав UPDATE в чужом коде, нельзя.
CREATE TRIGGER IF NOT EXISTS cs_no_direct_status
BEFORE UPDATE OF status ON changeset
FOR EACH ROW
WHEN COALESCE((SELECT value FROM cs_guard WHERE key='transition'), '0') <> '1'
BEGIN
  SELECT RAISE(ABORT, 'changeset.status изменяется только машиной переходов');
END;

CREATE TABLE IF NOT EXISTS cs_guard (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


#: Состояния, в которых ресурс остаётся в неизвестном виде. Замок держится до
#: вмешательства человека: второе изменение того же ресурса сейчас недопустимо.
УДЕРЖИВАЮТ_ЗАМОК = frozenset({"ROLLBACK_FAILED", "MANUAL_INTERVENTION_REQUIRED"})


class ChangeSetError(RuntimeError):
    def __init__(self, code: str, detail: str, status: int = 422):
        super().__init__(detail)
        self.error_code, self.detail, self.status = code, detail, status


def сейчас() -> str:
    import datetime as _d
    return _d.datetime.now(_d.timezone.utc).isoformat().replace("+00:00", "Z")


def открыть(путь: str | Path | None = None) -> sqlite3.Connection:
    п = str(путь or os.environ.get("CHANGESET_DB") or БД_ПО_УМОЛЧАНИЮ)
    Path(п).parent.mkdir(parents=True, exist_ok=True)
    с = sqlite3.connect(п, timeout=30, isolation_level=None)
    с.row_factory = sqlite3.Row
    с.executescript(СХЕМА)
    return с


def канон(данные: Any) -> str:
    """Каноническая форма для хэширования: порядок ключей не должен влиять."""
    return json.dumps(данные, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def хэш(данные: Any) -> str:
    return hashlib.sha256(канон(данные).encode("utf-8")).hexdigest()


def область_замка(resource_type: str, resource_id: str, site_id: str) -> str:
    return f"{site_id}|{resource_type}|{resource_id}"


# --- создание ----------------------------------------------------------------

def создать(соед: sqlite3.Connection, заявка: dict[str, Any], *,
            producer_service: str, actor_id: str, actor_type: str) -> dict:
    """Создать предложение. Повтор с тем же ключом возвращает то же самое."""
    ключ = str(заявка.get("idempotency_key") or "").strip()
    if not ключ:
        raise ChangeSetError("IDEMPOTENCY_KEY_REQUIRED",
                             "idempotency_key обязателен")
    есть = соед.execute(
        "SELECT * FROM changeset WHERE producer_service=? AND idempotency_key=?",
        (producer_service, ключ)).fetchone()
    if есть:
        # Тот же ключ с другим содержимым — не повтор, а другая заявка под
        # чужим именем. Молча вернуть старую значило бы потерять новую.
        if хэш(заявка.get("requested_change")) != хэш(
                json.loads(есть["requested_change"])):
            raise ChangeSetError(
                "IDEMPOTENCY_CONFLICT",
                "ключ идемпотентности уже использован с другим содержимым", 409)
        return {"changeset_id": есть["changeset_id"], "idempotent_replay": True,
                "status": есть["status"]}

    цели = list(dict.fromkeys(заявка.get("target_site_ids") or []))
    if not цели:
        raise ChangeSetError("TARGETS_REQUIRED", "нужен хотя бы один site_id")
    канареи = [s for s in (заявка.get("canary_site_ids") or []) if s in цели]
    if len(цели) > 1 and not канареи:
        # Раскатка без канарейки — это раскатка, у которой нет способа
        # остановиться до того, как пострадают все цели.
        канареи = [цели[0]]

    cid = str(uuid.uuid4())
    т = сейчас()
    try:
        _вставить(соед, cid, т, заявка, цели, канареи, ключ,
                  producer_service, actor_id, actor_type)
    except sqlite3.IntegrityError:
        # Кто-то успел первым между проверкой и вставкой. Это и есть
        # идемпотентность: побеждает первый, остальные получают его результат.
        есть = соед.execute(
            "SELECT * FROM changeset WHERE producer_service=? AND "
            "idempotency_key=?", (producer_service, ключ)).fetchone()
        if есть is None:
            raise
        return {"changeset_id": есть["changeset_id"], "idempotent_replay": True,
                "status": есть["status"]}
    return {"changeset_id": cid, "idempotent_replay": False,
            "status": M.PROPOSED}


def _вставить(соед, cid, т, заявка, цели, канареи, ключ, producer_service,
              actor_id, actor_type) -> None:
    соед.execute(
        "INSERT INTO changeset(changeset_id, schema_version, status, version, "
        "resource_type, resource_id, operation_type, target_site_ids, "
        "canary_site_ids, producer_service, actor_id, actor_type, "
        "idempotency_key, correlation_id, causation_id, requested_change, "
        "policy_version, created_at, updated_at) "
        "VALUES(?,?,?,1,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (cid, M.SCHEMA_VERSION, M.PROPOSED, заявка["resource_type"],
         заявка["resource_id"], заявка["operation_type"],
         канон(цели), канон(канареи), producer_service, actor_id, actor_type,
         ключ, заявка.get("correlation_id") or f"cs-{cid[:8]}",
         заявка.get("causation_id"), канон(заявка.get("requested_change") or {}),
         заявка.get("policy_version") or "policy/1.0.0", т, т))
    for s in цели:
        соед.execute(
            "INSERT INTO changeset_target(changeset_id, site_id, is_canary, "
            "state, updated_at) VALUES(?,?,?,?,?)",
            (cid, s, 1 if s in канареи else 0, "PENDING", т))
    _в_ящик(соед, cid, "changeset.proposed.v1", {
        "changeset_id": cid, "status": M.PROPOSED,
        "resource_type": заявка["resource_type"],
        "operation_type": заявка["operation_type"],
        "target_site_ids": цели, "producer_service": producer_service,
        "actor_id": actor_id, "actor_type": actor_type,
        "correlation_id": заявка.get("correlation_id") or f"cs-{cid[:8]}",
    })


# --- исходящий ящик ----------------------------------------------------------

def _в_ящик(соед: sqlite3.Connection, cid: str, тип: str,
            нагрузка: dict[str, Any], *, ключ: str | None = None) -> None:
    """Событие пишется в той же транзакции, что и изменение состояния."""
    к = ключ or f"{cid}:{тип}:{нагрузка.get('to_status') or нагрузка.get('status') or ''}:{нагрузка.get('attempt', 0)}"
    соед.execute(
        "INSERT OR IGNORE INTO changeset_outbox(changeset_id, event_type, "
        "idempotency_key, payload, created_at) VALUES(?,?,?,?,?)",
        (cid, тип, к, канон(нагрузка), сейчас()))


# --- переходы ----------------------------------------------------------------

def применить_переход(соед: sqlite3.Connection, cid: str, действие: str, *,
                      actor_id: str, служба: str, роль: str,
                      reason: str = "", поля: dict[str, Any] | None = None,
                      ожидаемая_версия: int | None = None,
                      fencing_token: int | None = None) -> dict:
    """Единственный способ изменить состояние набора изменений."""
    with соед:
        строка = соед.execute("SELECT * FROM changeset WHERE changeset_id=?",
                              (cid,)).fetchone()
        if строка is None:
            raise ChangeSetError("CHANGESET_NOT_FOUND", "набора нет", 404)
        текущее = строка["status"]

        if ожидаемая_версия is not None and строка["version"] != ожидаемая_версия:
            raise ChangeSetError(
                "VERSION_CONFLICT",
                f"версия набора {строка['version']}, ожидалась {ожидаемая_версия}",
                409)

        п = M.переход(текущее, действие)
        if п is None:
            raise ChangeSetError(
                "TRANSITION_NOT_ALLOWED",
                f"из состояния {текущее} действие {действие} не предусмотрено",
                409)
        if роль not in п.роли:
            raise ChangeSetError(
                "ROLE_DENIED",
                f"роль {роль} не вправе выполнять {действие}", 403)
        if роль not in M.роли_службы(служба):
            raise ChangeSetError(
                "ROLE_NOT_GRANTED",
                f"служба {служба} не имеет роли {роль}", 403)
        if строка["actor_type"] == "MODEL" and действие in (
                "approve", "apply", "rollback_start"):
            raise ChangeSetError("MODEL_ACTION_DENIED",
                                 "актору-модели исполнительные действия закрыты",
                                 403)

        # Аренда проверяется для всего, что ведёт к внешнему эффекту.
        if действие in ("apply", "applied", "verify_ok", "verify_fail",
                        "rollback_ok", "rollback_fail"):
            _проверить_аренду(соед, cid, fencing_token)

        т = сейчас()
        обновления, значения = ["status=?", "version=version+1", "updated_at=?"], \
            [п.в_состояние, т]
        for k, v in (поля or {}).items():
            обновления.append(f"{k}=?")
            значения.append(v if isinstance(v, (str, int, float, type(None)))
                            else канон(v))
        значения.append(cid)
        # Снимаем защиту ровно на одну операцию: триггер запрещает менять
        # статус всем, кроме этого места.
        соед.execute("INSERT INTO cs_guard(key,value) VALUES('transition','1') "
                     "ON CONFLICT(key) DO UPDATE SET value='1'")
        try:
            соед.execute(
                f"UPDATE changeset SET {', '.join(обновления)} WHERE changeset_id=?",
                значения)
        finally:
            соед.execute("UPDATE cs_guard SET value='0' WHERE key='transition'")

        соед.execute(
            "INSERT INTO changeset_transition(changeset_id, action, from_status, "
            "to_status, actor_id, actor_role, reason, correlation_id, "
            "causation_id, occurred_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (cid, действие, текущее, п.в_состояние, actor_id, роль, reason,
             строка["correlation_id"], строка["causation_id"], т))

        if п.в_состояние in M.АКТИВНЫЕ:
            _взять_замок(соед, строка, cid)
        elif п.в_состояние not in УДЕРЖИВАЮТ_ЗАМОК:
            # Требующий вмешательства держит замок намеренно: пока человек не
            # разобрался, второе изменение того же ресурса недопустимо.
            соед.execute("DELETE FROM changeset_lock WHERE changeset_id=?", (cid,))

        _в_ящик(соед, cid, п.событие or f"changeset.{действие}.v1", {
            "changeset_id": cid, "action": действие, "from_status": текущее,
            "to_status": п.в_состояние, "actor_id": actor_id, "role": роль,
            "reason": reason, "correlation_id": строка["correlation_id"],
            "causation_id": строка["causation_id"],
            "resource_type": строка["resource_type"],
            "resource_id": строка["resource_id"],
            "target_site_ids": json.loads(строка["target_site_ids"]),
            "plan_hash": строка["plan_hash"],
            "policy_version": строка["policy_version"],
            "occurred_at": т,
        })
    return {"changeset_id": cid, "from_status": текущее,
            "status": п.в_состояние, "action": действие}


def _взять_замок(соед: sqlite3.Connection, строка: sqlite3.Row, cid: str) -> None:
    for site_id in json.loads(строка["target_site_ids"]):
        область = область_замка(строка["resource_type"], строка["resource_id"],
                                site_id)
        занят = соед.execute(
            "SELECT changeset_id FROM changeset_lock WHERE lock_scope=?",
            (область,)).fetchone()
        if занят and занят["changeset_id"] != cid:
            raise ChangeSetError(
                "LOCK_CONFLICT",
                f"цель {site_id} уже изменяется набором {занят['changeset_id']}",
                409)
        соед.execute(
            "INSERT INTO changeset_lock(lock_scope, changeset_id, acquired_at) "
            "VALUES(?,?,?) ON CONFLICT(lock_scope) DO UPDATE SET "
            "changeset_id=excluded.changeset_id",
            (область, cid, сейчас()))


# --- аренда и ограждение -----------------------------------------------------

def взять_аренду(соед: sqlite3.Connection, cid: str, worker_id: str, *,
                 ttl: float = 60.0) -> dict:
    """Выдать аренду с новым маркером ограждения.

    Маркер только растёт. Исполнитель, проспавший своё время, вернётся со
    старым номером — и будет отвергнут, сколько бы он ни был уверен, что
    работает он один.
    """
    with соед:
        текущая = соед.execute(
            "SELECT * FROM changeset_lease WHERE changeset_id=?", (cid,)).fetchone()
        сейчас_м = time.monotonic()
        if текущая and текущая["expires_at"] > сейчас_м \
                and текущая["worker_id"] != worker_id:
            raise ChangeSetError(
                "LEASE_HELD",
                f"аренда у исполнителя {текущая['worker_id']}", 409)
        соед.execute(
            "INSERT INTO fencing_counter(scope, value) VALUES(?,1) "
            "ON CONFLICT(scope) DO UPDATE SET value=value+1", (cid,))
        маркер = соед.execute(
            "SELECT value FROM fencing_counter WHERE scope=?", (cid,)).fetchone()[0]
        соед.execute(
            "INSERT INTO changeset_lease(changeset_id, worker_id, fencing_token, "
            "expires_at, heartbeat_at) VALUES(?,?,?,?,?) "
            "ON CONFLICT(changeset_id) DO UPDATE SET worker_id=excluded.worker_id, "
            "fencing_token=excluded.fencing_token, "
            "expires_at=excluded.expires_at, heartbeat_at=excluded.heartbeat_at",
            (cid, worker_id, маркер, сейчас_м + ttl, сейчас_м))
    return {"changeset_id": cid, "worker_id": worker_id,
            "fencing_token": маркер, "ttl": ttl}


def продлить_аренду(соед: sqlite3.Connection, cid: str, worker_id: str,
                    маркер: int, *, ttl: float = 60.0) -> bool:
    с = time.monotonic()
    with соед:
        изменено = соед.execute(
            "UPDATE changeset_lease SET expires_at=?, heartbeat_at=? "
            "WHERE changeset_id=? AND worker_id=? AND fencing_token=?",
            (с + ttl, с, cid, worker_id, маркер)).rowcount
    return изменено > 0


def _проверить_аренду(соед: sqlite3.Connection, cid: str,
                      маркер: int | None) -> None:
    аренда = соед.execute("SELECT * FROM changeset_lease WHERE changeset_id=?",
                          (cid,)).fetchone()
    if аренда is None:
        raise ChangeSetError("LEASE_REQUIRED",
                             "действие требует действующей аренды", 409)
    if маркер is None:
        raise ChangeSetError("FENCING_TOKEN_REQUIRED",
                             "не предъявлен маркер ограждения", 409)
    if маркер < аренда["fencing_token"]:
        raise ChangeSetError(
            "FENCED_OUT",
            f"маркер {маркер} устарел: действующий {аренда['fencing_token']}",
            409)
    if маркер > аренда["fencing_token"]:
        raise ChangeSetError("FENCING_TOKEN_UNKNOWN",
                             "предъявлен маркер, который не выдавался", 409)


# --- чтение ------------------------------------------------------------------

def получить(соед: sqlite3.Connection, cid: str) -> dict | None:
    р = соед.execute("SELECT * FROM changeset WHERE changeset_id=?", (cid,)).fetchone()
    if р is None:
        return None
    d = dict(р)
    for поле in ("target_site_ids", "canary_site_ids", "requested_change",
                 "dry_run_result", "verification_plan", "rollback_plan",
                 "approval", "evidence_refs"):
        if d.get(поле):
            try:
                d[поле] = json.loads(d[поле])
            except (ValueError, TypeError):
                pass
    d["targets"] = [dict(x) for x in соед.execute(
        "SELECT * FROM changeset_target WHERE changeset_id=? ORDER BY "
        "is_canary DESC, site_id", (cid,))]
    d["transitions"] = [dict(x) for x in соед.execute(
        "SELECT * FROM changeset_transition WHERE changeset_id=? ORDER BY seq",
        (cid,))]
    return d


def обновить_цель(соед: sqlite3.Connection, cid: str, site_id: str, *,
                  state: str, before: str | None = None,
                  after: str | None = None, detail: str = "") -> None:
    with соед:
        соед.execute(
            "UPDATE changeset_target SET state=?, before_fingerprint="
            "COALESCE(?, before_fingerprint), after_fingerprint=?, "
            "attempts=attempts+1, detail=?, updated_at=? "
            "WHERE changeset_id=? AND site_id=?",
            (state, before, after, detail, сейчас(), cid, site_id))
