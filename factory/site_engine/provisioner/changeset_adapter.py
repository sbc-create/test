"""Мост между провайдер-адаптером и контуром изменений.

Второго оркестратора здесь нет и не будет. Последовательность шагов, права,
одобрение, аренда, fencing и журнал принадлежат CORE-003; Provisioner лишь
заводит по набору изменений на каждый внешний ресурс и читает их исходы.

Этот класс переводит один язык на другой: контур спрашивает
`observe/plan/dry_run/apply/verify/rollback`, провайдер отвечает
`observe/plan/apply/reconcile/retire`. Различие не косметическое — у
провайдера нет понятия «сухой прогон», и его обязан обеспечить мост, ни разу
не обратившись к провайдеру на запись.
"""
from __future__ import annotations

from typing import Any

from factory.site_engine.changeset import adapter as A
from factory.site_engine.provisioner.providers.base import ProviderError

#: resource_type контура → (provider_type, resource_kind)
ТИПЫ = {
    "dns.record_set": ("dns", "record_set"),
    "tls.certificate": ("tls", "certificate"),
    "analytics.counter": ("analytics", "counter"),
    "seo.project": ("seo_rank", "project"),
    "template.build": ("template", "counter_tag"),
    # Канонический род ресурса из bundle 1.3.1. Без записи здесь контур не
    # смог бы исполнить ресурс, который контракт уже объявил, — то самое
    # расхождение плана и реализации, ради устранения которого версия и
    # поднималась.
    "template.release": ("template", "counter_tag"),
}


