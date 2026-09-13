"""Контур качества SEO-контента.

Путь новой или изменённой сущности до черновика: событие → неизменяемый
`SEOFactPack` → Writer → детерминированные проверки → Blind Judge → ворота →
`SEOContentDraft`. Ни одно звено не имеет права выдумать факт, и ни одно не
публикует: черновик доходит до предложения и останавливается там.
"""
from __future__ import annotations

__all__ = ["factpack", "draft", "identity", "claims", "dedup", "language",
           "structured_data", "judge", "gate", "writer", "pipeline", "budget",
           "injection", "editorial", "store"]
