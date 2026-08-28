"""Происхождение текста: откуда он взят и из каких фактов собран.

Синопсис на странице — это утверждение о реальном произведении. У каждого
такого утверждения должен быть источник, который можно предъявить. Текст без
происхождения нельзя отличить от выдуманного, а выдуманный пересказ сюжета
реального фильма — это ложь, напечатанная на публичном сайте.

Поэтому описание либо приходит от поставщика и хранит его отпечаток, либо не
выдаётся за синопсис вовсе. Из подтверждённых полей можно собрать полезную
фактическую справку — год, страна, жанр, состав, — но она подписывается как
справка, а не как пересказ.
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

SYNOPSIS = "synopsis"
FACT_SHEET = "fact_sheet"
GENERATOR_VERSION = "seo-text-v1"


def content_hash(text: str) -> str:
    return hashlib.sha256((text or "").strip().encode("utf-8")).hexdigest()[:32]


@dataclass(frozen=True)
class TextProvenance:
    """Происхождение одного текстового блока."""

    kind: str
    source: str
    fetched_at: datetime | None
    content_hash: str
    input_facts: tuple[str, ...] = ()
    generator_version: str = GENERATOR_VERSION
    validation_result: str = "unchecked"

    def as_dict(self) -> dict:
        data = asdict(self)
        data["fetched_at"] = self.fetched_at.isoformat() if self.fetched_at else None
        data["input_facts"] = list(self.input_facts)
        return data


def from_provider(text: str, *, source: str, fetched_at=None) -> TextProvenance:
    """Описание, пришедшее от поставщика. Его можно назвать синопсисом."""
    return TextProvenance(
        kind=SYNOPSIS, source=source,
        fetched_at=fetched_at or datetime.now(timezone.utc),
        content_hash=content_hash(text), input_facts=("provider.description",),
        validation_result="ok" if (text or "").strip() else "empty",
    )


def fact_sheet(text: str, *, facts) -> TextProvenance:
    """Справка, собранная из подтверждённых полей.

    Это не пересказ сюжета и не должно им притворяться: перечисляются только
    те поля, которые действительно пришли от источника.
    """
    return TextProvenance(
        kind=FACT_SHEET, source="catalog.fields",
        fetched_at=datetime.now(timezone.utc),
        content_hash=content_hash(text), input_facts=tuple(facts),
        validation_result="ok" if facts else "no_facts",
    )
