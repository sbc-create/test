"""Адаптеры источников единого модуля оценок."""

from __future__ import annotations

from factory.unified_ratings.adapters.base import (
    Capabilities,
    HealthState,
    SourceFetch,
    UnifiedSourceAdapter,
)

__all__ = [
    "Capabilities",
    "HealthState",
    "SourceFetch",
    "UnifiedSourceAdapter",
    "build_adapter",
]


def build_adapter(source_key: str, **kwargs):
    """Собрать адаптер по ключу источника.

    Фабрика намеренно не умеет собирать адаптер для источника со статусом
    BLOCKED_*: вызывающий код не должен решать, «попробовать всё-таки».
    Исключение — Simkl: его адаптер собирается, но без ключа отказывает до
    сетевого запроса, и это видно в ``health()``.
    """
    if source_key == "anilist":
        from factory.unified_ratings.adapters.anilist import AniListAdapter

        return AniListAdapter(**kwargs)
    if source_key == "kitsu":
        from factory.unified_ratings.adapters.kitsu import KitsuAdapter

        return KitsuAdapter(**kwargs)
    if source_key == "simkl":
        from factory.unified_ratings.adapters.simkl import SimklAdapter

        return SimklAdapter(**kwargs)
    if source_key == "shikimori":
        from factory.unified_ratings.adapters.shikimori import ShikimoriUnifiedAdapter

        return ShikimoriUnifiedAdapter(**kwargs)
    if source_key in ("provider_feed_imdb", "provider_feed_kinopoisk"):
        from factory.unified_ratings.adapters.provider_feed import ProviderFeedAdapter

        return ProviderFeedAdapter(source_key, kwargs.pop("items_by_external_id", {}))
    raise KeyError(f"адаптер не зарегистрирован: {source_key}")
