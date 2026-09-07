"""Домен job_runtime: очередь, замки, состояние заданий и запросы недостающего.

Интерфейс ленивый: пакет с немедленным реэкспортом втягивает свои модули в
момент импорта самого пакета, и связь, безобидная между плоскими модулями,
превращается в кольцо.
"""
from __future__ import annotations

import importlib
from typing import Any

_МОДУЛИ = (
    "queue",
    "locks",
    "state",
    "input_request",
)


def __getattr__(имя: str) -> Any:
    if имя in _МОДУЛИ:
        return importlib.import_module(f"{__name__}.{имя}")
    raise AttributeError(
        f"домен job_runtime не отдаёт «{имя}»: возьмите его у нужного модуля")


def __dir__() -> list[str]:
    return sorted(_МОДУЛИ)
