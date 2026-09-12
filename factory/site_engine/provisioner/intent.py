"""OnboardingIntent — намерение, а не источник истины.

Намерение описывает, ЧЕГО просили: домен, шаблон, язык, цели. Оно неизменяемо
и не заменяет собой реестр: состав сайтов, их окружение и жизненный цикл
по-прежнему живут в Site Registry, а состояние onboarding вычисляется из
событий, а не хранится параллельно.

Ключ связи — `site_id`. Домен и его псевдонимы меняются, и связывать по ним
значит однажды потерять сайт, который просто переехал.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

СХЕМА = "onboarding-intent/1.0.0"

#: Домен разбирается как данные, а не исполняется. Разрешены только метки из
#: букв, цифр и дефисов — всё остальное отвергается до любой обработки.
ДОМЕН = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))+$")
МАКС_ПСЕВДОНИМОВ = 16


class IntentError(ValueError):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.error_code, self.detail = code, detail


def _домен(значение: str, поле: str) -> str:
    з = (значение or "").strip().lower().rstrip(".")
    if not з or len(з) > 253 or not ДОМЕН.match(з):
        raise IntentError("DOMAIN_INVALID", f"{поле}: {значение!r} не является доменом")
    return з


@dataclass(frozen=True)
class OnboardingIntent:
    requested_by: str
    canonical_domain: str
    template_family: str
    template_profile: str
    language: str
    region: str
    correlation_id: str
    idempotency_key: str
    aliases: tuple[str, ...] = ()
    dns_provider_ref: str | None = None
    dns_zone_ref: str | None = None
    seo_topic: str | None = None
    seo_goals: tuple[str, ...] = ()
    reference_profile: str | None = None
    monitoring_profile: str | None = None
    site_id: str | None = None          # известен при adoption существующего

    @classmethod
    def разобрать(cls, сырое: dict[str, Any]) -> "OnboardingIntent":
        обязательные = ("requested_by", "canonical_domain", "template_family",
                        "template_profile", "language", "region",
                        "correlation_id", "idempotency_key")
        пустые = [п for п in обязательные if not str(сырое.get(п) or "").strip()]
        if пустые:
            # Пустое поле — не разрешение подставить умолчание.
            raise IntentError("INTENT_INCOMPLETE",
                              f"не заданы поля: {пустые}")
        домен = _домен(сырое["canonical_domain"], "canonical_domain")
        псевдонимы = tuple(dict.fromkeys(
            _домен(a, "aliases") for a in (сырое.get("aliases") or [])))
        if len(псевдонимы) > МАКС_ПСЕВДОНИМОВ:
            raise IntentError("ALIASES_TOO_MANY",
                              f"псевдонимов больше {МАКС_ПСЕВДОНИМОВ}")
        if домен in псевдонимы:
            raise IntentError("ALIAS_DUPLICATES_CANONICAL",
                              "канонический домен указан и как псевдоним")
        return cls(
            requested_by=str(сырое["requested_by"]).strip(),
            canonical_domain=домен,
            aliases=псевдонимы,
            template_family=str(сырое["template_family"]).strip(),
            template_profile=str(сырое["template_profile"]).strip(),
            language=str(сырое["language"]).strip(),
            region=str(сырое["region"]).strip(),
            correlation_id=str(сырое["correlation_id"]).strip(),
            idempotency_key=str(сырое["idempotency_key"]).strip(),
            dns_provider_ref=(сырое.get("dns_provider_ref") or None),
            dns_zone_ref=(сырое.get("dns_zone_ref") or None),
            seo_topic=(сырое.get("seo_topic") or None),
            seo_goals=tuple(сырое.get("seo_goals") or ()),
            reference_profile=(сырое.get("reference_profile") or None),
            monitoring_profile=(сырое.get("monitoring_profile") or None),
            site_id=(сырое.get("site_id") or None),
        )

    @property
    def отпечаток(self) -> str:
        """Содержательный отпечаток намерения. Основание идемпотентности."""
        тело = json.dumps(asdict(self), ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"))
        return hashlib.sha256(тело.encode("utf-8")).hexdigest()

    def в_словарь(self) -> dict[str, Any]:
        return {"schema_version": СХЕМА, **asdict(self),
                "intent_fingerprint": self.отпечаток}
