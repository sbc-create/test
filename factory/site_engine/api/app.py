"""Маршруты Site Engine API v1.

Реализация намеренно не привязана к веб-фреймворку: `SiteEngineApi.handle`
принимает путь и параметры и возвращает статус с телом. Это позволяет покрыть
контракт тестами без поднятия сервера и оставляет выбор фреймворка на потом —
ровно то, чего требует модульный монолит.
"""
from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from factory.site_engine.contracts import Title
from factory.site_engine.profiles import ProfileNotFound, SiteProfile, load_profile
from factory.site_engine.store import MAX_LIMIT, InMemoryStore

API_VERSION = "v1"

#: Флаг включения. Отсутствует — API выключен, и это правильное умолчание.
FEATURE_FLAG = "SITE_ENGINE_API_ENABLED"

#: Окружения, в которых API вообще может быть включён. Production в списке нет
#: намеренно: маршрут, которого нет в production, невозможно там открыть.
ALLOWED_ENVIRONMENTS = ("local", "test", "staging")


class ApiDisabled(Exception):
    pass


@dataclass(frozen=True)
class ApiResponse:
    status: int
    body: dict[str, Any]

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300


def error(status: int, code: str, message: str, **extra: Any) -> ApiResponse:
    """Ошибки одинаковой формы. Разнобой в ошибках дороже, чем кажется."""
    return ApiResponse(status=status, body={"error": {"code": code, "message": message, **extra}})


def api_enabled(env: dict[str, str] | None = None) -> bool:
    env = env if env is not None else dict(os.environ)
    if env.get(FEATURE_FLAG, "").strip().lower() not in ("1", "true", "yes", "on"):
        return False
    return env.get("SITE_ENGINE_ENVIRONMENT", "local") in ALLOWED_ENVIRONMENTS


@dataclass
class SiteBinding:
    """Связка «профиль сайта — его источник нормализованного контента»."""

    profile: SiteProfile
    store: InMemoryStore
    adapter_name: str


