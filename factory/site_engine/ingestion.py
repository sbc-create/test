"""Обход поставщика и наполнение нормализованного хранилища.

Единственный модуль, которому разрешено писать в хранилище, и единственный,
которому разрешено обращаться к адаптеру поставщика. Оба ограничения проверяет
гейт границ.

Обрыв обхода здесь — ошибка, а не тихая остановка. Каталог Lords месяцами
обрывался на 4800 записях, отвечая HTTP 200: прогон завершался «успешно»,
витрина выглядела рабочей, и заметить это можно было только по датам.
"""
from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass

from factory.site_engine.contracts import (
    ContentEvent,
    ContractError,
    CoverageReport,
    EventType,
    IngestionRun,
    Title,
    utc_now,
)
from factory.site_engine.providers import ProviderAdapter, ProviderUnavailable
from factory.site_engine.store import InMemoryStore, WriteToken


class CatalogTruncation(ContractError):
    """Источник обещает продолжение, а обход упёрся в предел."""


@dataclass(frozen=True)
class IngestionLimits:
    """Пределы обхода. Названы явно, чтобы упор в них был виден, а не молчалив."""

    max_pages: int = 2000
    page_size: int = 24
    max_titles: int | None = None


def _run_id(site_id: str) -> str:
    return hashlib.sha256(f"{site_id}|{utc_now().isoformat()}".encode()).hexdigest()[:16]


def idempotency_key(event_type: EventType, canonical_id: str, marker: str) -> str:
    """Один и тот же факт обязан дать один и тот же ключ.

    Маркер — это то, что отличает событие: номер серии, значение оценки. Время
    в ключ не входит намеренно: иначе повторный цикл с тем же изменением
    положил бы его в ленту второй раз.
    """
    return hashlib.sha256(
        f"{event_type.value}|{canonical_id}|{marker}".encode()
    ).hexdigest()[:32]


def diff_titles(previous: Title | None, current: Title) -> list[ContentEvent]:
    """Что изменилось между двумя наблюдениями одного тайтла.

    Сравниваются счётчики сезонов, а не списки серий: списка серий у источника
    нет. Событие о выходе серии выпускается только при росте числа доступных
    серий — не при появлении записи и не «чтобы карточка появилась».
    """
    events: list[ContentEvent] = []
    stamp = current.observed_at

    def make(kind: EventType, marker: str, payload: dict) -> ContentEvent:
        return ContentEvent(
            event_id=idempotency_key(kind, current.canonical_id, marker)[:16],
            event_type=kind,
            provider=current.provider,
            provider_id=current.provider_id,
            canonical_title_id=current.canonical_id,
            observed_at=stamp,
            idempotency_key=idempotency_key(kind, current.canonical_id, marker),
            payload=payload,
        )

    if previous is None:
        return [make(EventType.TITLE_CREATED, "created", {"name": current.name})]

    before = {s.number: s for s in previous.seasons}
    for season in current.seasons:
        old = before.get(season.number)
        if old is None:
            events.append(
                make(EventType.SEASON_ADDED, f"s{season.number}",
                     {"season": season.number, "name": season.name})
            )
            continue
        was = old.available_episodes_count or 0
        now = season.available_episodes_count or 0
        if now > was:
            events.append(
                make(
                    EventType.EPISODE_ADDED,
                    f"s{season.number}e{now}",
                    {"season": season.number, "available_episodes": now, "was": was},
                )
            )

    old_best = previous.best_rating()
    new_best = current.best_rating()
    if new_best is not None and (old_best is None or old_best.value != new_best.value):
        events.append(
            make(EventType.RATING_UPDATED, f"{new_best.source}:{new_best.value}",
                 {"source": new_best.source, "value": new_best.value})
        )

    was_playable = bool(previous.playback and previous.playback.available)
    is_playable = bool(current.playback and current.playback.available)
    if is_playable and not was_playable:
        events.append(make(EventType.PLAYBACK_AVAILABLE, "playable", {}))
    elif was_playable and not is_playable:
        events.append(make(EventType.PLAYBACK_UNAVAILABLE, "not-playable", {}))

    return events


class IngestionService:
    """Прогон обхода: от адаптера поставщика до хранилища и ленты событий."""

    def __init__(
        self,
        *,
        site_id: str,
        adapter: ProviderAdapter,
        store: InMemoryStore,
        limits: IngestionLimits | None = None,
    ) -> None:
        self.site_id = site_id
        self.adapter = adapter
        self.store = store
        self.limits = limits or IngestionLimits()
        self.events: list[ContentEvent] = []
        self._seen_keys: set[str] = set()

    def run(self, *, on_event: Callable[[ContentEvent], None] | None = None) -> IngestionRun:
        run_id = _run_id(self.site_id)
        token = WriteToken(run_id=run_id, site_id=self.site_id)
        started = utc_now()
        seen = 0
        failures = 0
        truncated = False

        try:
            source_total = self.adapter.total_titles()
        except ProviderUnavailable:
            source_total = None
            failures += 1
        self.store.declare_source_total(token, source_total)

        try:
            for title in self.adapter.walk_titles(limit=self.limits.max_titles):
                previous = None
                try:
                    previous = self.store.get(title.canonical_id)
                except ContractError:
                    previous = None
                for event in diff_titles(previous, title):
                    if event.idempotency_key in self._seen_keys:
                        # Дедупликация: тот же факт, увиденный дважды, остаётся
                        # одним событием.
                        continue
                    self._seen_keys.add(event.idempotency_key)
                    self.events.append(event)
                    if on_event:
                        on_event(event)
                self.store.put(token, [title])
                seen += 1
                if self.limits.max_titles and seen >= self.limits.max_titles:
                    break
        except CatalogTruncation:
            truncated = True
        except ProviderUnavailable:
            failures += 1

        coverage = CoverageReport(
            site_id=self.site_id,
            source_total=source_total,
            local_total=self.store.count(),
            observed_at=utc_now(),
        )
        if coverage.complete is False and not truncated and self.limits.max_titles is None:
            # Обход дошёл до конца, а записей меньше обещанного. Это не
            # «почти всё» — это неполный каталог, и он обязан быть виден.
            truncated = True

        return IngestionRun(
            run_id=run_id,
            site_id=self.site_id,
            started_at=started,
            finished_at=utc_now(),
            pages_walked=max(1, (seen + self.limits.page_size - 1) // self.limits.page_size),
            titles_seen=seen,
            failures=failures,
            truncated=truncated,
            coverage=coverage,
        )
