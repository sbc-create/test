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


def load_migration_0007() -> ModuleType:
    cached = _CACHE.get(MIGRATION_FILENAME)
    if cached is not None:
        return cached
    path = Path(PATHS.root) / "migrations" / MIGRATION_FILENAME
    spec = importlib.util.spec_from_file_location("unified_ratings_migration_0007", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"не удалось загрузить миграцию {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _CACHE[MIGRATION_FILENAME] = module
    return module
