"""Исполнение набора изменений: канарейка, проверка, откат.

Порядок шагов выбран так, чтобы каждое утверждение об успехе опиралось на
наблюдение, а не на сообщение исполнителя:

* до применения снимается отпечаток «как было» — без него откат некуда вести;
* намерение записывается в журнал ДО внешнего эффекта;
* проверка читает состояние заново;
* при несовпадении запускается компенсация, и её результат тоже проверяется.

Канарейка идёт первой и одна. Если она не прошла, остальные цели не
затрагиваются вовсе — в этом весь смысл: остановиться дешевле, чем чинить.
"""
from __future__ import annotations

import json
from typing import Any

from . import adapter as A
from . import audit_bridge as AB
from . import model as M
from . import planner as P
from . import policy as POL
from . import store as S
from .registry_client import RegistryClient


class Engine:
    def __init__(self, соед, *, адаптер: A.TargetAdapter | None = None,
                 реестр: RegistryClient | None = None,
                 требовать_журнал: bool = True):
        self.соед = соед
        self.адаптер = адаптер
        self.реестр = реестр or RegistryClient()
        # Требование журнала можно снять только для проверок самого механизма.
        # В рабочем контуре изменение без записи о нём недопустимо.
        self.требовать_журнал = требовать_журнал

    # --- валидация -------------------------------------------------------

    def валидировать(self, cid: str, *, actor_id: str, служба: str) -> dict:
        набор = S.получить(self.соед, cid)
        if набор is None:
            raise S.ChangeSetError("CHANGESET_NOT_FOUND", "набора нет", 404)
        S.применить_переход(self.соед, cid, "validate", actor_id=actor_id,
                            служба=служба, роль=M.VALIDATOR)
        try:
            план = P.спланировать(набор, реестр=self.реестр, адаптер=self.адаптер)
            сухо = P.сухой_прогон(план, адаптер=self.адаптер,
                                  resource_type=набор["resource_type"])
            if сухо["effects"] != 0:
                raise S.ChangeSetError(
                    "DRY_RUN_HAD_EFFECTS",
                    f"сухой прогон создал {сухо['effects']} эффектов", 500)
            POL.применение_разрешено(набор, set(план["environments"]))
        except S.ChangeSetError as e:
            S.применить_переход(self.соед, cid, "validate_fail",
                                actor_id=actor_id, служба=служба,
                                роль=M.VALIDATOR, reason=f"{e.error_code}: {e.detail}",
                                поля={"failure_reason": f"{e.error_code}: {e.detail}"})
            raise
        S.применить_переход(
            self.соед, cid, "validate_ok", actor_id=actor_id, служба=служба,
            роль=M.VALIDATOR,
            поля={"plan_hash": план["plan_hash"],
                  "base_registry_version": план["base_registry_version"],
                  "expected_resource_fingerprint":
                      план["expected_resource_fingerprint"],
                  "risk_class": план["risk_class"],
                  "verification_plan": план["verification_plan"],
                  "rollback_plan": план["rollback_plan"],
                  "dry_run_result": {**сухо, "per_site_plan": план["per_site_plan"],
                                     "environments": план["environments"]}})
        return {"changeset_id": cid, "plan_hash": план["plan_hash"],
                "risk_class": план["risk_class"],
                "environments": план["environments"],
                "dry_run_effects": сухо["effects"]}

    # --- одобрение -------------------------------------------------------

    def запросить_одобрение(self, cid: str, *, actor_id: str, служба: str,
                            expires_at: str) -> dict:
        return S.применить_переход(
            self.соед, cid, "request_approval", actor_id=actor_id,
            служба=служба, роль=M.PROPOSER, поля={"expires_at": expires_at})

    def одобрить(self, cid: str, *, approver_id: str, служба: str,
                 actor_type: str, expires_at: str, reason: str = "") -> dict:
        набор = S.получить(self.соед, cid)
        if набор is None:
            raise S.ChangeSetError("CHANGESET_NOT_FOUND", "набора нет", 404)
        POL.проверить_действие_модели(actor_type, "approve")
        запись = POL.одобрить(набор, approver_id=approver_id,
                              approver_service=служба, approver_type=actor_type,
                              expires_at=expires_at, reason=reason)
        return S.применить_переход(
            self.соед, cid, "approve", actor_id=approver_id, служба=служба,
            роль=M.APPROVER, reason=reason,
            поля={"approval": запись, "expires_at": expires_at})

    def отозвать_одобрение(self, cid: str, *, actor_id: str) -> dict:
        """Отзыв не стирает запись, а помечает её недействительной."""
        набор = S.получить(self.соед, cid)
        запись = dict(набор.get("approval") or {})
        if not запись:
            raise S.ChangeSetError("APPROVAL_REQUIRED", "одобрения нет", 409)
        запись["revoked_at"] = S.сейчас()
        запись["revoked_by"] = actor_id
        self.соед.execute("UPDATE changeset SET approval=?, updated_at=? "
                          "WHERE changeset_id=?",
                          (S.канон(запись), S.сейчас(), cid))
        return {"changeset_id": cid, "revoked": True}

    # --- применение ------------------------------------------------------

    def применить(self, cid: str, *, actor_id: str, служба: str,
                  fencing_token: int) -> dict:
        """Применить одобренный набор или довести до конца прерванный.

        Возобновление — не отдельный режим и не отдельный код. Процесс,
        убитый на середине, оставляет набор в APPLYING или VERIFYING; тогда
        повторные проверки одобрения и дрейфа не нужны (они уже пройдены), а
        переход в APPLYING уже состоялся. Идемпотентность адаптера делает
        повторный проход по уже применённым целям безвредным.
        """
        набор = S.получить(self.соед, cid)
        if набор is None:
            raise S.ChangeSetError("CHANGESET_NOT_FOUND", "набора нет", 404)
        if набор["status"] in (M.APPLYING, M.VERIFYING):
            return self._прогнать_цели(набор, actor_id=actor_id, служба=служба,
                                       fencing_token=fencing_token,
                                       возобновление=True)

        # Проверки идут до перехода в APPLYING: сначала выясняем, вправе ли
        # мы вообще начинать, и только потом объявляем, что начали.
        POL.проверить_одобрение(набор, сейчас_utc=S.сейчас())
        дрейф = P.обнаружить_дрейф(набор, реестр=self.реестр, адаптер=self.адаптер)
        if дрейф["stale"]:
            S.применить_переход(
                self.соед, cid, "mark_stale_approved", actor_id=actor_id,
                служба=служба, роль=M.EXECUTOR,
                reason=f"дрейф: {дрейф['drift']}",
                поля={"failure_reason": S.канон(дрейф["drift"])})
            raise S.ChangeSetError("PLAN_STALE",
                                   f"план устарел: {дрейф['drift']}", 409)
        планы = набор["dry_run_result"]["per_site_plan"]
        POL.применение_разрешено(
            набор, set(набор["dry_run_result"].get("environments") or []))

        if self.требовать_журнал and not AB.доступен():
            # Внешний эффект без возможности его записать запрещён: изменение,
            # которого нет в истории, нельзя ни проверить, ни отменить осознанно.
            raise S.ChangeSetError(
                "AUDIT_LEDGER_UNAVAILABLE",
                "журнал аудита недоступен: изменения заблокированы", 503)

        S.применить_переход(self.соед, cid, "apply", actor_id=actor_id,
                            служба=служба, роль=M.EXECUTOR,
                            fencing_token=fencing_token)
        набор = S.получить(self.соед, cid)
        return self._прогнать_цели(набор, actor_id=actor_id, служба=служба,
                                   fencing_token=fencing_token,
                                   возобновление=False)

    def _прогнать_цели(self, набор: dict, *, actor_id: str, служба: str,
                       fencing_token: int, возобновление: bool) -> dict:
        cid = набор["changeset_id"]
        планы = набор["dry_run_result"]["per_site_plan"]
        ад = self.адаптер or A.получить(набор["resource_type"])

        канареи = [t["site_id"] for t in набор["targets"] if t["is_canary"]]
        прочие = [t["site_id"] for t in набор["targets"] if not t["is_canary"]]
        порядок = канареи + прочие
        применённые: list[str] = []
        итоги: dict[str, Any] = {}

        for site_id in порядок:
            п = планы[site_id]
            состояние_цели = next(
                (t["state"] for t in набор["targets"] if t["site_id"] == site_id),
                "PENDING")
            if возобновление and состояние_цели == "SUCCEEDED":
                # Цель уже доведена в прошлый раз. Повторять применение к ней
                # не нужно и незачем: её отпечаток уже проверен.
                применённые.append(site_id)
                continue
            наблюдение_до = ад.observe(site_id=site_id,
                                       resource_id=набор["resource_id"])
            S.обновить_цель(self.соед, cid, site_id, state="APPLYING",
                            before=наблюдение_до["fingerprint"])
            try:
                r = ад.apply(site_id=site_id, plan=п, fencing_token=fencing_token)
            except A.AdapterError as e:
                S.обновить_цель(self.соед, cid, site_id, state="APPLY_FAILED",
                                detail=f"{e.error_code}: {e.detail}")
                S.применить_переход(
                    self.соед, cid, "apply_fail", actor_id=actor_id,
                    служба=служба, роль=M.EXECUTOR, fencing_token=fencing_token,
                    reason=f"{site_id}: {e.error_code}",
                    поля={"failure_reason": f"{site_id}: {e.detail}"})
                return {"changeset_id": cid, "status": M.APPLY_FAILED,
                        "failed_target": site_id, "applied": применённые}

            наблюдение_после = ад.observe(site_id=site_id,
                                          resource_id=набор["resource_id"])
            проверка = ад.verify(site_id=site_id, plan=п,
                                 observed=наблюдение_после)
            итоги[site_id] = {"apply": r, "verify": проверка,
                              "observed": наблюдение_после["fingerprint"]}
            if not проверка["ok"]:
                S.обновить_цель(self.соед, cid, site_id, state="VERIFY_FAILED",
                                after=наблюдение_после["fingerprint"],
                                detail=проверка.get("reason", ""))
                # Канарейка не прошла — остальные цели не трогаем вовсе.
                if S.получить(self.соед, cid)["status"] == M.APPLYING:
                    S.применить_переход(
                        self.соед, cid, "applied", actor_id=actor_id,
                        служба=служба, роль=M.EXECUTOR,
                        fencing_token=fencing_token)
                S.применить_переход(
                    self.соед, cid, "verify_fail", actor_id=actor_id,
                    служба=служба, роль=M.EXECUTOR, fencing_token=fencing_token,
                    reason=f"{site_id}: {проверка.get('reason')}",
                    поля={"failure_reason": f"{site_id}: {проверка.get('reason')}"})
                откат = self.откатить(cid, actor_id=actor_id, служба=служба,
                                      fencing_token=fencing_token,
                                      цели=применённые + [site_id])
                return {"changeset_id": cid, "status": откат["status"],
                        "canary_failed": site_id,
                        "untouched_targets": [s for s in порядок
                                              if s not in применённые
                                              and s != site_id],
                        "rollback": откат, "results": итоги}
            S.обновить_цель(self.соед, cid, site_id, state="SUCCEEDED",
                            after=наблюдение_после["fingerprint"])
            применённые.append(site_id)

        if S.получить(self.соед, cid)["status"] == M.APPLYING:
            S.применить_переход(self.соед, cid, "applied", actor_id=actor_id,
                                служба=служба, роль=M.EXECUTOR,
                                fencing_token=fencing_token)
        S.применить_переход(self.соед, cid, "verify_ok", actor_id=actor_id,
                            служба=служба, роль=M.EXECUTOR,
                            fencing_token=fencing_token)
        return {"changeset_id": cid, "status": M.SUCCEEDED,
                "applied": применённые, "results": итоги}

    # --- откат -----------------------------------------------------------

    def откатить(self, cid: str, *, actor_id: str, служба: str,
                 fencing_token: int, цели: list[str] | None = None) -> dict:
        набор = S.получить(self.соед, cid)
        ад = self.адаптер or A.получить(набор["resource_type"])
        планы = набор["dry_run_result"]["per_site_plan"]
        отпечатки = {t["site_id"]: t["before_fingerprint"]
                     for t in набор["targets"]}
        список = цели or [t["site_id"] for t in набор["targets"]
                          if t["state"] in ("SUCCEEDED", "VERIFY_FAILED")]
        неудачи = []
        for site_id in список:
            было = отпечатки.get(site_id) or планы[site_id]["before_fingerprint"]
            try:
                r = ад.rollback(site_id=site_id, plan=планы[site_id],
                                before_fingerprint=было,
                                fencing_token=fencing_token)
            except A.AdapterError as e:
                неудачи.append(f"{site_id}: {e.error_code}")
                S.обновить_цель(self.соед, cid, site_id,
                                state="ROLLBACK_FAILED", detail=e.detail)
                continue
            # Успех отката тоже проверяется наблюдением, а не ответом адаптера.
            текущее = ад.observe(site_id=site_id, resource_id=набор["resource_id"])
            if текущее["fingerprint"] != было:
                неудачи.append(f"{site_id}: отпечаток после отката не совпал")
                S.обновить_цель(self.соед, cid, site_id,
                                state="ROLLBACK_FAILED",
                                after=текущее["fingerprint"])
                continue
            S.обновить_цель(self.соед, cid, site_id, state="ROLLED_BACK",
                            after=текущее["fingerprint"])

        if неудачи:
            S.применить_переход(
                self.соед, cid, "rollback_fail", actor_id=actor_id,
                служба=служба, роль=M.EXECUTOR, fencing_token=fencing_token,
                reason="; ".join(неудачи)[:400],
                поля={"failure_reason": "; ".join(неудачи)[:400]})
            S.применить_переход(
                self.соед, cid, "escalate", actor_id=actor_id, служба=служба,
                роль=M.EXECUTOR,
                reason="автоматические попытки отката исчерпаны")
            return {"changeset_id": cid,
                    "status": M.MANUAL_INTERVENTION_REQUIRED,
                    "failures": неудачи}
        S.применить_переход(self.соед, cid, "rollback_ok", actor_id=actor_id,
                            служба=служба, роль=M.EXECUTOR,
                            fencing_token=fencing_token)
        return {"changeset_id": cid, "status": M.ROLLED_BACK,
                "restored": список}
