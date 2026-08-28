"""Хранилище витрин с последней заведомо рабочей версией.

Обновление витрины не имеет права ухудшить её. Поставщик отвечает не всегда, и
полка, собранная во время сбоя, оказывается короче или пустой. Показать
посетителю обрубок хуже, чем показать вчерашнюю подборку: вчерашняя хотя бы
работает.

Поэтому новая версия заменяет прежнюю только целиком и только пройдя проверку.
Наполовину собранная полка не публикуется никогда.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

#: Полка короче этого выглядит как сбой, а не как подборка.
MIN_SHELF_ITEMS = 10


class ShelfRejected(Exception):
    """Новая версия полки не принята; в работе осталась прежняя."""


@dataclass
class StoredShelf:
    shelf_id: str
    domain: str
    items: tuple
    algorithm_version: str
    built_at: datetime


@dataclass
class CarouselStore:
    """Последняя принятая версия каждой полки на каждом домене."""

    minimum: int = MIN_SHELF_ITEMS
    _shelves: dict = field(default_factory=dict)
    rejections: list = field(default_factory=list)

    def _key(self, domain: str, shelf_id: str):
        return (domain, shelf_id)

    def get(self, domain: str, shelf_id: str) -> StoredShelf | None:
        return self._shelves.get(self._key(domain, shelf_id))

    def validate(self, items) -> tuple[bool, str]:
        """Полка целостна? Проверяется до публикации, а не после."""
        if len(items) < self.minimum:
            return False, f"в полке {len(items)} записей, нужно не меньше {self.minimum}"
        seen = set()
        for scored in items:
            item = scored.item
            if item.playback_state is not True:
                return False, f"{item.content_id}: воспроизведение не подтверждено"
            if not item.poster or not item.title.strip():
                return False, f"{item.content_id}: карточку нечем показать"
            if item.content_id in seen:
                return False, f"{item.content_id}: запись встречается дважды"
            seen.add(item.content_id)
        return True, "ok"

    def publish(self, domain: str, shelf_id: str, items, *,
                algorithm_version: str, now: datetime | None = None) -> StoredShelf:
        """Принять новую версию — или оставить прежнюю и сказать почему."""
        now = now or datetime.now(timezone.utc)
        ok, reason = self.validate(items)
        if not ok:
            self.rejections.append({"domain": domain, "shelf_id": shelf_id,
                                    "reason": reason, "at": now.isoformat()})
            previous = self.get(domain, shelf_id)
            if previous is None:
                raise ShelfRejected(f"{shelf_id}: {reason}; прежней версии нет")
            raise ShelfRejected(f"{shelf_id}: {reason}; в работе осталась версия "
                                f"от {previous.built_at.isoformat()}")
        stored = StoredShelf(shelf_id, domain, tuple(items), algorithm_version, now)
        self._shelves[self._key(domain, shelf_id)] = stored
        return stored

    def serve(self, domain: str, shelf_id: str) -> StoredShelf | None:
        """То, что показывается посетителю прямо сейчас."""
        return self.get(domain, shelf_id)
