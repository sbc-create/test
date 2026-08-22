"""
Безопасный адаптер CMS-мутаций.

Порядок неизменен: snapshot -> guardrails+manifest -> rollback dry-run ->
apply -> audit. Любой сбой на любом шаге => изменение не применяется.
CMS-контентные операции не требуют git-коммита, но всегда имеют audit record.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

from . import config
from .audit import AuditLog
from .guardrails import (AuthorizationBlocked, GuardrailViolation, MutationRequest,
                         authorize_mutation)
from .state import Store


class CMSBackend(Protocol):
    """Контракт CMS. Реальная реализация приходит от development-контура."""

    contract_version: str

    def read(self, site_id: str, target: str) -> dict[str, Any]: ...
    def write(self, site_id: str, target: str, payload: dict[str, Any]) -> dict[str, Any]: ...


class UnconfiguredCMS:
    """Заглушка: честно отказывает вместо тихого no-op."""
    contract_version = "0.0.0"

    def read(self, site_id: str, target: str) -> dict[str, Any]:
        raise AuthorizationBlocked(
            f"CMS не подключена (site={site_id}).",
            {"site": site_id, "needs": "secret://cms/seo-operator + DATA_SOURCE_REGISTRY.cms_content_api.status=available"})

    def write(self, site_id: str, target: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.read(site_id, target)


class InMemoryCMS:
    """Backend для dry-run, тестов и demo-* сайтов."""
    contract_version = "0.1.0"

    def __init__(self, initial: dict[str, dict[str, Any]] | None = None) -> None:
        self._data: dict[str, dict[str, Any]] = initial or {}

    def _key(self, site_id: str, target: str) -> str:
        return f"{site_id}::{target}"

    def read(self, site_id: str, target: str) -> dict[str, Any]:
        return json.loads(json.dumps(self._data.get(self._key(site_id, target), {})))

    def write(self, site_id: str, target: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._data[self._key(site_id, target)] = json.loads(json.dumps(payload))
        return self.read(site_id, target)


@dataclass
class MutationResult:
    applied: bool
    site_id: str
    target: str
    action: str
    experiment_id: str | None
    snapshot_id: int | None
    audit_seq: int | None
    dry_run: bool
    before: dict[str, Any] = field(default_factory=dict)
    after: dict[str, Any] = field(default_factory=dict)
    rollback_payload: dict[str, Any] = field(default_factory=dict)
    message: str = ""


class CMSAdapter:
    def __init__(self, backend: CMSBackend, store: Store, audit: AuditLog) -> None:
        self.backend = backend
        self.store = store
        self.audit = audit

    def _check_contract(self, site_id: str) -> None:
        site = config.get_site(site_id)
        expected = site.raw.get("cms_contract_version")
        actual = getattr(self.backend, "contract_version", None)
        if expected and actual and expected.split(".")[0] != actual.split(".")[0]:
            raise AuthorizationBlocked(
                f"Несовместимая версия CMS-контракта: ожидается {expected}, доступна {actual}.",
                {"site": site_id, "needs": "согласовать контракт с development-контуром"})

    def mutate(self, *, site_id: str, target: str, action: str, tier: int,
               new_payload: dict[str, Any], experiment_id: str | None,
               guard_payload: dict[str, Any] | None = None,
               dry_run: bool = True, is_defect_fix: bool = False) -> MutationResult:
        self._check_contract(site_id)

        # 1. Snapshot ДО любых проверок изменения — иначе нечего откатывать.
        before = self.backend.read(site_id, target)

        rollback_payload = {
            "executable": True,
            "kind": "cms_restore",
            "site_id": site_id,
            "target": target,
            "restore": before,
            "experiment_id": experiment_id,
        }

        req = MutationRequest(
            site_id=site_id, action=action, tier=tier, experiment_id=experiment_id,
            before_snapshot=before if before else {"_empty": True},
            rollback_payload=rollback_payload,
            payload=dict(guard_payload or {}, **{"target": target}),
            is_defect_fix=is_defect_fix,
        )

        # 2. Оба слоя: guardrails и manifest. Исключения наверх — цикл их поймает.
        authorize_mutation(req)

        # 3. Rollback проверяется до применения.
        if not self._rollback_dry_run(rollback_payload):
            raise GuardrailViolation("GR-006", "Rollback dry-run не прошёл — изменение не применяется.")

        if dry_run:
            rec = self.audit.append(
                actor="seo-operator", action=f"dry_run:{action}",
                payload={"target": target, "before": before, "proposed": new_payload},
                site_id=site_id, experiment_id=experiment_id)
            return MutationResult(
                applied=False, site_id=site_id, target=target, action=action,
                experiment_id=experiment_id, snapshot_id=None, audit_seq=rec.seq,
                dry_run=True, before=before, after=new_payload,
                rollback_payload=rollback_payload,
                message="DRY-RUN: изменение проверено и не применено.")

        # 4. Снапшот в durable store, затем запись.
        snapshot_id = self.store.save_snapshot(
            site_id=site_id, target=target, before=before,
            rollback_payload=rollback_payload, experiment_id=experiment_id)

        after = self.backend.write(site_id, target, new_payload)
        self.store.set_snapshot_after(snapshot_id, after)

        rec = self.audit.append(
            actor="seo-operator", action=action,
            payload={"target": target, "before": before, "after": after,
                     "snapshot_id": snapshot_id, "tier": tier},
            site_id=site_id, experiment_id=experiment_id)

        return MutationResult(
            applied=True, site_id=site_id, target=target, action=action,
            experiment_id=experiment_id, snapshot_id=snapshot_id, audit_seq=rec.seq,
            dry_run=False, before=before, after=after, rollback_payload=rollback_payload,
            message="Изменение применено со снапшотом и audit record.")

    def _rollback_dry_run(self, payload: dict[str, Any]) -> bool:
        return bool(payload.get("executable")) and payload.get("kind") in {
            "cms_restore", "homepage_reorder"} and "site_id" in payload

    def rollback(self, experiment_id: str) -> list[MutationResult]:
        """Откатывает все неоткаченные снапшоты эксперимента, начиная с последнего."""
        results = []
        for row in self.store.snapshots_for(experiment_id):
            payload = json.loads(row["rollback_payload"])
            target = row["target"]
            site_id = row["site_id"]
            restored = self.backend.write(site_id, target, payload["restore"])
            self.store.mark_rolled_back(row["id"])
            rec = self.audit.append(
                actor="seo-operator", action="rollback",
                payload={"target": target, "restored_to": payload["restore"], "snapshot_id": row["id"]},
                site_id=site_id, experiment_id=experiment_id)
            results.append(MutationResult(
                applied=True, site_id=site_id, target=target, action="rollback",
                experiment_id=experiment_id, snapshot_id=row["id"], audit_seq=rec.seq,
                dry_run=False, before=json.loads(row["after"] or "{}"), after=restored,
                rollback_payload=payload, message="Откат выполнен."))
        return results
