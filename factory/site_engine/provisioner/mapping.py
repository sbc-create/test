"""Связи внешних ресурсов с сайтами. Единственный писатель — Provisioner.

Что здесь хранится и чего здесь нет
-----------------------------------

Хранятся только ВНЕШНИЕ и публичные идентификаторы плюс ссылка на credential.
Значения секретов не хранятся никогда: связь должна переживать ротацию
токена, а запись, содержащая сам токен, превращает ротацию в миграцию данных.

Естественный ключ — `site_id + provider_type + resource_kind`. Он же основание
идемпотентности: повтор события или потерянный ответ провайдера не должны
создавать второй объект, и единственный надёжный способ это обеспечить —
искать по ключу ДО создания, а не надеяться на то, что вызов был один.

Состояния связи различают происхождение: CREATED — создано этим контуром,
ADOPTED — существовало раньше и принято под управление. Разница не
косметическая: компенсация вправе удалить только созданное.
"""
from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from typing import Any, Iterable

СОЗДАНО = "CREATED"
ПРИНЯТО = "ADOPTED"
ВЫВЕДЕНО = "RETIRED"
ОШИБКА = "FAILED"
СОСТОЯНИЯ = (СОЗДАНО, ПРИНЯТО, ВЫВЕДЕНО, ОШИБКА)

DDL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS resource_link (
  site_id        TEXT NOT NULL,
  provider_type  TEXT NOT NULL,
  resource_kind  TEXT NOT NULL,
  external_id    TEXT NOT NULL,
  fingerprint    TEXT NOT NULL,
  credential_ref TEXT,
  lifecycle      TEXT NOT NULL,
  origin         TEXT NOT NULL,
  changeset_id   TEXT,
  created_at     TEXT NOT NULL,
  updated_at     TEXT NOT NULL,
  PRIMARY KEY (site_id, provider_type, resource_kind)
);

-- Действия у провайдера. Существует ради ответа на вопрос «мы это уже
-- делали?» после обрыва, когда ответ провайдера потерян, а эффект случился.
CREATE TABLE IF NOT EXISTS provider_action (
  idempotency_key TEXT PRIMARY KEY,
  site_id         TEXT NOT NULL,
  provider_type   TEXT NOT NULL,
  resource_kind   TEXT NOT NULL,
  operation       TEXT NOT NULL,
  state           TEXT NOT NULL,          -- STARTED | SUCCEEDED | FAILED
  external_id     TEXT,
  detail          TEXT,
  started_at      TEXT NOT NULL,
  finished_at     TEXT
);

