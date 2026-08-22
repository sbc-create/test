"""
Проверки защищённого ядра. Вызываются ПЕРЕД любой mutation.

Ни один самосозданный модуль не может ослабить эти проверки: они живут
в protected path и покрыты mutation-тестами.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import config


class GuardrailViolation(Exception):
    """Поднимается вместо выполнения действия. Не перехватывать широко."""

    def __init__(self, rule_id: str, message: str) -> None:
        super().__init__(f"BLOCKED_PROTECTED_GUARDRAIL [{rule_id}]: {message}")
        self.rule_id = rule_id


class AuthorizationBlocked(Exception):
    """BLOCKED_AUTHORIZATION — не ошибка, а состояние. Цикл продолжает другие джобы."""

    def __init__(self, message: str, request: dict[str, Any] | None = None) -> None:
        super().__init__(f"BLOCKED_AUTHORIZATION: {message}")
        self.request = request or {}


@dataclass(frozen=True)
class MutationRequest:
    site_id: str
    action: str
    tier: int
    experiment_id: str | None
    before_snapshot: dict[str, Any] | None
    rollback_payload: dict[str, Any] | None
    payload: dict[str, Any]
    is_defect_fix: bool = False


def _action_tier(action: str) -> int:
    tiers = config.automation_policy()["tiers"]
    for level, spec in sorted(tiers.items()):
        if action in (spec.get("actions") or []):
            return int(level)
    raise GuardrailViolation("GR-004", f"Действие '{action}' не описано ни в одном tier — fail-closed.")


def check_rights(payload: dict[str, Any]) -> None:
    """GR-001: публикация только при подтверждённом праве."""
    if payload.get("publishes_content"):
        if not payload.get("rights_ref"):
            raise GuardrailViolation("GR-001", "Публикация без rights_ref запрещена.")
        if payload.get("source_confidence") not in ("high", "confirmed"):
            raise GuardrailViolation(
                "GR-001", f"source_confidence={payload.get('source_confidence')} недостаточен для публикации.")


def check_no_fake_engagement(payload: dict[str, Any]) -> None:
    """GR-002: никакой имитации пользовательской активности."""
    forbidden = {
        "comment_create_as_user": "создание комментария от имени пользователя",
        "rating_write": "запись оценки",
        "vote_write": "голос",
        "review_create": "создание отзыва",
    }
    action = payload.get("action", "")
    if action in forbidden:
        raise GuardrailViolation("GR-002", f"Запрещено: {forbidden[action]}.")

    if payload.get("author_type") == "user" and payload.get("generated_by") == "operator":
        raise GuardrailViolation("GR-002", "Автоматический контент не публикуется от имени пользователя.")

    if payload.get("schema_type") == "Review" and not payload.get("is_genuine_review"):
        raise GuardrailViolation("GR-002", "Review schema только для настоящих обзоров.")

    if payload.get("ratings") and payload.get("ratings_source") != "real_published":
        raise GuardrailViolation("GR-002", "В интерфейсе и structured data только реальные опубликованные оценки.")


def check_editorial_reply(site_manifest: dict[str, Any] | None, payload: dict[str, Any]) -> None:
    """Автоответ допустим только при disclosed_editorial_reply_enabled и раскрытом авторе."""
    if payload.get("action") != "editorial_reply":
        return
    if not (site_manifest or {}).get("disclosed_editorial_reply_enabled"):
        raise AuthorizationBlocked(
            "Публичные редакционные ответы выключены в site manifest.",
            {"needs": "disclosed_editorial_reply_enabled", "site": payload.get("site_id")},
        )
    allowed_authors = {"Редакция сайта", "AI-ассистент редакции"}
    if payload.get("author_label") not in allowed_authors:
        raise GuardrailViolation(
            "GR-002", f"Автор ответа должен быть раскрыт: {sorted(allowed_authors)}.")
    if payload.get("claims_personal_viewing_experience"):
        raise GuardrailViolation("GR-002", "Ответ не имитирует личный опыт просмотра.")


def check_rollback_available(req: MutationRequest) -> None:
    """GR-006: нет rollback => нет mutation."""
    if req.tier == 0:
        return
    if not req.before_snapshot:
        raise GuardrailViolation("GR-006", f"Нет before-snapshot для '{req.action}'.")
    if not req.rollback_payload:
        raise GuardrailViolation("GR-006", f"Нет rollback payload для '{req.action}'.")
    if not req.rollback_payload.get("executable"):
        raise GuardrailViolation("GR-006", "Rollback payload не помечен как исполняемый.")


def check_tenant_isolation(site_id: str, payload: dict[str, Any]) -> None:
    """GR-005."""
    targets = payload.get("target_sites") or [site_id]
    if any(t != site_id for t in targets):
        raise GuardrailViolation("GR-005", f"Cross-tenant запись: {targets} при site={site_id}.")
    canonical = payload.get("canonical_url")
    if canonical:
        site = config.get_site(site_id)
        if site.domain not in canonical and "demo.invalid" not in canonical:
            raise GuardrailViolation("GR-005", f"Canonical указывает вне tenant: {canonical}")


def check_search_spam(payload: dict[str, Any]) -> None:
    """GR-009."""
    if payload.get("generated_page_count", 0) > 50 and not payload.get("distinct_value_verified"):
        raise GuardrailViolation("GR-009", "Массовая генерация страниц без подтверждённой отдельной ценности.")
    if payload.get("technique") in {"keyword_stuffing", "hidden_text", "doorway", "synonym_spinning"}:
        raise GuardrailViolation("GR-009", f"Запрещённая техника: {payload['technique']}.")
    text = payload.get("text") or ""
    if text and _keyword_density_exceeded(text):
        raise GuardrailViolation("GR-009", "Плотность ключевых слов выходит за допустимые пределы.")


def _keyword_density_exceeded(text: str, threshold: float = 0.08) -> bool:
    words = [w.lower().strip(".,!?:;()«»\"'") for w in text.split()]
    words = [w for w in words if len(w) > 3]
    if len(words) < 40:
        return False
    top = max((words.count(w) for w in set(words)), default=0)
    return top / len(words) > threshold


def check_authorization(site_id: str, action: str, tier: int) -> dict[str, Any]:
    """GR-004: manifest — единственный источник production-авторизации."""
    manifest = config.authorization_manifest(site_id)
    if manifest is None:
        raise AuthorizationBlocked(
            f"Нет authorization manifest для site={site_id}.",
            {"site": site_id, "action": action, "needs": "inventory/authorization/<site>.authorization.yaml"},
        )
    if action not in (manifest.get("allowed_actions") or []):
        raise AuthorizationBlocked(
            f"Действие '{action}' не в allowed_actions для {site_id}.",
            {"site": site_id, "action": action, "needs": "allowed_actions += " + action},
        )
    from datetime import date
    expires = manifest.get("authorization_expires_at")
    if not expires:
        raise AuthorizationBlocked(f"Нет authorization_expires_at для {site_id}.", {"site": site_id})
    if date.fromisoformat(str(expires)) < date.today():
        raise AuthorizationBlocked(f"Авторизация {site_id} истекла {expires}.", {"site": site_id})

    if manifest.get("environment") == "production" and not manifest.get("production_authorized"):
        raise AuthorizationBlocked(f"production_authorized != true для {site_id}.", {"site": site_id})

    site_tier = int(manifest.get("seo_autonomy_tier", 0))
    if tier > site_tier:
        raise AuthorizationBlocked(
            f"Действие tier={tier} выше autonomy_tier={site_tier} для {site_id}.",
            {"site": site_id, "action": action, "needs": f"seo_autonomy_tier >= {tier}"},
        )
    if tier >= 3:
        raise AuthorizationBlocked(
            f"Tier 3 всегда требует отдельной явной авторизации владельца: {action}.",
            {"site": site_id, "action": action, "tier": 3},
        )
    return manifest


def authorize_mutation(req: MutationRequest) -> dict[str, Any]:
    """
    Единый вход для любой mutation. Два слоя: guardrails + manifest.
    Возвращает manifest при успехе, иначе поднимает исключение.
    """
    tier = _action_tier(req.action) if req.tier is None else req.tier
    payload = dict(req.payload, action=req.action, site_id=req.site_id)

    check_no_fake_engagement(payload)
    check_rights(payload)
    check_search_spam(payload)
    check_tenant_isolation(req.site_id, payload)
    check_rollback_available(MutationRequest(**{**req.__dict__, "tier": tier}))

    if not req.experiment_id and not req.is_defect_fix and tier >= 1:
        raise GuardrailViolation(
            "GR-007", "Любое изменение принадлежит эксперименту, если не является исправлением доказанного дефекта.")

    manifest = check_authorization(req.site_id, req.action, tier)
    check_editorial_reply(manifest, payload)
    return manifest


# --------------------------------------------------------------------------
# Целостность protected ядра
# --------------------------------------------------------------------------

def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protected_fingerprint() -> dict[str, str]:
    root = config.repo_root()
    out: dict[str, str] = {}
    for rel in config.guardrails().get("protected_paths", []):
        p = root / rel
        if p.is_file():
            out[rel] = _hash_file(p)
        elif p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file() and "__pycache__" not in f.parts:
                    out[str(f.relative_to(root))] = _hash_file(f)
    return out


def verify_integrity(baseline: dict[str, str]) -> list[str]:
    """Возвращает список изменённых/пропавших protected файлов."""
    current = protected_fingerprint()
    drift = [rel for rel, h in baseline.items() if current.get(rel) != h]
    drift += [rel for rel in current if rel not in baseline]
    return sorted(set(drift))
