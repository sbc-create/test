"""Общие фикстуры тестов фабрики.

Тесты работают на реальном репозитории, но пишут только в var/ и во временные
каталоги sites/, которые удаляются после теста.
"""
from __future__ import annotations

import copy
import os
import shutil
import signal
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
        site = path.name
        # Стенд обязан быть остановлен: иначе процессы php копятся и занимают
        # весь разрешённый диапазон портов до конца сессии.
        try:
            from factory import inventory as _inventory
            from factory.targets import build_target as _build_target
            package = yaml.safe_load((path / "package.yaml").read_text(encoding="utf-8"))
            target = _build_target(_inventory.target(package["target_ref"]), package)
            if hasattr(target, "stop"):
                target.stop()
        except Exception:  # noqa: BLE001 — уборка не должна ронять тест
            pass
        shutil.rmtree(path, ignore_errors=True)
        # временный сайт не оставляет за собой ни сборок, ни артефактов, ни состояния
        shutil.rmtree(PATHS.builds / site, ignore_errors=True)
        shutil.rmtree(PATHS.artifacts / "build" / site, ignore_errors=True)
        shutil.rmtree(PATHS.artifacts / "jobs" / site, ignore_errors=True)
        shutil.rmtree(PATHS.artifacts / "qa" / site, ignore_errors=True)
        shutil.rmtree(PATHS.artifacts / "seo" / site, ignore_errors=True)
        for state in PATHS.state.glob(f"{site}-*.json"):
            state.unlink(missing_ok=True)


@pytest.fixture(scope="session", autouse=True)
def stop_all_stands():
    """Останавливает все локальные стенды после сессии тестов.

    Без этого процессы php накапливаются между прогонами и занимают весь
    разрешённый диапазон портов — деплой начинает падать с BLOCKED_ACCESS.
    """
    yield
    targets_root = PATHS.var / "targets"
    if not targets_root.exists():
        return
    for pid_file in targets_root.rglob("server.pid"):
        try:
            pid = int(pid_file.read_text(encoding="utf-8").strip())
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except (ValueError, ProcessLookupError, PermissionError, OSError):
            pass
        finally:
            pid_file.unlink(missing_ok=True)
