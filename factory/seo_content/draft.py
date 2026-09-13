"""Версионированный черновик SEO-контента и его жизненный цикл.

Разделение ролей здесь жёсткое: модель приносит текст, всё остальное
назначает сервер. Владелец записи, окружение, идентификаторы, состояние
публикации и переходы состояния не принимаются из ответа модели даже если
она их прислала — принятое поле молча стало бы правом.

Ключ идемпотентности считается из шести величин:

    site_id + entity_type + entity_id + fact_pack_sha256 + prompt_version + locale

Отпечаток пакета входит в ключ намеренно. Повтор того же события даёт тот же
ключ и не порождает второй текст; изменение фактов даёт другой ключ и
обязано породить новую ревизию — старый текст не должен пережить данные, из
которых он собран.
"""
from __future__ import annotations

import dataclasses
import hashlib
from enum import Enum
from typing import Any, Mapping, Sequence

from .factpack import canonical_json, sha256_of

SCHEMA_VERSION = "seo.content.draft/1.0.0"
RESOURCE_KIND = "seo.content.draft"


class GateStatus(str, Enum):
    """Исход ворот качества. Промежуточных значений нет намеренно."""

    PASSED = "PASSED"
    REJECTED = "REJECTED"
    #: Фактов не хватает на честный текст. Это исправный исход, а не отказ.
    NEEDS_FACTS = "NEEDS_FACTS"
    #: Источники расходятся. Выбор удобного варианта делает не модель.
    FACT_CONFLICT = "FACT_CONFLICT"
    #: Текст возможен, но требует человека до применения.
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    #: Поля не должно быть вовсе.
    OMIT = "OMIT"
    #: Собственной ценности у страницы нет; честнее не индексировать.
    NOINDEX_RECOMMENDED = "NOINDEX_RECOMMENDED"


#: Исходы, при которых текст не может быть предложен к применению.
НЕПРОХОДНЫЕ = frozenset({GateStatus.REJECTED, GateStatus.NEEDS_FACTS,
                         GateStatus.FACT_CONFLICT, GateStatus.OMIT,
                         GateStatus.NOINDEX_RECOMMENDED,
                         GateStatus.REVIEW_REQUIRED})


class ClaimVerdict(str, Enum):
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    UNSUPPORTED = "UNSUPPORTED"
    NON_FACTUAL_STYLE = "NON_FACTUAL_STYLE"


@dataclasses.dataclass(frozen=True, slots=True)
class Claim:
    """Проверяемое утверждение, извлечённое из готового текста."""

    claim_id: str
    text: str
    field: str          # какое поле черновика его содержит
    claim_type: str     # year | title | work_type | country | genre | ...
    verdict: ClaimVerdict
    fact_id: str | None = None
    detail: str = ""
    material: bool = True  # существенное ли утверждение

    def to_dict(self) -> dict[str, Any]:
        д = dataclasses.asdict(self)
        д["verdict"] = self.verdict.value
        return д


@dataclasses.dataclass(frozen=True, slots=True)
class FaqItem:
    question: str
    answer: str
    fact_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"question": self.question, "answer": self.answer,
                "fact_refs": list(self.fact_refs)}


def idempotency_key(*, site_id: str, entity_type: str, entity_id: str,
                    fact_pack_sha256: str, prompt_version: str,
                    locale: str) -> str:
    """Ключ повторяемости.

    Порядок и разделитель фиксированы: ключ обязан совпасть у независимых
    вызывающих, иначе одинаковый запрос дважды создаст две записи.
    """
    основа = "\x1f".join((site_id, entity_type, entity_id, fact_pack_sha256,
                          prompt_version, locale))
    return "seo-draft-" + hashlib.sha256(основа.encode("utf-8")).hexdigest()


#: Поля, которые назначает сервер. Присланные значения не принимаются.
НАЗНАЧАЕТ_СЕРВЕР = frozenset({
    "draft_id", "revision", "owner_service", "target_environment",
    "publication_state", "lifecycle_state", "created_at", "idempotency_key",
    "quality_gate_status", "rejection_reasons", "server_assigned",
})


class ModelOverreach(ValueError):
    """Модель прислала поле, которое ей назначать не положено."""


