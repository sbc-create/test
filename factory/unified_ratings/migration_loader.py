"""Загрузка миграции 0007 по пути.

Имя файла начинается с цифр, поэтому обычный импорт невозможен. Модуль
кэшируется: повторная загрузка создала бы второй объект модуля со своим
состоянием, и проверка ``applied()`` могла бы ответить по другому экземпляру.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from factory.paths import PATHS

_CACHE: dict[str, ModuleType] = {}

MIGRATION_FILENAME = "0007_unified_ratings.py"
MIGRATION_0008_FILENAME = "0008_import_not_found.py"

#: Все миграции модуля по порядку. Применяются одной последовательностью,
#: чтобы «схема применена» означало одно и то же везде.
MIGRATION_FILES: tuple[str, ...] = (MIGRATION_FILENAME, MIGRATION_0008_FILENAME)


def _load(filename: str, module_name: str) -> ModuleType:
    cached = _CACHE.get(filename)
    if cached is not None:
        return cached
    path = Path(PATHS.root) / "migrations" / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"не удалось загрузить миграцию {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _CACHE[filename] = module
    return module


def load_migration_0007() -> ModuleType:
    return _load(MIGRATION_FILENAME, "unified_ratings_migration_0007")


def load_migration_0008() -> ModuleType:
    return _load(MIGRATION_0008_FILENAME, "unified_ratings_migration_0008")


def load_all() -> list[ModuleType]:
    return [load_migration_0007(), load_migration_0008()]
