"""Общие фикстуры тестов фабрики.

Тесты работают на реальном репозитории, но пишут только в var/ и во временные
каталоги sites/, которые удаляются после теста.
"""
from __future__ import annotations

import copy
import shutil
import sys
import uuid
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / ".claude" / "hooks"))

from factory.paths import PATHS  # noqa: E402
from factory import validation  # noqa: E402


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return ROOT


@pytest.fixture(scope="session")
def pilot_package() -> dict:
    return validation.load_package("pilot-local")


@pytest.fixture
def temp_site(pilot_package):
    """Создаёт временный сайт на основе пилотного пакета и удаляет его после теста."""
    created: list[Path] = []

    def make(mutate=None, *, site_id: str | None = None, copy_content: bool = True) -> str:
        new_id = site_id or f"tmp-{uuid.uuid4().hex[:8]}"
        target = PATHS.sites / new_id
        source = PATHS.sites / "pilot-local"
        if copy_content:
            shutil.copytree(source, target)
        else:
            target.mkdir(parents=True)
        package = copy.deepcopy(pilot_package)
        package["site_id"] = new_id
        package["job_id"] = f"{new_id}-job"
        if mutate:
            mutate(package)
        (target / "package.yaml").write_text(yaml.safe_dump(package, allow_unicode=True, sort_keys=False), encoding="utf-8")
        created.append(target)
        return new_id

    yield make
    for path in created:
        shutil.rmtree(path, ignore_errors=True)
