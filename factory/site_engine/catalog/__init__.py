"""Домен содержимого: записи, их тождество, рейтинги и воспроизводимость.

Самый крупный домен: пятнадцать модулей и восемьдесят четыре обращения из
остального кода. Здесь живёт то, что отвечает на вопросы «какая это запись»,
«тот же это тайтл или другой», «есть ли у него оценка» и «играет ли он».

Сюда входит `identity_resolver` — вопреки слову «identity» в имени он про
тождество произведений, а не людей. В домен личности его отнесла моя первая
раскладка по именам, и гейт границ это показал.

Интерфейс ленивый: пакет с немедленным реэкспортом втягивает пятнадцать
модулей при импорте самого пакета, и любая связь между ними и остальным
движком превращается в кольцо. Ленивое разрешение откладывает импорт до
первого обращения, когда инициализация закончена.
"""
from __future__ import annotations

import importlib
from typing import Any

_МОДУЛИ = (
    "catalog_identity",
    "content_identity",
    "content_kind",
    "store",
    "ingestion",
    "providers",
    "rating_feed",
    "rating_enrichment",
    "rating_sources",
    "rating_discovery",
    "playback_policy",
    "title_normalize",
    "kind_overlay",
    "identity_resolver",
    "catalog_snapshot",
)


def __getattr__(имя: str) -> Any:
    if имя in _МОДУЛИ:
        return importlib.import_module(f"{__name__}.{имя}")
    raise AttributeError(
        f"домен содержимого не отдаёт «{имя}»: возьмите его у нужного модуля")


def __dir__() -> list[str]:
    return sorted(_МОДУЛИ)
