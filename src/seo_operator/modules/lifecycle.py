"""
Жизненный цикл самостоятельно созданных модулей.

Модуль может решать повторяющуюся задачу без запроса владельцу, но не может
расширить собственные права. Этот файл — то место, где второе проверяется.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date
from enum import Enum
from typing import Any

from ..guardrails import AuthorizationBlocked, GuardrailViolation


class Stage(str, Enum):
    NEED_DETECTED = "NEED_DETECTED"
    SPEC_CREATED = "SPEC_CREATED"
    THREAT_AND_DATA_REVIEW = "THREAT_AND_DATA_REVIEW"
    IMPLEMENTED_IN_ISOLATED_BRANCH = "IMPLEMENTED_IN_ISOLATED_BRANCH"
    UNIT_TESTED = "UNIT_TESTED"
    INTEGRATION_TESTED = "INTEGRATION_TESTED"
    STAGING = "STAGING"
    CANARY = "CANARY"
    OBSERVED = "OBSERVED"
    PROMOTED = "PROMOTED"
    REVERTED = "REVERTED"
    DOCUMENTED = "DOCUMENTED"


ORDER = [
    Stage.NEED_DETECTED, Stage.SPEC_CREATED, Stage.THREAT_AND_DATA_REVIEW,
    Stage.IMPLEMENTED_IN_ISOLATED_BRANCH, Stage.UNIT_TESTED, Stage.INTEGRATION_TESTED,
    Stage.STAGING, Stage.CANARY, Stage.OBSERVED, Stage.PROMOTED, Stage.DOCUMENTED,
]

# Чего самосозданный модуль не может — независимо от того, что написано в его манифесте.
FORBIDDEN_CAPABILITIES = {
    "widen_own_credentials": "расширение собственных credentials",
    "read_other_secret_namespace": "чтение чужих secret namespace",
    "change_dns_or_ssh_scope": "изменение DNS/SSH scope",
    "disable_tests_hooks_sandbox": "отключение tests/hooks/sandbox",
    "modify_protected_guardrails": "изменение PROTECTED_GUARDRAILS.yaml",
    "enable_fake_engagement": "разрешение фиктивных комментариев/оценок",
    "weaken_rights_rules": "ослабление правил прав на контент",
    "deploy_to_all_sites_immediately": "мгновенная установка на все сайты",
    "destructive_migration": "разрушительная миграция без авторизации",
    "install_unverified_code": "установка непроверенного кода из интернета",
    "claim_success_without_evidence": "объявление успеха без доказательств",
    "modify_own_permission_rules": "изменение собственных permission rules",
    "modify_unattended_profile": "правка unattended-профиля",
    "modify_own_guard_hook": "правка hook, контролирующего сам модуль",
}


@dataclass
class ModuleManifest:
    name: str
    purpose: str
    owner: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    data_sensitivity: str                  # none | operational | pii | rights
    permissions: list[str]
    allowed_sites: list[str]
    mutation_scope: list[str]
    dependencies: dict[str, str]           # name -> pinned version
    timeouts_s: int
    retries: int
    quotas: dict[str, int]
    tests: list[str]
    rollout: dict[str, Any]
    rollback: dict[str, Any]
    metrics: list[str]
    version: str
    security_review_status: str = "pending"
    requested_capabilities: list[str] = field(default_factory=list)


@dataclass
class ModuleRecord:
    manifest: ModuleManifest
    stage: Stage = Stage.NEED_DETECTED
    history: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)


def validate_manifest(m: ModuleManifest) -> list[str]:
    problems = []
    for cap in m.requested_capabilities:
        if cap in FORBIDDEN_CAPABILITIES:
            problems.append(f"BLOCKED_PROTECTED_GUARDRAIL: запрошено «{FORBIDDEN_CAPABILITIES[cap]}».")
    if not m.dependencies:
        pass
    for name, version in m.dependencies.items():
        if version in ("*", "latest", ""):
            problems.append(f"Зависимость '{name}' не закреплена (получено '{version}').")
    if not m.tests:
        problems.append("Модуль без тестов не проходит дальше SPEC_CREATED.")
    if not m.rollback:
        problems.append("Нет плана отката.")
    if len(m.allowed_sites) > 1 and m.rollout.get("initial_share", 1.0) >= 1.0:
        problems.append("Мгновенная раскатка более чем на один сайт запрещена.")
    if m.data_sensitivity in ("pii", "rights") and m.security_review_status != "approved":
        problems.append(f"Чувствительность '{m.data_sensitivity}' требует пройденного security review.")
    return problems


def advance(record: ModuleRecord, to: Stage, evidence: dict[str, Any]) -> ModuleRecord:
    """Переход только на один шаг вперёд и только с доказательствами предыдущего этапа."""
    if to is Stage.REVERTED:
        record.stage = to
        record.history.append(f"{date.today().isoformat()}: REVERTED — {evidence.get('reason', 'без причины')}")
        return record

    if to not in ORDER:
        raise ValueError(f"Неизвестный этап: {to}")
    current_idx = ORDER.index(record.stage) if record.stage in ORDER else -1
    if ORDER.index(to) != current_idx + 1:
        raise GuardrailViolation(
            "GR-012", f"Нельзя перепрыгнуть этап: {record.stage.value} -> {to.value}.")

    required = {
        Stage.SPEC_CREATED: "spec_path",
        Stage.THREAT_AND_DATA_REVIEW: "threat_review",
        Stage.IMPLEMENTED_IN_ISOLATED_BRANCH: "branch",
        Stage.UNIT_TESTED: "unit_test_result",
        Stage.INTEGRATION_TESTED: "integration_test_result",
        Stage.STAGING: "staging_result",
        Stage.CANARY: "canary_scope",
        Stage.OBSERVED: "observation_result",
        Stage.PROMOTED: "promotion_evidence",
        Stage.DOCUMENTED: "doc_path",
    }.get(to)

    if required and not evidence.get(required):
        raise GuardrailViolation("GR-012", f"Переход в {to.value} требует доказательства '{required}'.")

    if to is Stage.PROMOTED:
        if not evidence.get("promotion_evidence", {}).get("metrics_improved"):
            raise GuardrailViolation("GR-012", "Продвижение без доказанного улучшения метрик запрещено.")

    record.stage = to
    record.evidence[to.value] = evidence
    record.history.append(f"{date.today().isoformat()}: -> {to.value}")
    return record


def needs_owner_approval(m: ModuleManifest) -> tuple[bool, list[str]]:
    """Одна конкретная заявка вместо остановки всего цикла."""
    reasons = []
    if any(p.startswith("schema_migration") for p in m.permissions):
        reasons.append("требуется schema migration")
    if any(p.startswith("elevated") for p in m.permissions):
        reasons.append("требуются расширенные права")
    if m.dependencies and any(d.startswith("external:") for d in m.dependencies):
        reasons.append("требуется новый внешний сервис")
    if m.rollout.get("irreversible"):
        reasons.append("необратимое действие")
    return bool(reasons), reasons
