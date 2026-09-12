"""Адаптер контура изменений для предложения SEO-контента.

Второго оркестратора здесь нет: последовательность стадий, права, одобрение,
аренда, ограждение и журнал принадлежат контуру изменений. Адаптер отвечает
на шесть вопросов о ЦЕЛЕВОМ ресурсе — наблюдение, план, сухой прогон,
применение, проверка, откат — и ничего не решает о жизненном цикле.

Наблюдаемое состояние читается заново на каждом шаге. Ответ применения
доказательством не является: адаптер может отчитаться об успехе и не
изменить ничего, и именно ради этого случая проверка существует отдельно.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from factory.site_engine.changeset import model as M
from factory.site_engine.changeset.adapter import AdapterError

from .schema import RESOURCE_KIND, отпечаток

СХЕМА = """
CREATE TABLE IF NOT EXISTS seo_surface (
  site_id     TEXT NOT NULL,
  resource_id TEXT NOT NULL,
  payload     TEXT NOT NULL,
  revision    INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY (site_id, resource_id)
);
-- Счётчик фактических эффектов: по нему проверяется, что повтор не создал
-- второго, а сухой прогон не создал ни одного.
CREATE TABLE IF NOT EXISTS seo_effect (
  seq         INTEGER PRIMARY KEY AUTOINCREMENT,
  site_id     TEXT NOT NULL,
  resource_id TEXT NOT NULL,
  plan_hash   TEXT NOT NULL,
  kind        TEXT NOT NULL,
  at          TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS seo_fault (
  step   TEXT PRIMARY KEY,
  active INTEGER NOT NULL DEFAULT 0
);
"""


class SeoContentAdapter:
    """Цель контура изменений: поверхность SEO одной сущности на витрине."""

    resource_type = RESOURCE_KIND

    def __init__(self, путь: str | Path | None = None):
        self.путь = str(путь or os.environ.get("SEO_SURFACE_DB")
                        or "/tmp/seo-surface.sqlite3")
        Path(self.путь).parent.mkdir(parents=True, exist_ok=True)
        self._соед = sqlite3.connect(self.путь, timeout=30, isolation_level=None)
        self._соед.row_factory = sqlite3.Row
        self._соед.executescript(СХЕМА)

    @property
    def owner_service(self) -> str:
        """Владелец берётся из канонической матрицы, а не объявляется здесь.

        Жёстко вписанный владелец однажды разойдётся с матрицей, контур
        отвергнет изменение с OWNERSHIP_MISMATCH — и отвергнет правильно,
        а искать причину будут не там.
        """
        return M.ЕДИНСТВЕННЫЙ_ПИСАТЕЛЬ.get(self.resource_type, "seo")

    # --- управление испытанием -------------------------------------------

    def сломать(self, шаг: str, включить: bool = True) -> None:
        self._соед.execute(
            "INSERT INTO seo_fault(step, active) VALUES(?,?) "
            "ON CONFLICT(step) DO UPDATE SET active=excluded.active",
            (шаг, 1 if включить else 0))

    def _сломан(self, шаг: str) -> bool:
        р = self._соед.execute("SELECT active FROM seo_fault WHERE step=?",
                               (шаг,)).fetchone()
        return bool(р and р["active"])

    def эффектов(self, *, plan_hash: str | None = None, kind: str | None = None) -> int:
        где, знач = [], []
        if plan_hash:
            где.append("plan_hash=?"); знач.append(plan_hash)
        if kind:
            где.append("kind=?"); знач.append(kind)
        sql = "SELECT count(*) FROM seo_effect" + (
            " WHERE " + " AND ".join(где) if где else "")
        return self._соед.execute(sql, знач).fetchone()[0]

    def посеять(self, site_id: str, resource_id: str, данные: dict) -> None:
        self._соед.execute(
            "INSERT INTO seo_surface(site_id, resource_id, payload) "
            "VALUES(?,?,?) ON CONFLICT(site_id, resource_id) DO UPDATE SET "
            "payload=excluded.payload",
            (site_id, resource_id, json.dumps(данные, ensure_ascii=False)))

    # --- контракт контура -------------------------------------------------

    def capabilities(self) -> dict[str, Any]:
        return {
            "adapter": "seo.content",
            "owner_service": self.owner_service,
            "resource_types": [self.resource_type],
            "operations": ["update", "patch"],
            "reversible_operations": ["update", "patch"],
            "supports_dry_run": True,
            "supports_observe": True,
            "supports_rollback": True,
            "environment": "non-production",
            "live_writes": False,
        }

    def observe(self, *, site_id: str, resource_id: str) -> dict[str, Any]:
        р = self._соед.execute(
            "SELECT payload, revision FROM seo_surface WHERE site_id=? AND "
            "resource_id=?", (site_id, resource_id)).fetchone()
        состояние = json.loads(р["payload"]) if р else {}
        return {"site_id": site_id, "resource_id": resource_id,
                "state": состояние, "revision": р["revision"] if р else 0,
                "fingerprint": отпечаток(состояние), "exists": р is not None}

    def plan(self, *, site_id: str, resource_id: str, operation: str,
             requested_change: dict[str, Any],
             observed: dict[str, Any]) -> dict[str, Any]:
        if operation not in self.capabilities()["operations"]:
            raise AdapterError("OPERATION_UNSUPPORTED",
                               f"операция {operation} адаптером не поддержана")
        операции = requested_change.get("operations") or []
        if not операции:
            raise AdapterError("OPERATIONS_EMPTY", "правок не заявлено")
        было = dict(observed.get("state") or {})
        стало = dict(было)
        for о in операции:
            # Путь — не файловый и не сетевой: это адрес поля внутри
            # поверхности. Разбирается здесь и нигде не исполняется.
            ключ = о["path"].strip("/").replace("/", ".")
            стало[ключ] = о["value_digest"]
        стало["_artifact_digest"] = requested_change.get("artifact_digest")
        diff = {k: {"from": было.get(k), "to": стало[k]}
                for k in sorted(стало) if было.get(k) != стало[k]}
        return {
            "site_id": site_id, "resource_id": resource_id,
            "operation": operation,
            "before_state": было, "expected_state": стало,
            "before_fingerprint": отпечаток(было),
            "expected_fingerprint": отпечаток(стало),
            "diff": diff, "reversible": True, "empty": not diff,
            "proposal_id": requested_change.get("proposal_id"),
        }

    def dry_run(self, *, site_id: str, plan: dict[str, Any]) -> dict[str, Any]:
        # Ни одной записи: ни в поверхность, ни в счётчик эффектов.
        текущее = self.observe(site_id=site_id, resource_id=plan["resource_id"])
        return {"would_change": plan["diff"],
                "current_fingerprint": текущее["fingerprint"],
                "expected_fingerprint": plan["expected_fingerprint"],
                "effects": 0,
                "applicable": текущее["fingerprint"] == plan["before_fingerprint"]}

    def apply(self, *, site_id: str, plan: dict[str, Any],
              fencing_token: int) -> dict[str, Any]:
        if self._сломан("apply"):
            raise AdapterError("ADAPTER_APPLY_FAILED",
                               "отказ применения (испытание)")
        plan_hash = plan.get("plan_hash") or отпечаток(plan)
        текущее = self.observe(site_id=site_id, resource_id=plan["resource_id"])
        if текущее["fingerprint"] == plan["expected_fingerprint"]:
            # Идемпотентность определяется состоянием, а не историей. Спрашивать
            # «применяли ли этот план когда-нибудь» неверно: после отката
            # состояние другое, и повторное применение обязано сработать, иначе
            # возврат вперёд молча ничего не делает.
            return {"applied": False, "idempotent_replay": True,
                    "fingerprint": текущее["fingerprint"]}
        self._соед.execute(
            "INSERT INTO seo_surface(site_id, resource_id, payload, revision) "
            "VALUES(?,?,?,1) ON CONFLICT(site_id, resource_id) DO UPDATE SET "
            "payload=excluded.payload, revision=revision+1",
            (site_id, plan["resource_id"],
             json.dumps(plan["expected_state"], ensure_ascii=False)))
        self._соед.execute(
            "INSERT INTO seo_effect(site_id, resource_id, plan_hash, kind, at) "
            "VALUES(?,?,?,'apply',datetime('now'))",
            (site_id, plan["resource_id"], plan_hash))
        текущее = self.observe(site_id=site_id, resource_id=plan["resource_id"])
        return {"applied": True, "idempotent_replay": False,
                "fingerprint": текущее["fingerprint"],
                "fencing_token": fencing_token}

    def verify(self, *, site_id: str, plan: dict[str, Any],
               observed: dict[str, Any]) -> dict[str, Any]:
        if self._сломан("verify"):
            return {"ok": False, "reason": "отказ проверки (испытание)",
                    "observed_fingerprint": observed["fingerprint"],
                    "expected_fingerprint": plan["expected_fingerprint"]}
        совпало = observed["fingerprint"] == plan["expected_fingerprint"]
        return {"ok": совпало,
                "reason": "" if совпало else "наблюдаемый отпечаток не совпал",
                "observed_fingerprint": observed["fingerprint"],
                "expected_fingerprint": plan["expected_fingerprint"]}

    def rollback(self, *, site_id: str, plan: dict[str, Any],
                 before_fingerprint: str, fencing_token: int) -> dict[str, Any]:
        if self._сломан("rollback"):
            raise AdapterError("ADAPTER_ROLLBACK_FAILED",
                               "отказ отката (испытание)")
        текущее = self.observe(site_id=site_id, resource_id=plan["resource_id"])
        if текущее["fingerprint"] == before_fingerprint:
            return {"restored": False, "idempotent_replay": True,
                    "fingerprint": текущее["fingerprint"]}
        self._соед.execute(
            "INSERT INTO seo_surface(site_id, resource_id, payload, revision) "
            "VALUES(?,?,?,1) ON CONFLICT(site_id, resource_id) DO UPDATE SET "
            "payload=excluded.payload, revision=revision+1",
            (site_id, plan["resource_id"],
             json.dumps(plan["before_state"], ensure_ascii=False)))
        self._соед.execute(
            "INSERT INTO seo_effect(site_id, resource_id, plan_hash, kind, at) "
            "VALUES(?,?,?,'rollback',datetime('now'))",
            (site_id, plan["resource_id"],
             plan.get("plan_hash") or отпечаток(plan)))
        после = self.observe(site_id=site_id, resource_id=plan["resource_id"])
        return {"restored": после["fingerprint"] == before_fingerprint,
                "idempotent_replay": False,
                "fingerprint": после["fingerprint"]}
