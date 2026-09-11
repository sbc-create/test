"""Каноническое хранилище Site Registry: записи, версии, outbox, аудит.

Зачем хранилище, если раньше хватало файлов
-------------------------------------------

Прежний реестр — это каталог JSON-профилей, читаемый на старте процесса. Над
файлами нельзя выполнить два обязательных требования: изменить запись и
записать событие ОДНОЙ транзакцией, и выдать монотонную версию, по которой
потребитель отличит «я отстал» от «ничего не менялось». Поэтому у службы
появляется своя БД — не второй реестр, а хранилище того же самого.

Профили остаются на диске и остаются источником первичного наполнения. БД
становится авторитетной после переноса, и обратная сторона этого — миграция
обратима: файлы не удаляются.

Почему SQLite
-------------

Реестр — единственный писатель своей БД, объём сотни записей, транзакция
нужна локальная. Postgres здесь добавил бы сетевой отказ туда, где его не
было. WAL включён: читатели не блокируют писателя.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

СХЕМА = "fleet-registry/1.0.0"

#: Состояния жизненного цикла. Перечень закрыт: запись, не попавшая ни в одно
#: состояние, означала бы, что мы не решили, что с ней делать.
СОСТОЯНИЯ = ("DRAFT", "ACTIVE", "QUARANTINED", "RETIRED")

DDL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- Запись о сайте. site_id неизменяем и никогда не перегенерируется:
-- он внешний ключ для Content, Monitoring и Backup.
CREATE TABLE IF NOT EXISTS site (
  site_id               TEXT PRIMARY KEY,
  canonical_domain      TEXT NOT NULL UNIQUE,
  family                TEXT NOT NULL,
  environment           TEXT NOT NULL,
  lifecycle_state       TEXT NOT NULL,
  owner_ref             TEXT,
  template_id           TEXT,
  template_version      TEXT,
  build_id              TEXT,
  release_id            TEXT,
  desired_state         TEXT NOT NULL DEFAULT 'ACTIVE',
  observed_state        TEXT,
  integration_refs      TEXT NOT NULL DEFAULT '{}',
  monitoring_profile_ref TEXT,
  backup_policy_ref     TEXT,
  content_profile_ref   TEXT,
  seo_profile_ref       TEXT,
  aggregate_version     INTEGER NOT NULL DEFAULT 1,
  created_at            TEXT NOT NULL,
  updated_at            TEXT NOT NULL,
  CHECK (lifecycle_state IN ('DRAFT','ACTIVE','QUARANTINED','RETIRED'))
);

-- Алиасы отдельной таблицей: уникальность домена обязана проверяться и
-- между canonical_domain и alias, а не только внутри своего столбца.
CREATE TABLE IF NOT EXISTS site_alias (
  alias    TEXT PRIMARY KEY,
  site_id  TEXT NOT NULL REFERENCES site(site_id) ON DELETE CASCADE
);

-- Монотонная версия реестра. Одна строка; растёт на каждой мутации.
CREATE TABLE IF NOT EXISTS registry_version (
  id      INTEGER PRIMARY KEY CHECK (id = 1),
  version INTEGER NOT NULL
);
INSERT OR IGNORE INTO registry_version(id, version) VALUES (1, 0);

-- Transactional outbox. Пишется в ТОЙ ЖЕ транзакции, что и запись о сайте:
-- в этом вся суть, иначе событие теряется между commit и публикацией.
CREATE TABLE IF NOT EXISTS outbox (
  seq               INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id          TEXT NOT NULL UNIQUE,
  event_type        TEXT NOT NULL,
  schema_version    TEXT NOT NULL,
  site_id           TEXT NOT NULL,
  aggregate_version INTEGER NOT NULL,
  registry_version  INTEGER NOT NULL,
  occurred_at       TEXT NOT NULL,
  correlation_id    TEXT NOT NULL,
  causation_id      TEXT,
  actor             TEXT NOT NULL,
  payload           TEXT NOT NULL,
  published_at      TEXT,
  attempts          INTEGER NOT NULL DEFAULT 0,
  last_error        TEXT
);
CREATE INDEX IF NOT EXISTS idx_outbox_unpub ON outbox(published_at, seq);
CREATE INDEX IF NOT EXISTS idx_outbox_site ON outbox(site_id, aggregate_version);

-- Идемпотентность команд: один и тот же ключ обязан дать один и тот же ответ,
-- а не вторую запись.
CREATE TABLE IF NOT EXISTS idempotency (
  key         TEXT PRIMARY KEY,
  command     TEXT NOT NULL,
  site_id     TEXT,
  response    TEXT NOT NULL,
  created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  at         TEXT NOT NULL,
  actor      TEXT NOT NULL,
  action     TEXT NOT NULL,
  site_id    TEXT,
  detail     TEXT
);
"""

