"""Адаптер аниме-порталов Yummy: снимок наблюдателя как источник.

Наблюдатель уже обходит каталог и держит состояние в файле. Адаптер читает
именно его — не поставщика и не базу витрины, — потому что снимок и есть
публичный интерфейс наблюдателя.

Живое поведение витрины не затрагивается: адаптер только читает.
"""
from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from factory.site_engine.contracts import (
    EpisodeCounts,
    PlaybackAvailability,
    Provenance,
    Title,
    utc_now,
)
from factory.site_engine.providers import (
    ProviderCapabilities,
    ProviderUnavailable,
    canonical_id,
    normalize_rating,
)

WATCHER_CAPABILITIES = ProviderCapabilities(
    has_episode_list=False,
    has_playback_endpoint=False,
    # У списка тайтлов `updated_at` есть, у карточки — нет. Различие
    # существенное: по нему нельзя судить о выходе серии, но переносить
    # его в модель можно и нужно.
    has_updated_at=True,
    has_working_search=False,
    has_seasons=True,
    max_page_size=100,
)


def _moment(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


@dataclass
class YummyWatcherAdapter:
    """Нормализованный вид снимка наблюдателя.

    Снимок хранит наблюдения, а не сообщения поставщика, поэтому
    `provider_timestamp` остаётся пустым, а `observed_at` берётся из самого
    снимка. Подменять одно другим — та самая ошибка, из-за которой сегодняшняя
    серия оказывалась ниже записей, ничего не выпускавших.
    """

    name: str = "yummy-watcher-snapshot"
    snapshot_path: Path | None = None
    capabilities: ProviderCapabilities = WATCHER_CAPABILITIES

    def _snapshot(self) -> dict[str, Any]:
        if self.snapshot_path is None or not self.snapshot_path.exists():
            raise ProviderUnavailable(f"снимка наблюдателя нет: {self.snapshot_path}")
        return json.loads(self.snapshot_path.read_text(encoding="utf-8"))

    def snapshot_version(self) -> str:
        """Версия для кэша по состоянию файла, а не по часам."""
        if self.snapshot_path is None or not self.snapshot_path.exists():
            return "отсутствует"
        info = self.snapshot_path.stat()
        return f"{info.st_mtime_ns}:{info.st_size}"

    def _title(self, provider_id: str, record: dict[str, Any], fallback) -> Title:
        observed = _moment(record.get("observedAt")) or fallback
        ratings = tuple(
            r
            for r in (
                normalize_rating("kinopoisk", record.get("kinopoiskScore"), observed_at=observed),
                normalize_rating("imdb", record.get("imdbScore"), observed_at=observed),
            )
            if r is not None
        )
        # Поимённого списка сезонов в снимке нет — есть счётчики. Достраивать
        # из них сезоны значит выдумывать структуру, которой источник не
        # сообщал, поэтому `seasons` остаётся пустым, а счётчики переносятся
        # как счётчики.
        counts = EpisodeCounts(
            available=record.get("availableEpisodes"),
            planned=record.get("plannedEpisodes"),
            max_season=record.get("maxSeason"),
            max_episode=record.get("maxEpisode"),
            seasons_count=record.get("seasonsCount"),
        )
        playback = None
        if record.get("videoAvailable") is not None:
            playback = PlaybackAvailability(
                available=bool(record["videoAvailable"]),
                checked_at=observed,
                provenance=Provenance.OBSERVED,
            )
        return Title(
            canonical_id=canonical_id("cdnvideohub", provider_id),
            provider="cdnvideohub",
            provider_id=provider_id,
            name=(record.get("name") or record.get("title") or provider_id).strip(),
            original_name=record.get("originalName") or None,
            year=record.get("year"),
            kind=record.get("typeLabel") or None,
            observed_at=observed,
            # Время поставщика здесь есть: список тайтлов отдаёт `updated_at`,
            # и наблюдатель его сохраняет. Оно заполнено у всех 6774 записей —
            # но двигается лишь у полутора процентов и не двигается при выходе
            # серии у старого сериала. Поэтому оно переносится как есть и не
            # используется как признак свежести.
            provider_timestamp=_moment(record.get("providerUpdatedAt")),
            poster_url=record.get("posterUrl"),
            ratings=ratings,
            episode_counts=counts,
            playback=playback,
        )

    def walk_titles(self, *, limit: int | None = None) -> Iterator[Title]:
        titles = self._snapshot().get("titles") or {}
        fallback = utc_now()
        for index, (provider_id, record) in enumerate(titles.items()):
            if limit is not None and index >= limit:
                return
            if not isinstance(record, dict):
                continue
            yield self._title(provider_id, record, fallback)

    def fetch_title(self, provider_id: str) -> Title:
        record = (self._snapshot().get("titles") or {}).get(provider_id)
        if not isinstance(record, dict):
            raise ProviderUnavailable(f"в снимке нет записи {provider_id}")
        return self._title(provider_id, record, utc_now())

    def total_titles(self) -> int | None:
        try:
            return len(self._snapshot().get("titles") or {})
        except ProviderUnavailable:
            return None
