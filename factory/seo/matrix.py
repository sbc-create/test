"""Доступ к матрице индексируемости."""
from __future__ import annotations

import functools

import yaml

from factory.paths import PATHS


@functools.lru_cache(maxsize=1)
def _raw(mtime: float) -> dict:  # noqa: ARG001
    path = PATHS.knowledge / "SEO_INDEXABILITY_MATRIX.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load() -> dict:
    path = PATHS.knowledge / "SEO_INDEXABILITY_MATRIX.yaml"
    return _raw(path.stat().st_mtime)


def page_type(page_type_id: str) -> dict | None:
    return {p["id"]: p for p in load().get("page_types", [])}.get(page_type_id)


def hard_rules() -> list[dict]:
    return load().get("hard_rules", [])


def url_policy() -> dict:
    return load().get("url_policy", {})
