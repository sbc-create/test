"""Общий контракт целей развёртывания.

Инварианты, которые обязан соблюдать любой адаптер:
1. `plan()` не меняет ничего.
2. Мутация начинается только после backup.
3. Релиз атомарен: симлинк `current` переключается только после health check.
4. Предыдущий рабочий релиз сохраняется, откат возможен без пересборки.
5. Повторный деплой того же build_id — no-op с `idempotent_noop: true`.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass
class Step:
    id: str
    detail: str = ""
    mutation: bool = False
    status: str = "ok"
    exit_code: int | None = 0
    started_at: str = ""
    finished_at: str = ""


@dataclass
class DeployPlan:
    site_id: str
    environment: str
    build_id: str
    target_ref: str
    steps: list[dict] = field(default_factory=list)

    @property
    def mutations(self) -> int:
        return sum(1 for s in self.steps if s.get("mutation"))

    def as_dict(self) -> dict:
        return {
            "site_id": self.site_id,
            "environment": self.environment,
            "build_id": self.build_id,
            "target_ref": self.target_ref,
            "steps": self.steps,
            "mutations": self.mutations,
        }


@dataclass
class DeployResult:
    site_id: str
    environment: str
    build_id: str
    release_id: str
    previous_release_id: str | None
    base_url: str
    steps: list[dict] = field(default_factory=list)
    mutations: list[dict] = field(default_factory=list)
    backup: dict | None = None
    idempotent_noop: bool = False

    def as_dict(self) -> dict:
        return {
            "site_id": self.site_id,
            "environment": self.environment,
            "build_id": self.build_id,
            "release_id": self.release_id,
            "previous_release_id": self.previous_release_id,
            "base_url": self.base_url,
            "steps": self.steps,
            "mutations": self.mutations,
            "backup": self.backup,
            "idempotent_noop": self.idempotent_noop,
        }


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class Target(Protocol):
    adapter: str

    def plan(self, build_dir: Path, build_id: str) -> DeployPlan: ...
    def backup(self) -> dict: ...
    def deploy(self, build_dir: Path, build_id: str, *, dry_run: bool = False) -> DeployResult: ...
    def health(self) -> tuple[bool, str]: ...
    def rollback(self) -> DeployResult: ...
    def base_url(self) -> str: ...
    def releases(self) -> list[str]: ...
