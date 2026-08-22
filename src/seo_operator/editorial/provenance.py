"""
Provenance и фактическая дисциплина редакции.

Правило, которое здесь закодировано: неподтверждённый факт не угадывается,
а опускается. «Дата не объявлена» — валидное состояние публикации,
выдуманная дата — нарушение GR-001/GR-009.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

CONFIDENCE_ORDER = {"unknown": 0, "low": 1, "medium": 2, "high": 3, "confirmed": 4}

PUBLISHABLE_MIN_CONFIDENCE = "high"

# Формулировки, которыми запрещено подменять отсутствующий факт.
SPECULATION_PATTERNS = [
    r"\bвероятно\s+вы[йи]дет\b",
    r"\bожидается\s+в\s+\d{4}\b",
    r"\bпо\s+слухам\b",
    r"\bпредположительно\b",
    r"\bскорее\s+всего\b",
    r"\bинсайдеры\s+сообщают\b",
]


@dataclass
class FactClaim:
    field: str
    value: Any
    source: str | None
    source_url: str | None = None
    confidence: str = "unknown"
    observed_at: str | None = None

    @property
    def publishable(self) -> bool:
        return (
            self.source is not None
            and CONFIDENCE_ORDER.get(self.confidence, 0) >= CONFIDENCE_ORDER[PUBLISHABLE_MIN_CONFIDENCE]
        )


@dataclass
class ProvenanceReport:
    ok: bool
    publishable_fields: list[str] = field(default_factory=list)
    omitted_fields: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)


def validate_claims(claims: list[FactClaim]) -> ProvenanceReport:
    report = ProvenanceReport(ok=True)
    for claim in claims:
        if claim.publishable:
            report.publishable_fields.append(claim.field)
        else:
            report.omitted_fields.append(claim.field)
            if claim.value not in (None, "", []) and claim.source is None:
                report.violations.append(
                    f"Поле '{claim.field}' имеет значение без источника — публикация запрещена.")
                report.ok = False
    return report


def check_text_for_speculation(text: str) -> list[str]:
    found = []
    lowered = text.lower()
    for pattern in SPECULATION_PATTERNS:
        if re.search(pattern, lowered):
            found.append(pattern)
    return found


def release_date_statement(claim: FactClaim) -> str:
    """
    Единственный разрешённый способ отрендерить дату выхода.
    Нет подтверждения — честная формулировка, не догадка.
    """
    if not claim.publishable or not claim.value:
        return "дата не объявлена"
    try:
        d = date.fromisoformat(str(claim.value))
    except ValueError:
        return "дата не объявлена"
    return d.isoformat()


def required_disclosure(item: dict[str, Any]) -> list[str]:
    """Что обязано быть раскрыто рядом с материалом."""
    out = []
    if item.get("is_promotion") or item.get("is_affiliate"):
        out.append("Реклама/партнёрское размещение — обязательная пометка, не редакционный выбор.")
    if item.get("generated_by") == "operator":
        out.append("Материал подготовлен редакцией с использованием AI-ассистента.")
    if item.get("ai_reply"):
        out.append("Ответ опубликован от лица «AI-ассистент редакции».")
    return out