CREATE TABLE IF NOT EXISTS provider_dlq (
  idempotency_key TEXT PRIMARY KEY,
  payload         TEXT NOT NULL,
  reason          TEXT NOT NULL,
  attempts        INTEGER NOT NULL,
  at              TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def _сейчас() -> str:
    import datetime as d
    return d.datetime.now(d.timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class Связь:
    site_id: str
    provider_type: str
    resource_kind: str
    external_id: str
    fingerprint: str
    credential_ref: str | None
    lifecycle: str
    origin: str
    changeset_id: str | None = None

    @property
    def ключ(self) -> tuple[str, str, str]:
        return (self.site_id, self.provider_type, self.resource_kind)


class Связи:
    """Хранилище связей. Одно на контур."""

    def __init__(self, путь: str) -> None:
        self.соед = sqlite3.connect(путь, timeout=30, isolation_level=None)
        self.соед.row_factory = sqlite3.Row
        self.соед.executescript(DDL)

    def закрыть(self) -> None:
        self.соед.close()

    # --- связи ------------------------------------------------------------
    def найти(self, site_id: str, provider_type: str,
              resource_kind: str) -> Связь | None:
        с = self.соед.execute(
            "SELECT * FROM resource_link WHERE site_id=? AND provider_type=? "
            "AND resource_kind=?", (site_id, provider_type, resource_kind)).fetchone()
        if с is None:
            return None
        return Связь(с["site_id"], с["provider_type"], с["resource_kind"],
                     с["external_id"], с["fingerprint"], с["credential_ref"],
                     с["lifecycle"], с["origin"], с["changeset_id"])

    def записать(self, связь: Связь) -> None:
        if связь.lifecycle not in СОСТОЯНИЯ:
            raise ValueError(f"состояние {связь.lifecycle} не объявлено")
        т = _сейчас()
        self.соед.execute(
            "INSERT INTO resource_link(site_id, provider_type, resource_kind, "
            "external_id, fingerprint, credential_ref, lifecycle, origin, "
            "changeset_id, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(site_id, provider_type, resource_kind) DO UPDATE SET "
            "external_id=excluded.external_id, fingerprint=excluded.fingerprint, "
            "credential_ref=excluded.credential_ref, lifecycle=excluded.lifecycle, "
            "origin=excluded.origin, changeset_id=excluded.changeset_id, "
            "updated_at=excluded.updated_at",
            (связь.site_id, связь.provider_type, связь.resource_kind,
             связь.external_id, связь.fingerprint, связь.credential_ref,
             связь.lifecycle, связь.origin, связь.changeset_id, т, т))

    def по_сайту(self, site_id: str) -> list[Связь]:
        return [Связь(с["site_id"], с["provider_type"], с["resource_kind"],
                      с["external_id"], с["fingerprint"], с["credential_ref"],
                      с["lifecycle"], с["origin"], с["changeset_id"])
                for с in self.соед.execute(
                    "SELECT * FROM resource_link WHERE site_id=? "
                    "ORDER BY provider_type, resource_kind", (site_id,))]

    def вывести_сайт(self, site_id: str) -> int:
        """SiteRetired: связи помечаются, объекты провайдера НЕ удаляются.

        Удаление зоны, счётчика или проекта необратимо и требует отдельного
        решения. Автоматически стирать чужие данные по факту вывода сайта —
        это ровно та «уборка», после которой нечего восстанавливать.
        """
        cur = self.соед.execute(
            "UPDATE resource_link SET lifecycle=?, updated_at=? "
            "WHERE site_id=? AND lifecycle IN (?,?)",
            (ВЫВЕДЕНО, _сейчас(), site_id, СОЗДАНО, ПРИНЯТО))
        return cur.rowcount

    # --- действия у провайдера -------------------------------------------
    def начать_действие(self, ключ: str, *, site_id: str, provider_type: str,
                        resource_kind: str, operation: str) -> dict | None:
        """Отметить намерение ДО вызова провайдера.

        Запись до вызова — единственный способ узнать после обрыва, что
        эффект мог случиться. Отметка после успеха отвечает на вопрос «мы
        закончили», но не на вопрос «мы начинали».
        """
        существует = self.действие(ключ)
        if существует is not None:
            return существует
        self.соед.execute(
            "INSERT INTO provider_action(idempotency_key, site_id, provider_type, "
            "resource_kind, operation, state, started_at) VALUES(?,?,?,?,?,?,?)",
            (ключ, site_id, provider_type, resource_kind, operation,
             "STARTED", _сейчас()))
        return None

    def завершить_действие(self, ключ: str, *, состояние: str,
                           external_id: str | None = None,
                           detail: str | None = None) -> None:
        self.соед.execute(
            "UPDATE provider_action SET state=?, external_id=?, detail=?, "
            "finished_at=? WHERE idempotency_key=?",
            (состояние, external_id, (detail or "")[:400], _сейчас(), ключ))

    def действие(self, ключ: str) -> dict | None:
        с = self.соед.execute(
            "SELECT * FROM provider_action WHERE idempotency_key=?",
            (ключ,)).fetchone()
        return dict(с) if с else None

    def незавершённые(self) -> list[dict]:
        """Начатые и не доведённые — кандидаты на сверку после обрыва."""
        return [dict(с) for с in self.соед.execute(
            "SELECT * FROM provider_action WHERE state='STARTED' "
            "ORDER BY started_at")]

    # --- очередь разбора --------------------------------------------------
    def в_dlq(self, ключ: str, нагрузка: dict, причина: str, попыток: int) -> None:
        self.соед.execute(
            "INSERT OR REPLACE INTO provider_dlq(idempotency_key, payload, "
            "reason, attempts, at) VALUES(?,?,?,?,?)",
            (ключ, json.dumps(нагрузка, ensure_ascii=False), причина[:300],
             попыток, _сейчас()))

    @property
    def глубина_dlq(self) -> int:
        return self.соед.execute("SELECT COUNT(*) c FROM provider_dlq").fetchone()["c"]

    # --- курсор -----------------------------------------------------------
    def курсор(self, имя: str) -> str | None:
        с = self.соед.execute("SELECT value FROM meta WHERE key=?", (f"cursor:{имя}",)).fetchone()
        return с["value"] if с else None

    def записать_курсор(self, имя: str, значение: str) -> None:
        self.соед.execute(
            "INSERT INTO meta(key, value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (f"cursor:{имя}", str(значение)))
