"""Общие фикстуры тестов фабрики.

Тесты работают на реальном репозитории, но пишут только в var/ и во временные
каталоги sites/, которые удаляются после теста.
"""
from __future__ import annotations

import builtins
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

from factory import validation  # noqa: E402
from factory.paths import PATHS  # noqa: E402


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


# --- Аудитор: тесты не пишут в боевые каталоги ---------------------------------
#
# Запрет на запись значений секретов живёт в самой рабочей функции
# (`factory/secret_hub/consumers._write_atomically`) — обойти его нельзя.
# Здесь — более широкий вопрос: не пишет ли набор в боевые каталоги ЧЕМ-ЛИБО
# ещё. Отказ 2026-08-31 показал, что «тест пишет в /srv» — не гипотеза.
#
# По умолчанию аудитор **отклоняет** такие записи. Переменная
# `SECRET_WRITE_AUDIT=log` переводит его в наблюдение: попытки пишутся в файл из
# `SECRET_WRITE_LOG` и пропускаются. Наблюдение нужно ровно один раз — чтобы
# снять полный список нарушителей, не останавливаясь на первом.
БОЕВЫЕ_КОРНИ = ("/srv", "/etc", "/var/lib", "/var/cache", "/run")

#: Исключения — каталоги, которые боевыми не являются, хотя лежат под теми же
#: корнями. Список намеренно короткий: каждая строка здесь ослабляет защиту.
БОЕВЫЕ_ИСКЛЮЧЕНИЯ = ("/var/lib/pytest", "/run/user")


def _боевой_путь(path) -> bool:
    try:
        цель = os.path.realpath(str(path))
    except (OSError, ValueError):
        return True  # не смогли выяснить — считаем боевым
    if any(цель == к or цель.startswith(к + os.sep) for к in БОЕВЫЕ_ИСКЛЮЧЕНИЯ):
        return False
    return any(цель == к or цель.startswith(к + os.sep) for к in БОЕВЫЕ_КОРНИ)


@pytest.fixture(autouse=True)
def _не_писать_в_боевые_каталоги(monkeypatch):
    режим = os.environ.get("SECRET_WRITE_AUDIT", "block")
    журнал = os.environ.get("SECRET_WRITE_LOG")
    настоящий_open = builtins.open

    def нарушение(путь, как):
        кто = os.environ.get("PYTEST_CURRENT_TEST", "сбор")
        if журнал:
            with настоящий_open(журнал, "a", encoding="utf-8") as fh:
                fh.write(f"{кто}\t{как}\t{путь}\n")
        if режим != "log":
            raise AssertionError(
                f"тест пытается писать в боевой путь {путь} ({как}). "
                "Прогон не имеет права менять состояние машины: подмените путь "
                "на tmp_path. Если запись действительно нужна для проверки "
                "боевого состояния — она не относится к unit-набору."
            )

    def охрана_open(file, mode="r", *args, **kwargs):
        if any(f in str(mode) for f in ("w", "a", "x", "+")) and _боевой_путь(file):
            нарушение(file, f"open({mode})")
        return настоящий_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", охрана_open)

    for имя in ("write_text", "write_bytes"):
        оригинал = getattr(Path, имя)

        def сделать(оригинал=оригинал, имя=имя):
            def обёртка(self, *a, **kw):
                if _боевой_путь(self):
                    нарушение(self, f"Path.{имя}")
                return оригинал(self, *a, **kw)
            return обёртка

        monkeypatch.setattr(Path, имя, сделать())
    yield
