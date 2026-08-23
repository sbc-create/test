"""Реестр аналитики: единственное место в git, где живут counter ID.

Хранится только публичное: домен, идентификатор счётчика, набор целей, статус
Вебмастера, состояние индексации. Токен, client secret и персональные данные
сюда попасть не могут — схема `schemas/analytics-registry.schema.json` их не
описывает, а `additionalProperties` в ней запрещены.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import jsonschema

from factory.errors import BlockedInput
from factory.paths import PATHS

REGISTRY_PATH = "config/analytics.json"
SCHEMA_PATH = "schemas/analytics-registry.schema.json"


class RegistryError(RuntimeError):
    pass


def registry_path(root: Path | None = None) -> Path:
    return (root or PATHS.root) / REGISTRY_PATH


def _schema(root: Path | None = None) -> dict:
    return json.loads(((root or PATHS.root) / SCHEMA_PATH).read_text(encoding="utf-8"))


def validate(data: dict, root: Path | None = None) -> None:
    """Реестр обязан валидироваться до записи, а не после жалобы CI."""
    validator = jsonschema.Draft202012Validator(_schema(root))
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    if errors:
        first = errors[0]
        location = "/".join(str(p) for p in first.path) or "(корень)"
        raise BlockedInput(
            f"Реестр аналитики не проходит схему: {location}: {first.message}",
            field=REGISTRY_PATH,
            required_input="Исправить данные реестра; схему под данные не подгонять",
            blocks_stage="VALIDATING",
        )


def load(root: Path | None = None) -> dict:
    path = registry_path(root)
    if not path.exists():
        raise RegistryError(f"реестр аналитики не найден: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    validate(data, root)
    return data


def save(data: dict, root: Path | None = None) -> Path:
    data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    validate(data, root)
    path = registry_path(root)
    # Атомарная запись: падение между write и replace не оставит обрезанный реестр.
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


@dataclass(frozen=True)
class Property:
    """Один домен под аналитикой. Обёртка над записью реестра."""

    raw: dict

    @property
    def domain(self) -> str:
        return self.raw["domain"]

    @property
    def counter_id(self) -> int | None:
        return self.raw.get("counter_id")

    @property
    def allowed_hosts(self) -> list[str]:
        return list(self.raw.get("allowed_hosts") or [])

    @property
    def analytics_enabled(self) -> bool:
        return bool(self.raw.get("analytics_enabled"))

    @property
    def indexing_enabled(self) -> bool:
        return bool(self.raw.get("seo_indexing_enabled"))

    @property
    def webmaster_status(self) -> str:
        return str((self.raw.get("webmaster") or {}).get("verification_status") or "PLANNED")

    @property
    def verification_marker(self) -> str | None:
        return (self.raw.get("webmaster") or {}).get("verification_marker")


def properties(root: Path | None = None) -> list[Property]:
    return [Property(entry) for entry in load(root).get("properties", [])]


def by_domain(domain: str, root: Path | None = None) -> Property | None:
    from factory.analytics.yandex import normalize_domain

    target = normalize_domain(domain)
    for entry in properties(root):
        if normalize_domain(entry.domain) == target:
            return entry
    return None


def upsert(entry: dict, root: Path | None = None) -> dict:
    """Обновляет запись домена, сохраняя всё, что не пришло в обновлении."""
    from factory.analytics.yandex import normalize_domain

    data = load(root)
    target = normalize_domain(entry["domain"])
    for index, existing in enumerate(data["properties"]):
        if normalize_domain(existing["domain"]) == target:
            merged = {**existing, **entry}
            merged["webmaster"] = {**(existing.get("webmaster") or {}), **(entry.get("webmaster") or {})}
            data["properties"][index] = merged
            break
    else:
        data["properties"].append(entry)
    save(data, root)
    return data


def indexing_enabled(root: Path | None = None) -> bool:
    """Глобальный рубильник индексации. По умолчанию и по заданию — выключен."""
    return bool(load(root).get("seo_indexing_enabled"))