class SiteEngineApi:
    def __init__(self, bindings: dict[str, SiteBinding], *, env: dict[str, str] | None = None):
        self._bindings = bindings
        self._env = env

    # ------------------------------------------------------------- маршруты
    def handle(self, path: str, params: dict[str, Any] | None = None) -> ApiResponse:
        if not api_enabled(self._env):
            # Выключенный API отвечает 404, а не 403: наличие маршрута — тоже
            # сведения, и сообщать их незачем.
            return error(404, "not_found", "маршрут не найден")
        params = params or {}
        parts = [p for p in path.strip("/").split("/") if p]
        if parts[:2] != ["api", API_VERSION]:
            return error(404, "not_found", "маршрут не найден")
        rest = parts[2:]

        if rest == ["health"]:
            return self._health()
        if rest == ["sites"]:
            return self._sites()
        if rest == ["ingestion", "status"]:
            return self._ingestion_status()
        if rest and rest[0] == "sites" and len(rest) >= 2:
            site_id = rest[1]
            binding = self._bindings.get(site_id)
            if binding is None:
                return error(404, "site_not_found", f"сайта {site_id} нет")
            tail = rest[2:]
            if not tail:
                return self._site(binding)
            if tail == ["config"]:
                return self._config(binding)
            if tail == ["coverage"]:
                return self._coverage(binding)
            if tail == ["shelves"]:
                return self._shelves(binding, params)
            if tail == ["titles"]:
                return self._titles(binding, params)
            if len(tail) >= 2 and tail[0] == "titles":
                title_id = tail[1]
                if len(tail) == 2:
                    return self._title(binding, title_id)
                if tail[2:] == ["episodes"]:
                    return self._episodes(binding, title_id)
                if tail[2:] == ["ratings"]:
                    return self._ratings(binding, title_id)
        return error(404, "not_found", "маршрут не найден")

    # ------------------------------------------------------------ реализация
    def _health(self) -> ApiResponse:
        return ApiResponse(
            200,
            {
                "status": "ok",
                "version": API_VERSION,
                "sites": len(self._bindings),
                # Секретов здесь нет и быть не может: отдаются только имена.
                "adapters": sorted({b.adapter_name for b in self._bindings.values()}),
            },
        )

    def _sites(self) -> ApiResponse:
        return ApiResponse(
            200,
            {
                "items": [
                    {
                        "site_id": b.profile.site_id,
                        "site_type": b.profile.site_type,
                        "domains": list(b.profile.domains),
                        "render_mode": b.profile.render_mode,
                    }
                    for b in sorted(self._bindings.values(), key=lambda x: x.profile.site_id)
                ],
                "total": len(self._bindings),
            },
        )

    def _site(self, binding: SiteBinding) -> ApiResponse:
        p = binding.profile
        return ApiResponse(
            200,
            {
                "site_id": p.site_id,
                "site_type": p.site_type,
                "domains": list(p.domains),
                "locale": p.locale,
                "timezone": p.timezone,
                "theme": p.theme,
                "render_mode": p.render_mode,
                "modules": sorted(p.enabled_modules),
                "normalized_content": p.normalized_content_kind(),
                "titles_known": binding.store.count(),
            },
        )

    def _config(self, binding: SiteBinding) -> ApiResponse:
        p = binding.profile
        return ApiResponse(
            200,
            {
                "site_id": p.site_id,
                "cache_policy": p.cache_policy,
                "seo": {
                    "enabled": p.seo_enabled,
                    "indexing_enabled": p.indexing_enabled,
                    "canonical_host": p.canonical_host,
                },
                "release_policy": {"keep_releases": p.keep_releases},
                "feature_flags": p.feature_flags,
                "health_endpoint": p.health_endpoint,
                "coverage_endpoint": p.coverage_endpoint,
                # Поставщики отдаются без credentials_ref: ссылка на секрет —
                # тоже сведения, которые наружу не нужны.
                "providers": [
                    {"adapter": pr.get("adapter"), "role": pr.get("role"),
                     "directions": pr.get("directions", [])}
                    for pr in p.content_providers
                ],
            },
        )

    def _coverage(self, binding: SiteBinding) -> ApiResponse:
        report = binding.store.coverage()
        return ApiResponse(
            200,
            {
                "site_id": report.site_id,
                "source_total": report.source_total,
                "local_total": report.local_total,
                "missing": report.missing,
                "ratio": report.ratio,
                # `null` — это «источник не сказал сколько», а не «полно».
                "complete": report.complete,
                "observed_at": report.observed_at.isoformat(),
            },
        )

    def _titles(self, binding: SiteBinding, params: dict[str, Any]) -> ApiResponse:
        try:
            offset = int(params.get("offset", 0))
            limit = int(params.get("limit", 24))
        except (TypeError, ValueError):
            return error(400, "bad_request", "offset и limit должны быть целыми")
        if offset < 0 or limit < 1:
            return error(400, "bad_request", "offset не может быть отрицательным, limit — меньше единицы")
        if limit > MAX_LIMIT:
            return error(
                400, "limit_too_large",
                f"limit больше предела {MAX_LIMIT}; молча отдать меньше было бы хуже",
                max_limit=MAX_LIMIT,
            )
        page = binding.store.query(offset=offset, limit=limit,
                                   genre=params.get("genre"), kind=params.get("kind"))
        return ApiResponse(
            200,
            {
                "items": [self._title_brief(t) for t in page.items],
                "total": page.total,
                "offset": page.offset,
                "limit": page.limit,
                "has_more": page.has_more,
            },
        )

    def _find(self, binding: SiteBinding, title_id: str) -> Title | None:
        from factory.site_engine.contracts import ContractError

        try:
            return binding.store.get(title_id)
        except ContractError:
            return None

    def _title(self, binding: SiteBinding, title_id: str) -> ApiResponse:
        title = self._find(binding, title_id)
        if title is None:
            return error(404, "title_not_found", f"тайтла {title_id} нет")
        return ApiResponse(200, self._title_full(title))

    def _episodes(self, binding: SiteBinding, title_id: str) -> ApiResponse:
        title = self._find(binding, title_id)
        if title is None:
            return error(404, "title_not_found", f"тайтла {title_id} нет")
        counts = title.episode_counts
        return ApiResponse(
            200,
            {
                "canonical_id": title.canonical_id,
                # Поимённого списка серий у источника нет ни на одном маршруте.
                # Ответ говорит это прямо, вместо того чтобы отдать пустой
                # список, который читается как «серий нет».
                "episode_list_available": False,
                "seasons": [
                    {
                        "number": s.number,
                        "name": s.name,
                        "episodes_count": s.episodes_count,
                        "available_episodes_count": s.available_episodes_count,
                    }
                    for s in title.seasons
                ],
                "counts": None
                if counts is None
                else {
                    "available": counts.available,
                    "planned": counts.planned,
                    "max_season": counts.max_season,
                    "max_episode": counts.max_episode,
                    "seasons_count": counts.seasons_count,
                },
                "available_episodes": title.available_episodes,
            },
        )

    def _ratings(self, binding: SiteBinding, title_id: str) -> ApiResponse:
        title = self._find(binding, title_id)
        if title is None:
            return error(404, "title_not_found", f"тайтла {title_id} нет")
        best = title.best_rating()
        return ApiResponse(
            200,
            {
                "canonical_id": title.canonical_id,
                "items": [
                    {"source": r.source, "value": r.value,
                     "provenance": r.provenance.value,
                     "observed_at": r.observed_at.isoformat() if r.observed_at else None}
                    for r in title.ratings
                ],
                "best": None if best is None else {"source": best.source, "value": best.value},
            },
        )

    def _shelves(self, binding: SiteBinding, params: dict[str, Any]) -> ApiResponse:
        """Полки строятся из нормализованного хранилища, а не из поставщика."""
        limit = min(int(params.get("limit", 12) or 12), MAX_LIMIT)
        everything = binding.store.query(offset=0, limit=MAX_LIMIT)
        watchable = [t for t in everything.items if t.playback and t.playback.available]
        rated = sorted(
            (t for t in everything.items if t.best_rating() is not None),
            key=lambda t: t.best_rating().value,
            reverse=True,
        )
        with_episodes = [t for t in everything.items if (t.available_episodes or 0) > 0]
        shelves = [
            {"id": "watchable", "title": "Можно смотреть",
             "items": [self._title_brief(t) for t in watchable[:limit]]},
            {"id": "top-rated", "title": "С высокой оценкой",
             "items": [self._title_brief(t) for t in rated[:limit]]},
            {"id": "with-episodes", "title": "С доступными сериями",
             "items": [self._title_brief(t) for t in with_episodes[:limit]]},
        ]
        return ApiResponse(200, {"site_id": binding.profile.site_id,
                                 "shelves": [s for s in shelves if s["items"]]})

    def _ingestion_status(self) -> ApiResponse:
        return ApiResponse(
            200,
            {
                "sites": [
                    {
                        "site_id": b.profile.site_id,
                        "adapter": b.adapter_name,
                        "titles_known": b.store.count(),
                        "coverage_ratio": b.store.coverage().ratio,
                    }
                    for b in sorted(self._bindings.values(), key=lambda x: x.profile.site_id)
                ]
            },
        )

    @staticmethod
    def _title_brief(title: Title) -> dict[str, Any]:
        best = title.best_rating()
        return {
            "canonical_id": title.canonical_id,
            "name": title.name,
            "year": title.year,
            "kind": title.kind,
            "rating": None if best is None else {"source": best.source, "value": best.value},
            "available_episodes": title.available_episodes,
            "watchable": bool(title.playback and title.playback.available),
        }

    @classmethod
    def _title_full(cls, title: Title) -> dict[str, Any]:
        body = cls._title_brief(title)
        body.update(
            {
                "provider": title.provider,
                "provider_id": title.provider_id,
                "original_name": title.original_name,
                "genres": list(title.genres),
                "countries": list(title.countries),
                "external_ids": title.external_ids.as_dict(),
                "poster_url": title.poster_url,
                "observed_at": title.observed_at.isoformat(),
                "provider_timestamp": title.provider_timestamp.isoformat()
                if title.provider_timestamp
                else None,
                "schema_version": title.schema_version,
            }
        )
        return body


def create_api(
    site_ids: list[str],
    *,
    root: Path | str = ".",
    loader: Callable[[SiteProfile], tuple[InMemoryStore, str]] | None = None,
    env: dict[str, str] | None = None,
) -> SiteEngineApi:
    """Сборка API из профилей.

    Загрузчик передаётся снаружи: API не знает, откуда берётся содержимое, и
    именно поэтому один и тот же каркас обслуживает витрину, портал и новый
    тип сайта.
    """
    bindings: dict[str, SiteBinding] = {}
    for site_id in site_ids:
        try:
            profile = load_profile(site_id, root)
        except ProfileNotFound:
            continue
        if loader is None:
            store, adapter_name = InMemoryStore(site_id), "none"
        else:
            store, adapter_name = loader(profile)
        bindings[site_id] = SiteBinding(profile=profile, store=store, adapter_name=adapter_name)
    return SiteEngineApi(bindings, env=env)
