"""Политика: разделение ролей и привязка одобрения к плану.

Одобрение здесь — не флаг «разрешено», а утверждение о КОНКРЕТНОМ плане для
КОНКРЕТНЫХ целей. Поэтому оно связано хэшем со всем, изменение чего меняет
смысл разрешения: план, цели, версия реестра, версия политики, класс риска,
срок. Любая правка после одобрения делает подпись недействительной
арифметически, а не по доброй воле исполнителя.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Any

from . import model as M
from .store import ChangeSetError, канон, сейчас

POLICY_VERSION = "policy/1.0.0"

#: Автономное применение в production выключено. Это не настройка «по
#: умолчанию», а состояние, которое нельзя включить, пока не закрыты долги,
#: перечисленные в ДОЛГИ_БЛОКИРУЮЩИЕ_АВТОНОМИЮ.
AUTONOMOUS_PRODUCTION_APPLY = False

ДОЛГИ_БЛОКИРУЮЩИЕ_АВТОНОМИЮ = (
    "REGISTRY_CORE_GIT_PROVENANCE",
    "OFF_HOST_BACKUP",
    "LIVE_CONSUMER_ADAPTERS",
)

#: Окружения, где применение разрешено без участия человека.
АВТО_ОКРУЖЕНИЯ = frozenset({"test", "non-production"})


def _секрет() -> bytes:
    """Ключ подписи одобрения.

    Берётся из окружения, в код и в Git не попадает. Отсутствие ключа — не
    повод подписывать пустой строкой: это повод отказаться подписывать.
    """
    к = os.environ.get("CHANGESET_APPROVAL_KEY", "").strip()
    if not к:
        raise ChangeSetError("APPROVAL_KEY_MISSING",
                             "ключ подписи одобрения не настроен", 503)
    return к.encode("utf-8")


def связка(набор: dict[str, Any]) -> dict[str, Any]:
    """Всё, изменение чего обязано аннулировать одобрение."""
    return {
        "changeset_id": набор["changeset_id"],
        "plan_hash": набор["plan_hash"],
        "target_site_ids": sorted(набор["target_site_ids"]),
        "canary_site_ids": sorted(набор.get("canary_site_ids") or []),
        "resource_type": набор["resource_type"],
        "resource_id": набор["resource_id"],
        "operation_type": набор["operation_type"],
        "base_registry_version": набор["base_registry_version"],
        "expected_resource_fingerprint": набор["expected_resource_fingerprint"],
        "policy_version": набор["policy_version"],
        "risk_class": набор["risk_class"],
        "verification_plan_hash": hashlib.sha256(
            канон(набор.get("verification_plan") or {}).encode()).hexdigest(),
        "rollback_plan_hash": hashlib.sha256(
            канон(набор.get("rollback_plan") or {}).encode()).hexdigest(),
    }


def подпись(набор: dict[str, Any], *, approver: str, expires_at: str) -> str:
    тело = канон({**связка(набор), "approver": approver,
                  "expires_at": expires_at})
    return hmac.new(_секрет(), тело.encode("utf-8"), hashlib.sha256).hexdigest()


def одобрить(набор: dict[str, Any], *, approver_id: str, approver_service: str,
             approver_type: str, expires_at: str,
             reason: str = "") -> dict[str, Any]:
    """Сформировать запись одобрения, проверив разделение ролей."""
    if approver_type == "MODEL":
        raise ChangeSetError("MODEL_ACTION_DENIED",
                             "актор-модель не вправе одобрять", 403)
    if M.APPROVER not in M.роли_службы(approver_service):
        raise ChangeSetError("ROLE_NOT_GRANTED",
                             f"служба {approver_service} не имеет роли approver",
                             403)
    # Предложивший и одобривший — разные лица. Совпадение означало бы, что
    # одобрение не добавляет ничего, кроме видимости процедуры.
    if approver_id == набор["actor_id"]:
        raise ChangeSetError(
            "SEPARATION_OF_DUTIES",
            "предложивший изменение не может сам его одобрить", 403)
    if not набор.get("plan_hash"):
        raise ChangeSetError("PLAN_REQUIRED",
                             "одобрять нечего: план не построен")
    запись = {
        "approver_id": approver_id,
        "approver_service": approver_service,
        "approver_type": approver_type,
        "approved_at": сейчас(),
        "expires_at": expires_at,
        "reason": reason,
        "policy_version": POLICY_VERSION,
        "binding": связка(набор),
        "signature": подпись(набор, approver=approver_id,
                             expires_at=expires_at),
    }
    return запись


def проверить_одобрение(набор: dict[str, Any], *, сейчас_utc: str) -> None:
    """Действительно ли одобрение ДЛЯ ЭТОГО набора в ЭТОМ виде."""
    запись = набор.get("approval")
    if not запись:
        raise ChangeSetError("APPROVAL_REQUIRED", "изменение не одобрено", 403)
    if запись.get("revoked_at"):
        raise ChangeSetError("APPROVAL_REVOKED", "одобрение отозвано", 403)
    if сейчас_utc > запись["expires_at"]:
        raise ChangeSetError("APPROVAL_EXPIRED", "срок одобрения истёк", 403)
    текущая = связка(набор)
    if текущая != запись["binding"]:
        различия = sorted(k for k in текущая
                          if текущая[k] != запись["binding"].get(k))
        raise ChangeSetError(
            "APPROVAL_BINDING_MISMATCH",
            f"после одобрения изменилось: {различия}", 409)
    ожидаемая = подпись(набор, approver=запись["approver_id"],
                        expires_at=запись["expires_at"])
    if not hmac.compare_digest(ожидаемая.encode(),
                               str(запись["signature"]).encode()):
        raise ChangeSetError("APPROVAL_SIGNATURE_INVALID",
                             "подпись одобрения не совпала", 403)


def применение_разрешено(набор: dict[str, Any], окружения: set[str]) -> None:
    """Можно ли вообще применять этот набор в этих окружениях."""
    чужие = окружения - АВТО_ОКРУЖЕНИЯ
    if чужие and not AUTONOMOUS_PRODUCTION_APPLY:
        raise ChangeSetError(
            "AUTONOMOUS_PRODUCTION_APPLY_DISABLED",
            f"применение в окружениях {sorted(чужие)} выключено; "
            f"блокирующие долги: {list(ДОЛГИ_БЛОКИРУЮЩИЕ_АВТОНОМИЮ)}", 403)


def проверить_действие_модели(actor_type: str, действие: str) -> None:
    if actor_type == "MODEL" and действие in M.ЗАПРЕЩЕНО_МОДЕЛИ:
        raise ChangeSetError(
            "MODEL_ACTION_DENIED",
            f"актору-модели действие {действие} закрыто", 403)
