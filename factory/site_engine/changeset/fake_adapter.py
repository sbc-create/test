"""Детерминированный адаптер для проверки механизма.

Существует только ради испытаний. Хранит состояние в отдельной эфемерной базе
и умеет по команде отказать на нужном шаге — иначе проверить поведение при
неудачной проверке или неудачном откате было бы нечем, кроме веры.

Никакого отношения к реальным шаблонам, контенту, SEO и провайдерам не имеет
и иметь не должен.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from .adapter import AdapterError

СХЕМА = """
CREATE TABLE IF NOT EXISTS fake_resource (
  site_id     TEXT NOT NULL,
  resource_id TEXT NOT NULL,
  payload     TEXT NOT NULL,
  revision    INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY (site_id, resource_id)
);
-- Счётчик реальных эффектов. По нему проверяется, что повтор применения не
-- создал второго эффекта, а сухой прогон не создал ни одного.
CREATE TABLE IF NOT EXISTS fake_effect (
  seq        INTEGER PRIMARY KEY AUTOINCREMENT,
  site_id    TEXT NOT NULL,
  resource_id TEXT NOT NULL,
  plan_hash  TEXT NOT NULL,
  kind       TEXT NOT NULL,
  at         TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS fake_fault (
  step   TEXT PRIMARY KEY,
  active INTEGER NOT NULL DEFAULT 0
);
"""


def _отпечаток(данные: Any) -> str:
    return hashlib.sha256(json.dumps(данные, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


class FakeAdapter:
    """Адаптер-пустышка с наблюдаемым состоянием и управляемыми отказами."""

    owner_service = "control-plane"
    resource_type = "fake.resource"

    def __init__(self, путь: str | Path | None = None):
        self.путь = str(путь or os.environ.get("FAKE_ADAPTER_DB")
                        or "/tmp/fake-adapter.sqlite3")
        Path(self.путь).parent.mkdir(parents=True, exist_ok=True)
        self._соед = sqlite3.connect(self.путь, timeout=30, isolation_level=None)
        self._соед.row_factory = sqlite3.Row
        self._соед.executescript(СХЕМА)

    # --- управление испытанием ------------------------------------------

    def сломать(self, шаг: str, включить: bool = True) -> None:
        """Заставить отказать конкретный шаг: apply, verify или rollback."""
        self._соед.execute(
            "INSERT INTO fake_fault(step, active) VALUES(?,?) "
            "ON CONFLICT(step) DO UPDATE SET active=excluded.active",
            (шаг, 1 if включить else 0))

    def _сломан(self, шаг: str) -> bool:
        р = self._соед.execute("SELECT active FROM fake_fault WHERE step=?",
                               (шаг,)).fetchone()
        return bool(р and р["active"])

    def эффектов(self, *, plan_hash: str | None = None) -> int:
        if plan_hash:
            return self._соед.execute(
                "SELECT count(*) FROM fake_effect WHERE plan_hash=?",
                (plan_hash,)).fetchone()[0]
        return self._соед.execute("SELECT count(*) FROM fake_effect").fetchone()[0]

    def посеять(self, site_id: str, resource_id: str, данные: dict) -> None:
        self._соед.execute(
            "INSERT INTO fake_resource(site_id, resource_id, payload) "
            "VALUES(?,?,?) ON CONFLICT(site_id, resource_id) DO UPDATE SET "
            "payload=excluded.payload",
            (site_id, resource_id, json.dumps(данные, ensure_ascii=False)))

    # --- контракт адаптера ----------------------------------------------

    def capabilities(self) -> dict[str, Any]:
        return {
            "adapter": "fake",
            "owner_service": self.owner_service,
            "resource_types": [self.resource_type],
            "operations": ["create", "update", "patch"],
            "reversible_operations": ["create", "update", "patch"],
            "supports_dry_run": True,
            "supports_observe": True,
            "supports_rollback": True,
            "environment": "test",
        }

    def observe(self, *, site_id: str, resource_id: str) -> dict[str, Any]:
        р = self._соед.execute(
            "SELECT payload, revision FROM fake_resource WHERE site_id=? AND "
            "resource_id=?", (site_id, resource_id)).fetchone()
        состояние = json.loads(р["payload"]) if р else {}
        return {"site_id": site_id, "resource_id": resource_id,
                "state": состояние, "revision": р["revision"] if р else 0,
                "fingerprint": _отпечаток(состояние), "exists": р is not None}

    def plan(self, *, site_id: str, resource_id: str, operation: str,
             requested_change: dict[str, Any],
             observed: dict[str, Any]) -> dict[str, Any]:
        if operation not in self.capabilities()["operations"]:
            raise AdapterError("OPERATION_UNSUPPORTED",
                               f"операция {operation} адаптером не поддержана")
        было = dict(observed.get("state") or {})
        стало = dict(было)
        стало.update(requested_change)
        diff = {k: {"from": было.get(k), "to": стало[k]}
                for k in sorted(стало) if было.get(k) != стало[k]}
        return {
            "site_id": site_id, "resource_id": resource_id,
            "operation": operation,
            "before_state": было, "expected_state": стало,
            "before_fingerprint": _отпечаток(было),
            "expected_fingerprint": _отпечаток(стало),
            "diff": diff, "reversible": True,
            "empty": not diff,
        }

    def dry_run(self, *, site_id: str, plan: dict[str, Any]) -> dict[str, Any]:
        # Ни одной записи: ни в ресурс, ни в счётчик эффектов. Сухой прогон,
        # оставляющий след, перестаёт быть сухим.
        текущее = self.observe(site_id=site_id, resource_id=plan["resource_id"])
        return {"would_change": plan["diff"],
                "current_fingerprint": текущее["fingerprint"],
                "expected_fingerprint": plan["expected_fingerprint"],
                "effects": 0,
                "applicable": текущее["fingerprint"] == plan["before_fingerprint"]}

    def apply(self, *, site_id: str, plan: dict[str, Any],
              fencing_token: int) -> dict[str, Any]:
        if self._сломан("apply"):
            raise AdapterError("ADAPTER_APPLY_FAILED", "отказ применения (испытание)")
        plan_hash = plan.get("plan_hash") or _отпечаток(plan)
        уже = self._соед.execute(
            "SELECT count(*) FROM fake_effect WHERE plan_hash=? AND kind='apply'",
            (plan_hash,)).fetchone()[0]
        if уже:
            # Повтор того же плана эффекта не создаёт: состояние уже такое,
            # какое план и требовал.
            текущее = self.observe(site_id=site_id, resource_id=plan["resource_id"])
            return {"applied": False, "idempotent_replay": True,
                    "fingerprint": текущее["fingerprint"]}
        self._соед.execute(
            "INSERT INTO fake_resource(site_id, resource_id, payload, revision) "
            "VALUES(?,?,?,1) ON CONFLICT(site_id, resource_id) DO UPDATE SET "
            "payload=excluded.payload, revision=revision+1",
            (site_id, plan["resource_id"],
             json.dumps(plan["expected_state"], ensure_ascii=False)))
        self._соед.execute(
            "INSERT INTO fake_effect(site_id, resource_id, plan_hash, kind, at) "
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
            "INSERT INTO fake_resource(site_id, resource_id, payload, revision) "
            "VALUES(?,?,?,1) ON CONFLICT(site_id, resource_id) DO UPDATE SET "
            "payload=excluded.payload, revision=revision+1",
            (site_id, plan["resource_id"],
             json.dumps(plan["before_state"], ensure_ascii=False)))
        self._соед.execute(
            "INSERT INTO fake_effect(site_id, resource_id, plan_hash, kind, at) "
            "VALUES(?,?,?,'rollback',datetime('now'))",
            (site_id, plan["resource_id"],
             plan.get("plan_hash") or _отпечаток(plan)))
        после = self.observe(site_id=site_id, resource_id=plan["resource_id"])
        return {"restored": после["fingerprint"] == before_fingerprint,
                "idempotent_replay": False,
                "fingerprint": после["fingerprint"]}
