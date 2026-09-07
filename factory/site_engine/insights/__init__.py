"""Домен insights: наблюдения о происходящем: аналитика, SEO, журнал действий.

Интерфейс ленивый: пакет с немедленным реэкспортом втягивает свои модули в
момент импорта самого пакета, и связь, безобидная между плоскими модулями,
превращается в кольцо. Ленивое разрешение откладывает импорт до первого
обращения, когда инициализация уже закончена.
"""
from __future__ import annotations

import importlib
from typing import Any

_МОДУЛИ = (
    "seo_binding",
    "freshness",
    "fingerprint",
)


def __getattr__(имя: str) -> Any:
    if имя in _МОДУЛИ:
        return importlib.import_module(f"{__name__}.{имя}")
    raise AttributeError(
        f"домен insights не отдаёт «{имя}»: возьмите его у нужного модуля")


def __dir__() -> list[str]:
    return sorted(_МОДУЛИ)
