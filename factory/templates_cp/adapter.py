"""Адаптер ресурса Templates для канонического контура изменений.

Реализует ИХ интерфейс `TargetAdapter`, а не свой: машина состояний,
одобрение, аренда, fencing и журнал принадлежат Control Plane. Здесь только
то, что умеет один ресурс — привязка сайта к релизу шаблона.

Границы, которые здесь важны
----------------------------

`observe` отвечает, что привязано СЕЙЧАС, и ничего не пишет. Его результат
входит в `plan_hash`, поэтому он обязан быть детерминированным: живой
манифест витрины сюда не подмешивается — он меняется сам по себе, и план
начал бы отличаться от запуска к запуску без единого изменения заявки.

Сверка с живой витриной — дело `verify`, и там она обязательна: код возврата
исполнителя успехом не является, а привязка, записанная в базу, ещё не
означает, что витрина отдаёт именно этот релиз.

`apply` идемпотентен по `plan_hash`, а не по «мы уже что-то писали». Повтор
после обрыва обязан быть безопасным, иначе доставка at-least-once превращает
каждый обрыв в второй эффект.

Production через этот адаптер не применяется. Выкладка витрины требует
конвейера деплоя, бэкапа и отдельной авторизации; адаптер, способный
переписать боевую привязку «по дороге», был бы именно тем прямым путём в
production, который контур обязан закрывать.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

РЕСУРС = "template.build"
ВЛАДЕЛЕЦ = "templates"
ОПЕРАЦИИ = ("create", "update", "patch", "publish", "rollback")

#: Поля привязки. Перечень закрыт: заявка, приносящая незнакомое поле, — это
#: не расширение, а попытка записать в ресурс то, чего контракт не описывает.
ПОЛЯ_ПРИВЯЗКИ = ("template_family", "design_version", "build_id",
                 "artifact_sha256", "source_commit", "profile")

СХЕМА = """
CREATE TABLE IF NOT EXISTS template_binding (
  site_id     TEXT NOT NULL,
  resource_id TEXT NOT NULL,
  payload     TEXT NOT NULL,
  revision    INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY (site_id, resource_id)
);
-- Счётчик фактических эффектов. Он существует, чтобы «сухой прогон ничего не
-- сделал» и «повтор не создал второго эффекта» были измеримы, а не заявлены.
CREATE TABLE IF NOT EXISTS template_effect (
  seq         INTEGER PRIMARY KEY AUTOINCREMENT,
  site_id     TEXT NOT NULL,
  resource_id TEXT NOT NULL,
  plan_hash   TEXT NOT NULL,
  kind        TEXT NOT NULL
);
-- Что уже применено по этому плану. Основание идемпотентности.
CREATE TABLE IF NOT EXISTS template_applied (
  site_id     TEXT NOT NULL,
  resource_id TEXT NOT NULL,
  plan_hash   TEXT NOT NULL,
  before      TEXT NOT NULL,
  PRIMARY KEY (site_id, resource_id, plan_hash)
);
"""


try:                                    # канонический тип ошибки адаптера
    from factory.site_engine.changeset.adapter import AdapterError as _Базовая
except Exception:                        # вне процесса Control Plane
    _Базовая = RuntimeError


class AdapterError(_Базовая):
    """Отказ адаптера.

    Наследуется от канонической ошибки намеренно: исполнитель ловит именно
    её, и собственный несовместимый тип превратил бы штатный отказ адаптера
    в необработанное исключение посреди применения.
    """

    def __init__(self, code: str, detail: str):
        super().__init__(code, detail) if _Базовая is not RuntimeError \
            else super().__init__(detail)
        self.error_code, self.detail = code, detail


def _отпечаток(данные: Any) -> str:
    сырое = json.dumps(данные, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"))
    return "sha256:" + hashlib.sha256(сырое.encode("utf-8")).hexdigest()


class TemplatesAdapter:
    """Привязка сайта к релизу шаблона."""

    owner_service = ВЛАДЕЛЕЦ
    resource_type = РЕСУРС

    def __init__(self, путь: str | Path | None = None,
                 домены: dict[str, str] | None = None,
                 окружения: dict[str, str] | None = None,
                 открывашка=None) -> None:
        self.путь = str(путь or os.environ.get("TEMPLATES_ADAPTER_DB")
                        or "/var/lib/templates-cp/adapter.sqlite3")
        Path(self.путь).parent.mkdir(parents=True, exist_ok=True)
        self._соед = sqlite3.connect(self.путь, timeout=30, isolation_level=None)
        self._соед.row_factory = sqlite3.Row
        self._соед.executescript(СХЕМА)
        #: Домены и окружения приходят из проекции Registry. Зашитой таблицы
        #: здесь нет: домен — изменяемый атрибут, ключ — site_id.
        self.домены = dict(домены or {})
        self.окружения = dict(окружения or {})
        self._открыть = открывашка or urllib.request.urlopen

    # --- служебное --------------------------------------------------------

    def _привязка(self, site_id: str, resource_id: str) -> dict[str, Any]:
        с = self._соед.execute(
            "SELECT payload, revision FROM template_binding "
            "WHERE site_id=? AND resource_id=?", (site_id, resource_id)).fetchone()
        if с is None:
            return {"bound": False, "binding": None, "revision": 0}
        return {"bound": True, "binding": json.loads(с["payload"]),
                "revision": с["revision"]}

    def _эффект(self, site_id: str, resource_id: str, plan_hash: str,
                вид: str) -> None:
        self._соед.execute(
            "INSERT INTO template_effect(site_id, resource_id, plan_hash, kind) "
            "VALUES(?,?,?,?)", (site_id, resource_id, plan_hash, вид))

    def эффектов(self, site_id: str | None = None) -> int:
        """Сколько фактических эффектов адаптер произвёл."""
        if site_id:
            return self._соед.execute(
                "SELECT COUNT(*) c FROM template_effect WHERE site_id=?",
                (site_id,)).fetchone()["c"]
        return self._соед.execute(
            "SELECT COUNT(*) c FROM template_effect").fetchone()["c"]

    def _запретить_production(self, site_id: str, действие: str) -> None:
        окружение = self.окружения.get(site_id)
        if окружение == "production":
            raise AdapterError(
                "PRODUCTION_APPLY_FORBIDDEN",
                f"{действие} для production-сайта {site_id} через адаптер "
                f"не выполняется: выкладка витрины требует конвейера деплоя, "
                f"бэкапа и отдельной авторизации")

    # --- контракт ---------------------------------------------------------

    def capabilities(self) -> dict[str, Any]:
        return {
            "owner_service": self.owner_service,
            "resource_types": [РЕСУРС],
            "operations": list(ОПЕРАЦИИ),
            "reversible": True,
            "dry_run": True,
            "idempotency": "plan_hash",
            "production_apply": False,
            "verification": "observe_and_compare_fingerprint",
        }

    def observe(self, *, site_id: str, resource_id: str) -> dict[str, Any]:
        состояние = self._привязка(site_id, resource_id)
        return {"state": состояние, "fingerprint": _отпечаток(состояние),
                "resource_type": РЕСУРС, "resource_id": resource_id,
                "site_id": site_id}

    def plan(self, *, site_id: str, resource_id: str, operation: str,
             requested_change: dict[str, Any],
             observed: dict[str, Any]) -> dict[str, Any]:
        if operation not in ОПЕРАЦИИ:
            raise AdapterError("OPERATION_UNSUPPORTED",
                               f"операция {operation} не поддерживается")
        лишние = sorted(set(requested_change) - set(ПОЛЯ_ПРИВЯЗКИ))
        if лишние:
            raise AdapterError(
                "FIELD_UNKNOWN",
                f"поля {лишние} контрактом привязки не описаны")
        было = observed["state"]
        текущая = dict(было.get("binding") or {})
        станет = {**текущая, **{k: v for k, v in requested_change.items()}}
        станет = {k: станет[k] for k in sorted(станет)}
        целевое = {"bound": True, "binding": станет,
                   "revision": (было.get("revision") or 0) + (0 if станет == текущая else 1)}
        diff = {k: {"before": текущая.get(k), "after": станет.get(k)}
                for k in sorted(set(текущая) | set(станет))
                if текущая.get(k) != станет.get(k)}
        return {
            "diff": diff,
            "empty": not diff,
            "reversible": True,
            "before_state": было,
            "before_fingerprint": observed["fingerprint"],
            "expected_state": целевое,
            "expected_fingerprint": _отпечаток(целевое),
            "resource_id": resource_id,
            "operation": operation,
        }

    def dry_run(self, *, site_id: str, plan: dict[str, Any]) -> dict[str, Any]:
        """Ни одной записи. Считается то же, что применилось бы."""
        до = self.эффектов()
        итог = {"effects": 0, "would_change": plan["diff"],
                "expected_fingerprint": plan["expected_fingerprint"],
                "empty": plan["empty"]}
        # Самопроверка: сухой прогон, который что-то записал, обязан быть
        # обнаружен здесь, а не в production.
        if self.эффектов() != до:
            raise AdapterError("DRY_RUN_HAD_EFFECTS",
                               "сухой прогон изменил состояние")
        return итог

    def apply(self, *, site_id: str, plan: dict[str, Any],
              fencing_token: int) -> dict[str, Any]:
        self._запретить_production(site_id, "apply")
        rid, ph = plan["resource_id"], plan["plan_hash"]
        уже = self._соед.execute(
            "SELECT 1 FROM template_applied WHERE site_id=? AND resource_id=? "
            "AND plan_hash=?", (site_id, rid, ph)).fetchone()
        if уже:
            # Повтор — норма, а не ошибка. Второго эффекта не создаём.
            return {"applied": True, "idempotent_replay": True, "effects": 0,
                    "fencing_token": fencing_token}
        if plan["empty"]:
            self._соед.execute(
                "INSERT OR IGNORE INTO template_applied(site_id, resource_id, "
                "plan_hash, before) VALUES(?,?,?,?)",
                (site_id, rid, ph, json.dumps(plan["before_state"], ensure_ascii=False)))
            return {"applied": True, "idempotent_replay": False, "effects": 0,
                    "fencing_token": fencing_token, "empty": True}
        станет = plan["expected_state"]
        self._соед.execute("BEGIN IMMEDIATE")
        try:
            self._соед.execute(
                "INSERT INTO template_binding(site_id, resource_id, payload, revision) "
                "VALUES(?,?,?,?) ON CONFLICT(site_id, resource_id) DO UPDATE SET "
                "payload=excluded.payload, revision=excluded.revision",
                (site_id, rid, json.dumps(станет["binding"], ensure_ascii=False),
                 станет["revision"]))
            self._соед.execute(
                "INSERT INTO template_applied(site_id, resource_id, plan_hash, before) "
                "VALUES(?,?,?,?)",
                (site_id, rid, ph, json.dumps(plan["before_state"], ensure_ascii=False)))
            self._эффект(site_id, rid, ph, "apply")
            self._соед.execute("COMMIT")
        except Exception:
            self._соед.execute("ROLLBACK")
            raise
        return {"applied": True, "idempotent_replay": False, "effects": 1,
                "fencing_token": fencing_token}

    def verify(self, *, site_id: str, plan: dict[str, Any],
               observed: dict[str, Any]) -> dict[str, Any]:
        """Сошлось ли. Состояние читается заново, а не берётся из apply."""
        свежее = self.observe(site_id=site_id, resource_id=plan["resource_id"])
        совпало = свежее["fingerprint"] == plan["expected_fingerprint"]
        расхождение = None
        if not совпало:
            факт = (свежее["state"].get("binding") or {})
            ждали = (plan["expected_state"].get("binding") or {})
            расхождение = {k: {"expected": ждали.get(k), "observed": факт.get(k)}
                           for k in sorted(set(ждали) | set(факт))
                           if ждали.get(k) != факт.get(k)}
        # `ok` и `reason` — имена, которые читает исполнитель. `verified`
        # оставлено для собственных проверок и отчётов.
        итог = {"ok": совпало, "verified": совпало,
                "reason": "" if совпало else f"отпечаток не совпал: {расхождение}",
                "observed_fingerprint": свежее["fingerprint"],
                "expected_fingerprint": plan["expected_fingerprint"],
                "mismatch": расхождение, "evidence": ["observed_state"]}
        живое = self._живой_манифест(site_id)
        if живое is not None:
            итог["live_manifest"] = живое
            итог["evidence"].append("live_manifest")
        return итог

    def rollback(self, *, site_id: str, plan: dict[str, Any],
                 before_fingerprint: str, fencing_token: int) -> dict[str, Any]:
        self._запретить_production(site_id, "rollback")
        rid, ph = plan["resource_id"], plan["plan_hash"]
        сейчас = self.observe(site_id=site_id, resource_id=rid)
        if сейчас["fingerprint"] == before_fingerprint:
            # Уже в исходном состоянии: повторный откат эффекта не создаёт.
            return {"rolled_back": True, "idempotent_replay": True, "effects": 0,
                    "fingerprint": сейчас["fingerprint"]}
        было = plan["before_state"]
        self._соед.execute("BEGIN IMMEDIATE")
        try:
            if не_привязан := not было.get("bound"):
                self._соед.execute(
                    "DELETE FROM template_binding WHERE site_id=? AND resource_id=?",
                    (site_id, rid))
            else:
                self._соед.execute(
                    "INSERT INTO template_binding(site_id, resource_id, payload, revision) "
                    "VALUES(?,?,?,?) ON CONFLICT(site_id, resource_id) DO UPDATE SET "
                    "payload=excluded.payload, revision=excluded.revision",
                    (site_id, rid, json.dumps(было["binding"], ensure_ascii=False),
                     было.get("revision") or 1))
            self._соед.execute(
                "DELETE FROM template_applied WHERE site_id=? AND resource_id=? "
                "AND plan_hash=?", (site_id, rid, ph))
            self._эффект(site_id, rid, ph, "rollback")
            self._соед.execute("COMMIT")
        except Exception:
            self._соед.execute("ROLLBACK")
            raise
        стало = self.observe(site_id=site_id, resource_id=rid)
        return {"rolled_back": стало["fingerprint"] == before_fingerprint,
                "idempotent_replay": False, "effects": 1,
                "fingerprint": стало["fingerprint"],
                "restored_unbound": bool(не_привязан)}

    # --- сверка с живой витриной -----------------------------------------

    def _живой_манифест(self, site_id: str) -> dict[str, Any] | None:
        """Что витрина отдаёт на самом деле. Только чтение, отказ не фатален."""
        домен = self.домены.get(site_id)
        if not домен:
            return None
        зпр = urllib.request.Request(
            f"https://{домен}/__template_version",
            headers={"User-Agent": "site-factory-templates-adapter/1.0 (read-only)"})
        try:
            with self._открыть(зпр, timeout=20) as о:
                данные = json.loads(о.read().decode("utf-8"))
        except Exception as ош:
            return {"reachable": False, "reason": type(ош).__name__}
        return {"reachable": True,
                **{k: данные.get(k) for k in ПОЛЯ_ПРИВЯЗКИ}}

    def закрыть(self) -> None:
        self._соед.close()
