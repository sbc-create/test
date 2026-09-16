"""Адаптер витрин Lords: статический рендер из кэша живого каталога.

Читает то же, что читает работающая сборка, и переводит в нормализованную
модель. Живое поведение не затрагивается: адаптер только читает.
"""
from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from factory.site_engine.contracts import (
    PlaybackAvailability,
    Provenance,
    Title,
    utc_now,
)
from factory.site_engine.providers import (
    ProviderCapabilities,
    ProviderContractBroken,
    ProviderUnavailable,
    title_from_provider,
)


def _moment(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


#: Проверено запросами к публичному API, а не взято из документации.
CDNVIDEOHUB_CAPABILITIES = ProviderCapabilities(
    has_episode_list=False,
    has_playback_endpoint=False,
    # У списка каталога `updated_at` есть, у карточки — нет.
    has_updated_at=True,
    has_working_search=False,
    has_seasons=True,
    max_page_size=24,
)


@dataclass
class LordsCatalogAdapter:
    """Каталог Lords из кэша, собранного работающим обходом.

    Ходить к поставщику здесь не нужно и незачем: обход уже сходил, а его
    результат — файл. Это же делает адаптер пригодным для API-каркаса без
    единого внешнего запроса.
    """

    name: str = "lords-live-cache"
    cache_path: Path | None = None
    capabilities: ProviderCapabilities = CDNVIDEOHUB_CAPABILITIES

    def _records(self) -> list[dict[str, Any]]:
        if self.cache_path is None or not self.cache_path.exists():
            raise ProviderUnavailable(
                f"кэша живого каталога нет: {self.cache_path}. "
                "Витрина при этом остаётся на прежнем релизе — это last-known-good"
            )
        payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            items = payload.get("items")
            if isinstance(items, list):
                return items
            raise ProviderContractBroken(
                f"в кэше {self.cache_path} нет списка items; "
                f"есть {sorted(payload)[:6]}"
            )
        return payload if isinstance(payload, list) else []

    @staticmethod
    def _normalize(raw: dict[str, Any]) -> dict[str, Any]:
        """Приведение записи кэша к общему виду.

        Кэш называет идентификатор `external_id`, а не `id`, и хранит признак
        доступности объектом `playback`. Разница именований — единственное, что
        здесь происходит: значения не толкуются и не достраиваются.
        """
        prepared = dict(raw)
        prepared["id"] = raw.get("external_id") or raw.get("id")
        prepared["kind"] = "series" if raw.get("is_series") else "movie"
        return prepared

    def walk_titles(self, *, limit: int | None = None) -> Iterator[Title]:
        stamp = utc_now()
        for index, raw in enumerate(self._records()):
            if limit is not None and index >= limit:
                return
            prepared = self._normalize(raw)
            title = title_from_provider(provider="cdnvideohub", raw=prepared, observed_at=stamp)
            playback = raw.get("playback")
            if playback is not None:
                title = replace(
                    title,
                    playback=PlaybackAvailability(
                        available=bool(playback),
                        checked_at=stamp,
                        provenance=Provenance.PROVIDER,
                    ),
                )
            # Время поставщика здесь есть: список каталога отдаёт `updated_at`.
            # В карточке его нет — именно поэтому дельта серий считается по
            # счётчикам, а не по этому полю.
            stamped = _moment(raw.get("updated_at"))
            if stamped is not None:
                title = replace(title, provider_timestamp=stamped)
            yield title

    def fetch_title(self, provider_id: str) -> Title:
        for title in self.walk_titles():
            if title.provider_id == provider_id:
                return title
        raise ProviderUnavailable(f"в кэше нет записи {provider_id}")

    def total_titles(self) -> int | None:
        try:
            return len(self._records())
        except ProviderUnavailable:
            return None
