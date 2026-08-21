"""Единая точка правды о расположении каталогов фабрики."""
from __future__ import annotations

import os
from pathlib import Path

ENV_ROOT = "FACTORY_ROOT"


def repo_root() -> Path:
    override = os.environ.get(ENV_ROOT)
    if override:
        return Path(override).resolve()
    here = Path(__file__).resolve().parent.parent
    return here


class Paths:
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or repo_root()).resolve()

    # статические каталоги репозитория
    @property
    def knowledge(self) -> Path: return self.root / "knowledge"
    @property
    def schemas(self) -> Path: return self.root / "schemas"
    @property
    def inventory(self) -> Path: return self.root / "inventory"
    @property
    def blueprints(self) -> Path: return self.root / "blueprints"
    @property
    def themes(self) -> Path: return self.root / "themes"
    @property
    def plugins(self) -> Path: return self.root / "plugins"
    @property
    def sites(self) -> Path: return self.root / "sites"
    @property
    def queue(self) -> Path: return self.root / "queue"
    @property
    def automation(self) -> Path: return self.root / "automation"
    @property
    def docs(self) -> Path: return self.root / "docs"

    # изменяемое состояние
    @property
    def var(self) -> Path: return self.root / "var"
    @property
    def state(self) -> Path: return self.var / "state"
    @property
    def locks(self) -> Path: return self.var / "locks"
    @property
    def builds(self) -> Path: return self.var / "build"
    @property
    def targets(self) -> Path: return self.var / "targets"
    @property
    def backups(self) -> Path: return self.var / "backups"
    @property
    def audit(self) -> Path: return self.var / "audit"
    @property
    def artifacts(self) -> Path: return self.root / "artifacts"

    def site_dir(self, site_id: str) -> Path: return self.sites / site_id
    def site_package(self, site_id: str) -> Path: return self.sites / site_id / "package.yaml"
    def build_dir(self, site_id: str, build_id: str) -> Path: return self.builds / site_id / build_id
    def artifact_dir(self, *parts: str) -> Path:
        p = self.artifacts.joinpath(*parts)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def ensure_runtime(self) -> None:
        for d in (self.state, self.locks, self.builds, self.targets, self.backups, self.audit, self.artifacts):
            d.mkdir(parents=True, exist_ok=True)


PATHS = Paths()