@dataclasses.dataclass(frozen=True, slots=True)
class SEOContentDraft:
    """Черновик. Неизменяем; правка — это новая ревизия."""

    # --- личность --------------------------------------------------------
    site_id: str
    entity_type: str
    entity_id: str
    locale: str
    fact_pack_version: int
    fact_pack_sha256: str

    # --- происхождение текста --------------------------------------------
    model_version: str
    prompt_version: str
    generation_parameters: Mapping[str, Any]

    # --- содержимое ------------------------------------------------------
    meta_title: str | None
    meta_description: str | None
    h1_recommendation: str | None
    body_description: str | None
    editorial_notes: tuple[Any, ...] = ()
    faq_items: tuple[FaqItem, ...] = ()
    claim_map: tuple[Claim, ...] = ()
    warnings: tuple[str, ...] = ()
    quality_scores: Mapping[str, Any] = dataclasses.field(default_factory=dict)
    quality_gate_status: GateStatus = GateStatus.REVIEW_REQUIRED
    rejection_reasons: tuple[str, ...] = ()

    # --- назначает сервер -------------------------------------------------
    idempotency_key: str = ""
    created_at: str = ""
    revision: int = 1
    owner_service: str = "seo"
    target_environment: str = "test"
    publication_state: str = "DRAFT"
    lifecycle_state: str = "OPEN"
    schema_version: str = SCHEMA_VERSION
    resource_kind: str = RESOURCE_KIND

    #: Рекомендации по технической разметке — согласованный набор, а не
    #: разрозненные подсказки: H1, canonical, хлебные крошки и JSON-LD
    #: обязаны говорить об одной сущности.
    technical_recommendations: Mapping[str, Any] = dataclasses.field(
        default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.quality_gate_status is GateStatus.PASSED

    def payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "resource_kind": self.resource_kind,
            "site_id": self.site_id, "entity_type": self.entity_type,
            "entity_id": self.entity_id, "locale": self.locale,
            "fact_pack_version": self.fact_pack_version,
            "fact_pack_sha256": self.fact_pack_sha256,
            "model_version": self.model_version,
            "prompt_version": self.prompt_version,
            "generation_parameters": dict(self.generation_parameters),
            "meta_title": self.meta_title,
            "meta_description": self.meta_description,
            "h1_recommendation": self.h1_recommendation,
            "body_description": self.body_description,
            "editorial_notes": [н.to_dict() if hasattr(н, "to_dict") else н
                                for н in self.editorial_notes],
            "faq_items": [f.to_dict() for f in self.faq_items],
            "claim_map": [c.to_dict() for c in self.claim_map],
            "warnings": list(self.warnings),
            "quality_scores": dict(self.quality_scores),
            "quality_gate_status": self.quality_gate_status.value,
            "rejection_reasons": list(self.rejection_reasons),
            "idempotency_key": self.idempotency_key,
            "created_at": self.created_at,
            "revision": self.revision,
            "owner_service": self.owner_service,
            "target_environment": self.target_environment,
            "publication_state": self.publication_state,
            "lifecycle_state": self.lifecycle_state,
            "technical_recommendations": dict(self.technical_recommendations),
        }

    @property
    def content_sha256(self) -> str:
        """Отпечаток только содержимого.

        Служебные поля исключены: две записи с одним текстом и разным
        временем создания — это один текст, и считать их разными значило бы
        ломать проверку дублей.
        """
        тело = {k: v for k, v in self.payload().items()
                if k not in ("created_at", "revision", "publication_state",
                             "lifecycle_state", "idempotency_key")}
        return sha256_of(тело)

    @property
    def sha256(self) -> str:
        return sha256_of(self.payload())

    def texts(self) -> dict[str, str]:
        """Все тексты черновика — то, что увидит человек."""
        итог = {k: v for k, v in (
            ("meta_title", self.meta_title),
            ("meta_description", self.meta_description),
            ("h1_recommendation", self.h1_recommendation),
            ("body_description", self.body_description),
        ) if v}
        for i, н in enumerate(self.editorial_notes):
            текст = н.text if hasattr(н, "text") else str(н)
            итог[f"editorial_note[{i}]"] = текст
        for i, f in enumerate(self.faq_items):
            итог[f"faq[{i}].answer"] = f.answer
        return итог


def reject_model_overreach(ответ: Mapping[str, Any]) -> None:
    """Отклонить ответ модели, назначающий себе служебные поля.

    Не «отфильтровать молча»: попытка назначить владельца или состояние
    публикации — это не шум, а превышение роли, и она должна быть видна.
    """
    лишние = sorted(set(ответ) & НАЗНАЧАЕТ_СЕРВЕР)
    if лишние:
        raise ModelOverreach(
            "модель прислала поля, которые назначает сервер: "
            + ", ".join(лишние))
