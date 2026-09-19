"""Централизованный ratings ingestion для всех шаблонов Site Factory.

Цепочка
-------

``external sources → adapters → title identity resolver → append-only
observations → current projection → immutable ratings snapshot →
rating_gateway → templates``

Шаблоны (Lords, Animedia, Zona и будущие) читают только готовый snapshot по
``canonical_title_id``. Они не ходят во внешние API и не парсят рейтинги.

Историческое размещение прототипов в ``factory/lords/`` не означает
принадлежность рейтингов только Lords — этот пакет общий.
"""

from __future__ import annotations

SCHEMA_SNAPSHOT = "ratings_snapshot_v1"
ADAPTER_VERSION_SHIKIMORI = "shikimori-graphql/1.0.0"
ADAPTER_VERSION_ANIMEMEDIA = "animemedia-unverified/0.0.0"

__all__ = [
    "ADAPTER_VERSION_ANIMEMEDIA",
    "ADAPTER_VERSION_SHIKIMORI",
    "SCHEMA_SNAPSHOT",
]
