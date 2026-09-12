"""Канонический append-only Audit/Action Ledger Control Plane.

Почему отдельное хранилище, а не таблица реестра
------------------------------------------------

В `registry.sqlite3` уже есть таблица `audit` — но это локальный след
операций самого реестра: шесть полей, без конверта, без цепочки хэшей, без
идемпотентности. Общефлотский журнал, положенный туда же, связал бы судьбы
двух разных вещей: восстановление реестра тянуло бы за собой всю историю
аудита, а рост журнала — резервные копии реестра. Поэтому `audit` и `outbox`
реестра объявлены ПРОИЗВОДИТЕЛЯМИ, а канонический журнал живёт отдельно и
принадлежит Architect.

Чего журнал не делает
---------------------

Не исполняет команд. Это журнал фактов: он принимает утверждение о уже
случившемся и хранит его неизменным. Событие, изменяющее состояние мира,
здесь только отражается.

Неизменяемость
--------------

UPDATE и DELETE запрещены триггерами на уровне БД, а не только отсутствием
endpoint: запрет, живущий лишь в приложении, снимается любым, кто дотянулся
до файла. Исправление возможно только новым событием со ссылкой
`corrects_event_id`.

Честное название защиты
-----------------------

`LOCAL_HASH_CHAIN`: цепочка SHA-256 обнаруживает изменение задним числом,
если злоумышленник не переписал всю цепь. Это tamper-EVIDENT, а не
tamper-PROOF, и называть это неуязвимостью нельзя.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Any

СХЕМА = "fleet-audit-ledger/1.0.0"
ГЕНЕЗИС_ХЭШ = "0" * 64

#: Фазы жизненного цикла действия. Перечень закрыт: событие, не попавшее ни в
#: одну фазу, означало бы, что мы не знаем, что именно записали.
ФАЗЫ = ("PROPOSED", "VALIDATED", "AUTHORIZED", "STARTED", "SUCCEEDED",
        "FAILED", "VERIFIED", "ROLLED_BACK", "BLOCKED", "CANCELLED",
        "OBSERVED", "GENESIS")
РЕЗУЛЬТАТЫ = ("SUCCESS", "FAILURE", "PENDING", "NOT_APPLICABLE")
ТИПЫ_АКТОРОВ = ("SERVICE", "HUMAN", "MODEL")

#: Полномочия. Qwen как MODEL их не получает — см. `ПРАВА_СЛУЖБ`.
ПОЛНОМОЧИЯ = ("OBSERVE", "PROPOSE", "EXECUTE", "AUTHORIZE")

#: Что каждой службе позволено записывать. Проверяется сервером по опознанной
#: личности, а не по тому, что клиент написал в теле запроса.
ПРАВА_СЛУЖБ: dict[str, set[str]] = {
    "architect":   {"OBSERVE", "PROPOSE", "EXECUTE", "AUTHORIZE"},
    # Мост контура изменений. Публикует факты исполнения, но не разрешения:
    # раньше он писал под личностью architect и получал вместе с ней
    # AUTHORIZE — полномочие, которое мосту не нужно ни для чего.
    "control-plane": {"OBSERVE", "EXECUTE"},
    "registry":    {"OBSERVE", "EXECUTE"},
    "templates":   {"OBSERVE", "PROPOSE", "EXECUTE"},
    "content":     {"OBSERVE", "PROPOSE", "EXECUTE"},
    "seo":         {"OBSERVE", "PROPOSE"},
    "monitoring":  {"OBSERVE"},
    "backup":      {"OBSERVE", "EXECUTE"},
    "integrations": {"OBSERVE", "PROPOSE", "EXECUTE"},
    # Qwen — MODEL. Только наблюдение и предложение: AUTHORIZE, APPLY,
    # DEPLOY, DELETE и ROLLBACK ему недоступны по построению.
    "qwen":        {"OBSERVE", "PROPOSE"},
    "human_owner": {"AUTHORIZE"},
}
#: Фазы, запрещённые модели независимо от полномочий.
ФАЗЫ_ЗАПРЕЩЁННЫЕ_МОДЕЛИ = {"AUTHORIZED", "STARTED", "SUCCEEDED",
                           "ROLLED_BACK", "VERIFIED"}

ПОЛЯ = (
    "event_id", "schema_version", "event_type", "phase", "result",
    "error_code", "occurred_at", "received_at", "stored_at",
    "producer_service", "producer_instance", "actor_id", "actor_type",
    "authority", "scope", "environment", "site_id", "resource_type",
    "resource_id", "resource_owner", "action_id", "change_set_id",
    "correlation_id", "causation_id", "idempotency_key", "prompt_id",
    "prompt_rev", "run_id", "summary", "before_hash", "after_hash",
    "commit_sha", "build_id", "release_id", "approval_ref", "rollback_ref",
    "evidence_refs", "corrects_event_id", "supersedes_event_id",
)

DDL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS ledger_event (
  ledger_seq        INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id          TEXT NOT NULL UNIQUE,
  schema_version    TEXT NOT NULL,
  event_type        TEXT NOT NULL,
  phase             TEXT NOT NULL,
  result            TEXT,
  error_code        TEXT,
  occurred_at       TEXT,
  received_at       TEXT NOT NULL,
  stored_at         TEXT NOT NULL,
  producer_service  TEXT NOT NULL,
  producer_instance TEXT,
  actor_id          TEXT NOT NULL,
  actor_type        TEXT NOT NULL,
  authority         TEXT NOT NULL,
  scope             TEXT NOT NULL,
  environment       TEXT,
  site_id           TEXT,
  resource_type     TEXT,
  resource_id       TEXT,
  resource_owner    TEXT,
  action_id         TEXT,
  change_set_id     TEXT,
  correlation_id    TEXT NOT NULL,
  causation_id      TEXT,
  idempotency_key   TEXT NOT NULL,
  prompt_id         TEXT,
  prompt_rev        TEXT,
  run_id            TEXT,
  summary           TEXT,
  before_hash       TEXT,
  after_hash        TEXT,
  commit_sha        TEXT,
  build_id          TEXT,
  release_id        TEXT,
  approval_ref      TEXT,
  rollback_ref      TEXT,
  evidence_refs     TEXT NOT NULL DEFAULT '[]',
  corrects_event_id TEXT,
  supersedes_event_id TEXT,
  payload_hash      TEXT NOT NULL,
  prev_hash         TEXT NOT NULL,
  event_hash        TEXT NOT NULL,
  UNIQUE (producer_service, idempotency_key)
);
CREATE INDEX IF NOT EXISTS ix_le_site ON ledger_event(site_id, ledger_seq);
CREATE INDEX IF NOT EXISTS ix_le_action ON ledger_event(action_id, ledger_seq);
CREATE INDEX IF NOT EXISTS ix_le_corr ON ledger_event(correlation_id, ledger_seq);
CREATE INDEX IF NOT EXISTS ix_le_prod ON ledger_event(producer_service, ledger_seq);

-- Запрет изменения и удаления на уровне БД. Запрет, живущий только в
-- приложении, снимается любым, кто открыл файл напрямую.
CREATE TRIGGER IF NOT EXISTS le_no_update BEFORE UPDATE ON ledger_event
BEGIN SELECT RAISE(ABORT, 'ledger_event is append-only: UPDATE forbidden'); END;
CREATE TRIGGER IF NOT EXISTS le_no_delete BEFORE DELETE ON ledger_event
BEGIN SELECT RAISE(ABORT, 'ledger_event is append-only: DELETE forbidden'); END;

CREATE TABLE IF NOT EXISTS ledger_outbox (
  seq          INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id     TEXT NOT NULL UNIQUE,
  event_type   TEXT NOT NULL,
  ledger_seq   INTEGER NOT NULL,
  occurred_at  TEXT NOT NULL,
  published_at TEXT,
  attempts     INTEGER NOT NULL DEFAULT 0,
  last_error   TEXT
);

CREATE TABLE IF NOT EXISTS ledger_checkpoint (
  checkpoint_id TEXT PRIMARY KEY,
  ledger_seq    INTEGER NOT NULL,
  chain_root    TEXT NOT NULL,
  event_count   INTEGER NOT NULL,
  created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS consumer_cursor (
  consumer   TEXT PRIMARY KEY,
  position   TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ledger_dlq (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  consumer   TEXT NOT NULL,
  source_ref TEXT,
  error_code TEXT NOT NULL,
  reason     TEXT NOT NULL,
  attempts   INTEGER NOT NULL,
  first_at   TEXT NOT NULL,
  last_at    TEXT NOT NULL,
  payload    TEXT
);
"""