class ProviderTargetAdapter:
    """Один внешний ресурс как цель контура изменений."""

    def __init__(self, провайдер, намерение, связи, *,
                 resource_type: str, changeset_id: str | None = None) -> None:
        self.провайдер = провайдер
        self.намерение = намерение
        self.связи = связи
        self.resource_type = resource_type
        self.changeset_id = changeset_id
        self._эффектов = 0

    @property
    def owner_service(self) -> str:
        """Владелец берётся из канонической матрицы, а не задаётся здесь.

        Жёстко объявленный владелец однажды разойдётся с матрицей, и контур
        отвергнет изменение с OWNERSHIP_MISMATCH — причём отвергнет
        правильно, а искать причину будут в другом месте. Ресурс шаблона
        принадлежит службе templates, внешние ресурсы провайдеров —
        архитектору, и адаптер обязан говорить об этом одно и то же с
        матрицей.
        """
        from factory.site_engine.changeset import model as _M
        return _M.ЕДИНСТВЕННЫЙ_ПИСАТЕЛЬ.get(self.resource_type, "architect")

    # --- контракт контура -------------------------------------------------
    def capabilities(self) -> dict[str, Any]:
        return {"owner_service": self.owner_service,
                "resource_types": [self.resource_type],
                "operations": ["create", "update", "patch", "publish", "rollback"],
                "reversible": True, "dry_run": True,
                "idempotency": "natural_key+idempotency_key",
                "provider_type": self.провайдер.provider_type,
                "live_writes": self.провайдер.live_writes}

    def observe(self, *, site_id: str, resource_id: str) -> dict[str, Any]:
        # Отказ провайдера переводится в ошибку адаптера: контур ловит именно
        # её, а чужой тип исключения прошёл бы мимо обработки и оставил набор
        # изменений навсегда в состоянии VALIDATING.
        try:
            н = self.провайдер.observe(site_id=site_id, intent=self.намерение)
        except ProviderError as ош:
            raise A.AdapterError(ош.error_code, ош.detail) from ош
        состояние = {"exists": н.существует, "external_id": н.external_id,
                     "ownership_proven": н.владение_подтверждено}
        return {"state": состояние,
                # Отпечаток берётся у провайдера: он описывает РЕСУРС, а не
                # наше представление о нём.
                "fingerprint": н.fingerprint or "sha256:отсутствует",
                "resource_type": self.resource_type, "resource_id": resource_id,
                "site_id": site_id, "_наблюдение": н}

    def plan(self, *, site_id: str, resource_id: str, operation: str,
             requested_change: dict[str, Any],
             observed: dict[str, Any]) -> dict[str, Any]:
        н = observed["_наблюдение"]
        try:
            п = self.провайдер.plan(site_id=site_id, intent=self.намерение,
                                    observed=н)
        except ProviderError as ош:
            raise A.AdapterError(ош.error_code, ош.detail) from ош
        return {"diff": {} if п["empty"] else {"target": п["target"]},
                "empty": п["empty"], "reversible": True,
                "before_state": observed["state"],
                "before_fingerprint": observed["fingerprint"],
                "expected_state": {"exists": True},
                "expected_fingerprint": п["expected_fingerprint"],
                "resource_id": resource_id, "operation": operation,
                "provider_plan": п,
                "estimated_cost": п.get("estimated_cost", 0)}

    def dry_run(self, *, site_id: str, plan: dict[str, Any]) -> dict[str, Any]:
        """Ни одного обращения к провайдеру на запись."""
        до = self._эффектов
        итог = {"effects": 0, "would_change": plan["diff"],
                "expected_fingerprint": plan["expected_fingerprint"],
                "estimated_cost": plan.get("estimated_cost", 0)}
        if self._эффектов != до:
            raise A.AdapterError("DRY_RUN_HAD_EFFECTS",
                                 "сухой прогон изменил состояние")
        return итог

    def apply(self, *, site_id: str, plan: dict[str, Any],
              fencing_token: int) -> dict[str, Any]:
        provider_type, resource_kind = ТИПЫ[self.resource_type]
        # Ключ идемпотентности выводится из ПЛАНА и естественного ключа:
        # повтор после обрыва даёт тот же ключ, а другое изменение — другой.
        ключ = (f"{site_id}:{provider_type}:{resource_kind}:"
                f"{plan['expected_fingerprint'][:24]}")
        прежнее = self.связи.начать_действие(
            ключ, site_id=site_id, provider_type=provider_type,
            resource_kind=resource_kind, operation="apply")
        if прежнее and прежнее["state"] == "SUCCEEDED":
            return {"applied": True, "idempotent_replay": True, "effects": 0,
                    "external_id": прежнее["external_id"],
                    "fencing_token": fencing_token}
        try:
            r = self.провайдер.apply(site_id=site_id, plan=plan["provider_plan"],
                                     idempotency_key=ключ)
        except ProviderError as ош:
            self.связи.завершить_действие(ключ, состояние="FAILED",
                                          detail=f"{ош.error_code}: {ош.detail}")
            raise A.AdapterError(ош.error_code, ош.detail) from ош
        self.связи.завершить_действие(ключ, состояние="SUCCEEDED",
                                      external_id=r["external_id"])
        if r.get("created"):
            self._эффектов += 1
        self._записать_связь(site_id, r, происхождение="CREATED"
                             if r.get("created") else "ADOPTED")
        return {"applied": True, "idempotent_replay": False,
                "effects": 1 if r.get("created") else 0,
                "external_id": r["external_id"], "public": self._публичное(r),
                "fencing_token": fencing_token}

    def verify(self, *, site_id: str, plan: dict[str, Any],
               observed: dict[str, Any]) -> dict[str, Any]:
        """Соответствует ли наблюдаемое плану.

        Побайтное равенство отпечатков здесь не годится и не годилось бы
        никогда: провайдер дописывает к объекту СВОИ поля — номер счётчика,
        идентификатор проекта, — которых до создания не существует. Сверка
        отпечатков объявляла бы успешное создание расхождением и отправляла
        в откат только что созданный ресурс.

        Поэтому проверяется вложение: каждое поле, которое мы планировали,
        обязано присутствовать у ресурса и совпадать. Поля, добавленные
        провайдером, расхождением не считаются — мы их не планировали.
        """
        свежее = self.провайдер.reconcile(
            site_id=site_id,
            external_id=(observed["state"].get("external_id")
                         or self._внешний(site_id)))
        ожидалось = (plan.get("provider_plan") or {}).get("target") or {}
        факт = свежее.подробности or {}
        расхождения = {к: {"expected": з, "observed": факт.get(к)}
                       for к, з in ожидалось.items() if факт.get(к) != з}
        совпало = bool(свежее.существует) and not расхождения
        return {"ok": совпало, "verified": совпало,
                "reason": "" if совпало else (
                    "ресурса нет у провайдера" if not свежее.существует
                    else f"поля не совпали: {sorted(расхождения)}"),
                "observed_fingerprint": свежее.fingerprint,
                "expected_fingerprint": plan["expected_fingerprint"],
                "mismatch": расхождения or None,
                "evidence": ["provider_reconcile"]}

    def rollback(self, *, site_id: str, plan: dict[str, Any],
                 before_fingerprint: str, fencing_token: int) -> dict[str, Any]:
        """Компенсация удаляет только созданное ЭТИМ набором изменений."""
        provider_type, resource_kind = ТИПЫ[self.resource_type]
        связь = self.связи.найти(site_id, provider_type, resource_kind)
        if связь is None:
            return {"rolled_back": True, "idempotent_replay": True, "effects": 0}
        if связь.origin != "CREATED":
            # Существовавший ранее или принятый ресурс не наш, чтобы удалять.
            return {"rolled_back": False, "preserved": True, "effects": 0,
                    "reason": f"ресурс {связь.external_id} имеет происхождение "
                              f"{связь.origin}: компенсация его не трогает"}
        r = self.провайдер.удалить(external_id=связь.external_id,
                                   создан_набором=связь.changeset_id,
                                   changeset_id=self.changeset_id)
        return {"rolled_back": bool(r.get("deleted")), "effects": 1,
                "external_id": связь.external_id}

    # --- вспомогательное ---------------------------------------------------
    def _внешний(self, site_id: str) -> str:
        provider_type, resource_kind = ТИПЫ[self.resource_type]
        связь = self.связи.найти(site_id, provider_type, resource_kind)
        return связь.external_id if связь else ""

    @staticmethod
    def _публичное(r: dict) -> dict:
        """Только публичные идентификаторы. Токенов здесь не бывает."""
        return {k: v for k, v in r.items()
                if k in ("public_counter_id", "project_id")}

    def _записать_связь(self, site_id: str, r: dict, *, происхождение: str) -> None:
        from factory.site_engine.provisioner.mapping import Связь
        provider_type, resource_kind = ТИПЫ[self.resource_type]
        self.связи.записать(Связь(
            site_id=site_id, provider_type=provider_type,
            resource_kind=resource_kind, external_id=r["external_id"],
            fingerprint=r.get("fingerprint") or "",
            credential_ref=getattr(self.провайдер, "credential_ref", None),
            lifecycle="CREATED" if происхождение == "CREATED" else "ADOPTED",
            origin=происхождение, changeset_id=self.changeset_id))