ПОЛЯ = ("site_id", "canonical_domain", "family", "environment",
        "lifecycle_state", "owner_ref", "template_id", "template_version",
        "build_id", "release_id", "desired_state", "observed_state",
        "integration_refs", "monitoring_profile_ref", "backup_policy_ref",
        "content_profile_ref", "seo_profile_ref", "aggregate_version",
        "created_at", "updated_at")


def сейчас() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def открыть(путь: str | Path) -> sqlite3.Connection:
    п = Path(путь)
    п.parent.mkdir(parents=True, exist_ok=True)
    с = sqlite3.connect(п, timeout=30, isolation_level=None)
    с.row_factory = sqlite3.Row
    с.executescript(DDL)
    return с


class ConflictError(RuntimeError):
    """Ожидаемая версия не совпала либо домен занят."""


def _версия(соед: sqlite3.Connection) -> int:
    return соед.execute("SELECT version FROM registry_version WHERE id=1"
                        ).fetchone()["version"]


def _занят_домен(соед: sqlite3.Connection, домен: str,
                 кроме: str | None = None) -> str | None:
    р = соед.execute("SELECT site_id FROM site WHERE canonical_domain=?",
                     (домен,)).fetchone()
    if р and р["site_id"] != кроме:
        return р["site_id"]
    a = соед.execute("SELECT site_id FROM site_alias WHERE alias=?",
                     (домен,)).fetchone()
    if a and a["site_id"] != кроме:
        return a["site_id"]
    return None