#: Грубый, намеренно широкий поиск секретов. Ложное срабатывание дешевле
#: пропущенного токена: первое стоит одной правки, второе — компрометации.
СЕКРЕТЫ = re.compile(
    r"(Bearer\s+[A-Za-z0-9._\-]{16,}"
    r"|(?:api[_-]?key|password|passwd|secret|token|credential)"
    r"\s*[:=]\s*['\"]?[A-Za-z0-9._\-]{12,}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----)", re.I)


class LedgerError(RuntimeError):
    def __init__(self, code: str, detail: str, status: int = 422):
        super().__init__(detail)
        self.error_code, self.detail, self.status = code, detail, status


def сейчас() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def канон(данные: dict[str, Any]) -> str:
    """Детерминированная сериализация: одно и то же событие — один и тот же байт."""
    return json.dumps(данные, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def открыть(путь: str | Path) -> sqlite3.Connection:
    п = Path(путь)
    п.parent.mkdir(parents=True, exist_ok=True)
    с = sqlite3.connect(п, timeout=30, isolation_level=None)
    с.row_factory = sqlite3.Row
    с.executescript(DDL)
    return с


def _хэш_события(тело: dict[str, Any], prev_hash: str) -> tuple[str, str]:
    payload_hash = hashlib.sha256(канон(тело).encode()).hexdigest()
    event_hash = hashlib.sha256(
        (prev_hash + payload_hash).encode()).hexdigest()
    return payload_hash, event_hash


def _проверить_секреты(тело: dict[str, Any]) -> None:
    м = СЕКРЕТЫ.search(канон(тело))
    if м:
        raise LedgerError(
            "SECRET_IN_PAYLOAD",
            "в событии обнаружен секрет; журнал не принимает секреты ни в "
            "каком виде — ни в summary, ни в payload, ни в ссылках")


def append(соед: sqlite3.Connection, событие: dict[str, Any], *,
           producer_service: str, actor_id: str, actor_type: str,
           authority: str, известные_сайты=None) -> dict[str, Any]:
    """Добавить событие. Личность и полномочия приходят ОТ СЕРВЕРА.

    `producer_service`, `actor_id`, `actor_type` и `authority` берутся из
    опознанной службы, а не из тела запроса: клиент, которому верят на слово,
    объявит себя кем угодно.
    """
    if producer_service not in ПРАВА_СЛУЖБ:
        raise LedgerError("UNKNOWN_PRODUCER",
                          f"служба {producer_service!r} не объявлена", 403)
    if authority not in ПОЛНОМОЧИЯ:
        raise LedgerError("UNKNOWN_AUTHORITY", f"полномочие {authority!r}")
    if authority not in ПРАВА_СЛУЖБ[producer_service]:
        raise LedgerError(
            "AUTHORITY_DENIED",
            f"службе {producer_service} не разрешено полномочие {authority}", 403)

    фаза = событие.get("phase")
    if фаза not in ФАЗЫ:
        raise LedgerError("UNKNOWN_PHASE", f"фаза {фаза!r} не объявлена")
    if actor_type == "MODEL" and фаза in ФАЗЫ_ЗАПРЕЩЁННЫЕ_МОДЕЛИ:
        raise LedgerError(
            "MODEL_PHASE_DENIED",
            f"актор типа MODEL не вправе записывать фазу {фаза}: модель "
            f"предлагает и объясняет, но не исполняет и не разрешает", 403)
    рез = событие.get("result")
    if рез is not None and рез not in РЕЗУЛЬТАТЫ:
        raise LedgerError("UNKNOWN_RESULT", f"результат {рез!r} не объявлен")

    ключ = (событие.get("idempotency_key") or "").strip()
    if not ключ:
        raise LedgerError("IDEMPOTENCY_KEY_REQUIRED",
                          "idempotency_key обязателен")
    корр = (событие.get("correlation_id") or "").strip()
    if not корр:
        raise LedgerError("CORRELATION_ID_REQUIRED",
                          "correlation_id обязателен")

    scope = (событие.get("scope") or "").strip().upper()
    site_id = (событие.get("site_id") or "").strip() or None
    if scope not in ("SITE", "FLEET"):
        raise LedgerError("UNKNOWN_SCOPE", "scope обязан быть SITE или FLEET")
    if scope == "SITE":
        if not site_id:
            raise LedgerError("SITE_ID_REQUIRED",
                              "для scope=SITE обязателен site_id из реестра")
        if известные_сайты is not None and site_id not in известные_сайты:
            # Домен ключом связи не является: он меняется, идентификатор нет.
            raise LedgerError(
                "SITE_ID_UNKNOWN",
                f"site_id {site_id!r} отсутствует в Site Registry; домен "
                f"ключом связи не является")

    _проверить_секреты(событие)

    тело = {k: событие.get(k) for k in ПОЛЯ}
    тело["evidence_refs"] = событие.get("evidence_refs") or []
    тело.update({"schema_version": СХЕМА, "producer_service": producer_service,
                 "actor_id": actor_id, "actor_type": actor_type,
                 "authority": authority, "scope": scope, "site_id": site_id,
                 "idempotency_key": ключ, "correlation_id": корр})
    # Время сервера назначает сервер. Клиентское occurred_at сохраняется
    # отдельно: расхождение часов — это факт, а не повод подменять одно другим.
    тело["received_at"] = сейчас()

    соед.execute("BEGIN IMMEDIATE")
    try:
        уже = соед.execute(
            "SELECT * FROM ledger_event WHERE producer_service=? "
            "AND idempotency_key=?", (producer_service, ключ)).fetchone()
        if уже:
            сравнимое = {k: тело.get(k) for k in ПОЛЯ
                         if k not in ("received_at", "stored_at", "event_id")}
            прежнее = {k: (json.loads(уже["evidence_refs"])
                           if k == "evidence_refs" else уже[k])
                       for k in ПОЛЯ
                       if k not in ("received_at", "stored_at", "event_id")}
            if канон(сравнимое) != канон(прежнее):
                raise LedgerError(
                    "IDEMPOTENCY_CONFLICT",
                    "тот же ключ идемпотентности с другим содержимым: "
                    "повтор обязан повторять, а не переписывать", 409)
            соед.execute("COMMIT")
            return {"event_id": уже["event_id"], "ledger_seq": уже["ledger_seq"],
                    "idempotent_replay": True, "event_hash": уже["event_hash"]}

        посл = соед.execute(
            "SELECT event_hash FROM ledger_event ORDER BY ledger_seq DESC LIMIT 1"
        ).fetchone()
        prev_hash = посл["event_hash"] if посл else ГЕНЕЗИС_ХЭШ
        тело["event_id"] = событие.get("event_id") or str(uuid.uuid4())
        тело["stored_at"] = сейчас()
        payload_hash, event_hash = _хэш_события(тело, prev_hash)

        столбцы = list(ПОЛЯ) + ["payload_hash", "prev_hash", "event_hash"]
        значения = [json.dumps(тело[k], ensure_ascii=False)
                    if k == "evidence_refs" else тело.get(k) for k in ПОЛЯ]
        значения += [payload_hash, prev_hash, event_hash]
        соед.execute(
            "INSERT INTO ledger_event(%s) VALUES(%s)" % (
                ",".join(столбцы), ",".join("?" * len(столбцы))), значения)
        seq = соед.execute("SELECT last_insert_rowid() s").fetchone()["s"]
        # Событие о добавлении — в тот же транзакции. Но САМО оно в журнал не
        # возвращается: иначе каждая запись порождала бы запись о записи.
        соед.execute(
            "INSERT INTO ledger_outbox(event_id, event_type, ledger_seq, "
            "occurred_at) VALUES(?,?,?,?)",
            (тело["event_id"], "audit.event.appended.v1", seq, тело["stored_at"]))
        соед.execute("COMMIT")
    except Exception:
        соед.execute("ROLLBACK")
        raise
    return {"event_id": тело["event_id"], "ledger_seq": seq,
            "idempotent_replay": False, "event_hash": event_hash}


def проверить_цепь(соед: sqlite3.Connection) -> dict[str, Any]:
    """Пересчитать цепочку и назвать точное место разрыва, если он есть."""
    prev = ГЕНЕЗИС_ХЭШ
    проверено = 0
    for р in соед.execute("SELECT * FROM ledger_event ORDER BY ledger_seq"):
        тело = {k: (json.loads(р["evidence_refs"]) if k == "evidence_refs"
                    else р[k]) for k in ПОЛЯ}
        ph, eh = _хэш_события(тело, prev)
        if ph != р["payload_hash"] or eh != р["event_hash"] or prev != р["prev_hash"]:
            return {"ok": False, "verified": проверено,
                    "broken_at_seq": р["ledger_seq"],
                    "broken_event_id": р["event_id"],
                    "reason": ("содержимое не соответствует сохранённому хэшу"
                               if ph != р["payload_hash"] else
                               "разрыв цепочки prev_hash/event_hash")}
        prev = р["event_hash"]
        проверено += 1
    return {"ok": True, "verified": проверено, "chain_root": prev}


def checkpoint(соед: sqlite3.Connection) -> dict[str, Any]:
    п = проверить_цепь(соед)
    if not п["ok"]:
        raise LedgerError("CHAIN_BROKEN",
                          f"цепь разорвана на seq {п['broken_at_seq']}", 500)
    посл = соед.execute(
        "SELECT ledger_seq FROM ledger_event ORDER BY ledger_seq DESC LIMIT 1"
    ).fetchone()
    cid = "cp-" + uuid.uuid4().hex[:12]
    соед.execute(
        "INSERT INTO ledger_checkpoint(checkpoint_id, ledger_seq, chain_root, "
        "event_count, created_at) VALUES(?,?,?,?,?)",
        (cid, посл["ledger_seq"] if посл else 0, п["chain_root"],
         п["verified"], сейчас()))
    return {"checkpoint_id": cid, "ledger_seq": посл["ledger_seq"] if посл else 0,
            "chain_root": п["chain_root"], "event_count": п["verified"]}
