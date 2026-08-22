"""Загрузка политик и реестров. Один источник истины — файлы в seo/."""
from __future__ import annotations

import functools
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


def repo_root() -> Path:
    env = os.environ.get("SEO_REPO_ROOT")
    if env:
        return Path(env).resolve()
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "seo" / "PROTECTED_GUARDRAILS.yaml").exists():
            return parent
    return Path.cwd()


def state_dir() -> Path:
    d = Path(os.environ.get("SEO_STATE_DIR", repo_root() / ".seo-state"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_yaml(rel: str) -> dict[str, Any]:
    path = repo_root() / rel
    if not path.exists():
        raise FileNotFoundError(f"Отсутствует обязательный файл политики: {rel}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{rel}: ожидался mapping на верхнем уровне")
    return data


@functools.lru_cache(maxsize=None)
def guardrails() -> dict[str, Any]:
    return _load_yaml("seo/PROTECTED_GUARDRAILS.yaml")


@functools.lru_cache(maxsize=None)
def automation_policy() -> dict[str, Any]:
    return _load_yaml("seo/AUTOMATION_POLICY.yaml")


@functools.lru_cache(maxsize=None)
def experiment_policy() -> dict[str, Any]:
    return _load_yaml("seo/EXPERIMENT_POLICY.yaml")


@functools.lru_cache(maxsize=None)
def rollback_policy() -> dict[str, Any]:
    return _load_yaml("seo/ROLLBACK_POLICY.yaml")


@functools.lru_cache(maxsize=None)
def query_taxonomy() -> dict[str, Any]:
    return _load_yaml("seo/QUERY_TAXONOMY.yaml")


@functools.lru_cache(maxsize=None)
def priority_model() -> dict[str, Any]:
    return _load_yaml("seo/NEW_RELEASE_PRIORITY_MODEL.yaml")


@functools.lru_cache(maxsize=None)
def data_sources() -> dict[str, Any]:
    return _load_yaml("seo/DATA_SOURCE_REGISTRY.yaml")


@dataclass(frozen=True)
class Site:
    site_id: str
    tenant: str
    domain: str
    environment: str
    raw: dict[str, Any]

    @property
    def autonomy_tier(self) -> int:
        return int(self.raw.get("seo_autonomy_tier", 0))

    @property
    def timezone(self) -> str:
        return self.raw.get("analytics_timezone", "UTC")

    @property
    def brand_tokens(self) -> list[str]:
        return [t.lower() for t in self.raw.get("brand_tokens", [])]

    @property
    def experiment_limit(self) -> int:
        return int(self.raw.get("experiment_concurrency_limit", 3))


@functools.lru_cache(maxsize=None)
def portfolio() -> list[Site]:
    data = _load_yaml("seo/PORTFOLIO_REGISTRY.yaml")
    sites = []
    for entry in data.get("sites") or []:
        sites.append(Site(
            site_id=entry["site_id"],
            tenant=entry["tenant"],
            domain=entry["domain"],
            environment=entry["environment"],
            raw=entry,
        ))
    return sites


def portfolio_status() -> str:
    return _load_yaml("seo/PORTFOLIO_REGISTRY.yaml").get("status", "UNKNOWN")


def get_site(site_id: str) -> Site:
    for site in portfolio():
        if site.site_id == site_id:
            return site
    raise KeyError(f"Неизвестный site_id: {site_id}")


def authorization_manifest(site_id: str) -> dict[str, Any] | None:
    path = repo_root() / "inventory" / "authorization" / f"{site_id}.authorization.yaml"
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def reset_caches() -> None:
    """Для тестов: сбросить закэшированные политики."""
    for fn in (guardrails, automation_policy, experiment_policy, rollback_policy,
               query_taxonomy, priority_model, data_sources, portfolio):
        fn.cache_clear()