def применить(соед: sqlite3.Connection, *, команда: str, site_id: str,
              поля: dict[str, Any], actor: str, correlation_id: str | None = None,
              causation_id: str | None = None, expected_version: int | None = None,
              aliases: list[str] | None = None) -> dict[str, Any]:
    """Изменить запись и записать событие ОДНОЙ транзакцией.

    `expected_version` — оптимистическая блокировка: команда, рассчитанная на
    версию, которой уже нет, обязана быть отвергнута, а не применена поверх
    чужого изменения.
    """
    тип = {"register": "site.registered.v1", "update": "site.updated.v1",
           "activate": "site.activated.v1", "retire": "site.retired.v1"}[команда]
    корр = correlation_id or str(uuid.uuid4())
    т = сейчас()
    соед.execute("BEGIN IMMEDIATE")
    try:
        текущая = _версия(соед)
        if expected_version is not None and expected_version != текущая:
            raise ConflictError(
                f"ожидалась версия реестра {expected_version}, текущая {текущая}")

        есть = соед.execute("SELECT * FROM site WHERE site_id=?",
                            (site_id,)).fetchone()
        домен = поля.get("canonical_domain") or (есть["canonical_domain"] if есть else None)
        if домен is None:
            raise ValueError("canonical_domain обязателен")
        чужой = _занят_домен(соед, домен, кроме=site_id)
        if чужой:
            raise ConflictError(f"домен {домен} уже принадлежит {чужой}")
        for a in (aliases or []):
            чужой = _занят_домен(соед, a, кроме=site_id)
            if чужой:
                raise ConflictError(f"алиас {a} уже принадлежит {чужой}")

        if есть is None:
            if команда != "register":
                raise ValueError(f"сайта {site_id} нет; команда {команда}")
            агрегат = 1
            значения = {k: поля.get(k) for k in ПОЛЯ}
            значения.update({"site_id": site_id, "canonical_domain": домен,
                             "aggregate_version": 1, "created_at": т,
                             "updated_at": т})
            # setdefault здесь не годится: ключ уже есть со значением None,
            # и столбец NOT NULL его отвергает. Нужна подстановка значения,
            # а не отсутствующего ключа.
            значения["desired_state"] = значения.get("desired_state") or "ACTIVE"
            значения["lifecycle_state"] = значения.get("lifecycle_state") or "DRAFT"
            значения["family"] = значения.get("family") or "unknown"
            значения["environment"] = значения.get("environment") or "non-production"
            значения["integration_refs"] = json.dumps(
                поля.get("integration_refs") or {}, ensure_ascii=False)
            соед.execute(
                "INSERT INTO site(%s) VALUES(%s)" % (
                    ",".join(ПОЛЯ), ",".join("?" * len(ПОЛЯ))),
                [значения.get(k) for k in ПОЛЯ])
        else:
            агрегат = есть["aggregate_version"] + 1
            новые = dict(есть)
            for k, v in поля.items():
                if k in ПОЛЯ and k not in ("site_id", "created_at", "aggregate_version"):
                    новые[k] = (json.dumps(v, ensure_ascii=False)
                                if k == "integration_refs" and not isinstance(v, str) else v)
            if команда == "activate":
                новые["lifecycle_state"] = "ACTIVE"
            if команда == "retire":
                новые["lifecycle_state"] = "RETIRED"
            новые["aggregate_version"] = агрегат
            новые["updated_at"] = т
            соед.execute(
                "UPDATE site SET %s WHERE site_id=?" % ",".join(
                    f"{k}=?" for k in ПОЛЯ if k != "site_id"),
                [новые[k] for k in ПОЛЯ if k != "site_id"] + [site_id])

        if aliases is not None:
            соед.execute("DELETE FROM site_alias WHERE site_id=?", (site_id,))
            for a in aliases:
                соед.execute("INSERT INTO site_alias(alias, site_id) VALUES(?,?)",
                             (a, site_id))

        новая_версия = текущая + 1
        соед.execute("UPDATE registry_version SET version=? WHERE id=1",
                     (новая_версия,))
        запись = dict(соед.execute("SELECT * FROM site WHERE site_id=?",
                                   (site_id,)).fetchone())
        соед.execute(
            "INSERT INTO outbox(event_id, event_type, schema_version, site_id, "
            "aggregate_version, registry_version, occurred_at, correlation_id, "
            "causation_id, actor, payload) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), тип, СХЕМА, site_id, агрегат, новая_версия, т,
             корр, causation_id, actor, json.dumps(запись, ensure_ascii=False)))
        соед.execute(
            "INSERT INTO audit(at, actor, action, site_id, detail) VALUES(?,?,?,?,?)",
            (т, actor, команда, site_id, json.dumps(
                {"registry_version": новая_версия}, ensure_ascii=False)))
        соед.execute("COMMIT")
    except Exception:
        соед.execute("ROLLBACK")
        raise
    return {"site_id": site_id, "aggregate_version": агрегат,
            "registry_version": новая_версия, "correlation_id": корр,
            "event_type": тип}


def снимок(соед: sqlite3.Connection) -> dict[str, Any]:
    """Снимок ACTIVE production. Fixtures и карантин сюда не попадают."""
    строки = [dict(р) for р in соед.execute(
        "SELECT * FROM site WHERE environment='production' "
        "AND lifecycle_state='ACTIVE' ORDER BY site_id")]
    for с in строки:
        с["integration_refs"] = json.loads(с["integration_refs"] or "{}")
        с["aliases"] = [a["alias"] for a in соед.execute(
            "SELECT alias FROM site_alias WHERE site_id=? ORDER BY alias",
            (с["site_id"],))]
    тело = {"schema_version": СХЕМА, "registry_version": _версия(соед),
            "generated_at": сейчас(), "count": len(строки), "sites": строки}
    сырое = json.dumps(тело["sites"], ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")).encode()
    тело["checksum"] = hashlib.sha256(сырое).hexdigest()
    тело["etag"] = 'W/"%s-%d"' % (тело["checksum"][:16], тело["registry_version"])
    return тело


def события(соед: sqlite3.Connection, after: int = 0,
            limit: int = 100) -> dict[str, Any]:
    строки = [dict(р) for р in соед.execute(
        "SELECT * FROM outbox WHERE seq > ? ORDER BY seq LIMIT ?",
        (after, min(limit, 1000)))]
    for с in строки:
        с["payload"] = json.loads(с["payload"])
    return {"schema_version": СХЕМА, "items": строки,
            "next_cursor": строки[-1]["seq"] if строки else after,
            "registry_version": _версия(соед)}
