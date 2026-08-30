"""Сборка профиля нового сайта из составляющих.

Новый сайт не должен начинаться с копирования чужого профиля целиком: копия
приносит с собой чужие домены, чужие счётчики и чужие допущения, а замечают это
через месяц. Здесь профиль собирается из названного набора решений, и всё, что
не названо, берётся из умолчаний, одинаковых для всех.

Функция ничего не пишет на диск: она возвращает профиль. Записывает его тот, кто
решил его завести.
"""
from __future__ import annotations

from typing import Any

from factory.site_engine.contracts import ContractError

SCHEMA_VERSION = "1.0"

#: Слои кэша, одинаковые у всех сайтов. Различия задаются точечно, а не
#: переписыванием политики целиком: переписанная политика молча теряет слой.
DEFAULT_CACHE_LAYERS: dict[str, dict[str, Any]] = {
    "homepage_shelves": {"ttl_seconds": 300, "stale_while_revalidate_seconds": 300,
                         "last_known_good": True, "tags": ["shelf"]},
    "catalog": {"ttl_seconds": 900, "stale_while_revalidate_seconds": 600,
                "last_known_good": True, "tags": ["catalog"]},
    "title_page": {"ttl_seconds": 900, "stale_while_revalidate_seconds": 600,
                   "last_known_good": True, "tags": ["title"]},
    "seo": {"ttl_seconds": 3600, "stale_while_revalidate_seconds": 1800,
            "last_known_good": True, "tags": ["seo"]},
    "static_assets": {"ttl_seconds": 86400, "last_known_good": True, "tags": ["static"]},
}

DEFAULT_EVENT_MAP: dict[str, list[str]] = {
    "TITLE_CREATED": ["shelf:new-titles", "catalog"],
    "TITLE_UPDATED": ["title", "catalog"],
}

#: Модули, без которых сайта не бывает.
BASE_MODULES = ("site-configuration", "cache-invalidation", "monitoring-audit",
                "renderer-adapters")


def scaffold_profile(
    *,
    site_id: str,
    site_type: str,
    domain: str,
    theme: str,
    modules: tuple[str, ...],
    contact_email: str,
    owners: dict[str, str],
    render_mode: str = "static",
    locale: str = "ru-RU",
    timezone: str = "Europe/Moscow",
    directions: tuple[str, ...] = (),
    providers: tuple[dict[str, Any], ...] = (),
    normalized_content_source: dict[str, str] | None = None,
    cache_layers: dict[str, dict[str, Any]] | None = None,
    event_map: dict[str, list[str]] | None = None,
    keep_releases: int = 2,
    release_size_budget_mb: int = 200,
    full_render_budget_minutes: int = 15,
    feature_flags: dict[str, Any] | None = None,
    seo_enabled: bool = True,
    indexing_enabled: bool = False,
) -> dict[str, Any]:
    """Профиль нового сайта.

    Проверяется здесь только то, что нельзя проверить схемой: согласованность
    решений между собой. Остальное — дело гейта, и дублировать его тут значит
    завести второе мнение о правилах.
    """
    if not site_id or not domain:
        raise ContractError("у сайта обязаны быть идентификатор и домен")

    enabled = tuple(sorted(set(modules) | set(BASE_MODULES)))

    ходит_к_поставщику = "content-ingestion" in enabled or bool(providers)
    if ходит_к_поставщику and "provider-adapters" not in enabled:
        enabled = tuple(sorted(set(enabled) | {"provider-adapters"}))
    if not ходит_к_поставщику and normalized_content_source is None:
        raise ContractError(
            f"{site_id}: ни своих поставщиков, ни источника нормализованного "
            "контента — показывать будет нечего"
        )
    if not ходит_к_поставщику and "provider-adapters" in enabled:
        raise ContractError(
            f"{site_id}: объявлен provider-adapters, но сайт к поставщику не ходит"
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "site_id": site_id,
        "site_type": site_type,
        "domains": [domain],
        "locale": locale,
        "timezone": timezone,
        "theme": {"name": theme},
        "content_providers": [dict(p) for p in providers],
        "content_directions": list(directions),
        "enabled_modules": list(enabled),
        **({"normalized_content_source": dict(normalized_content_source)}
           if normalized_content_source else {}),
        "render_strategy": {
            "mode": render_mode,
            "release_size_budget_mb": release_size_budget_mb,
            "full_render_budget_minutes": full_render_budget_minutes,
        },
        "cache_policy": {
            "schema_version": SCHEMA_VERSION,
            "layers": dict(cache_layers or DEFAULT_CACHE_LAYERS),
            "invalidation": {
                "mode": "event-driven",
                "event_map": dict(event_map or DEFAULT_EVENT_MAP),
                "dry_run_supported": True,
            },
            "keys": {"site_scoped": True, "stampede_protection": "coalesce"},
            # Три запрета одинаковы у всех и не настраиваются: каждый куплен
            # инцидентом, и сайт, которому они мешают, устроен неправильно.
            "forbidden": {
                "cache_errors": False,
                "empty_response_as_success": False,
                "indefinite_html_cache": False,
            },
            "observability": {"expose_hit_miss_stale": True},
        },
        "seo_profile": {
            "enabled": seo_enabled,
            # Индексация остаётся решением владельца и по умолчанию выключена.
            "indexing_enabled": indexing_enabled,
            "canonical_host": domain,
            "editorial_profile": f"{site_id}-editorial",
        },
        "analytics_profile": {
            "enabled": False,
            "provider": "none",
            # Сбор не разрешён, пока владелец не разрешил его явно.
            "collection_authorized": False,
        },
        "legal_profile": {"contact_email": contact_email, "owner": None, "documents": None},
        "release_policy": {
            "keep_releases": keep_releases,
            "rollback_ready": True,
            "zero_downtime_switch": True,
        },
        "feature_flags": dict(feature_flags or {"ad_slots_enabled": False}),
        "owners": dict(owners),
        "health_endpoint": "/healthz",
        "coverage_endpoint": "/api/v1/coverage",
    }
