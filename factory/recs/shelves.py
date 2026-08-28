"""Генераторы полок. Каждая полка отвечает на свой вопрос.

Разные полки опираются на разные даты, и смешивать их нельзя: «недавно
добавленные» — про дату поступления в каталог, «новинки» — про дату выхода,
«обновлённые сериалы» — про дату новой серии. Фильм 1979 года, заведённый
вчера, честно попадает в первую полку и не должен попадать во вторую.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from factory.recs.model import merge_duplicates
from factory.recs.ranker import (
    ALGORITHM_VERSION,
    Scored,
    diversify,
    is_eligible,
    rating_confidence,
    score_item,
)

LATEST_ADDED = "latest_added"
NEW_RELEASES = "new_releases"
UPDATED_SERIES = "updated_series"
MONTHLY_POPULAR = "monthly_popular"
HIGH_RATED = "high_rated"
REFERENCE_TRENDING = "reference_trending"
SIMILAR = "similar"
EDITORIAL = "editorial"

SHELF_TITLES = {
    LATEST_ADDED: "Недавно добавленные",
    NEW_RELEASES: "Новинки",
    UPDATED_SERIES: "Новые серии",
    MONTHLY_POPULAR: "Популярное за месяц",
    HIGH_RATED: "Высокие оценки",
    REFERENCE_TRENDING: "Сейчас смотрят",
    SIMILAR: "Похожее",
    EDITORIAL: "Выбор редакции",
}


@dataclass(frozen=True)
class Shelf:
    shelf_id: str
    title: str
    items: tuple[Scored, ...]
    algorithm_version: str = ALGORITHM_VERSION

    def __len__(self) -> int:
        return len(self.items)


def _eligible(items, *, domain, profile_directions, editorial, now):
    merged = merge_duplicates(items)
    return [i for i in merged
            if is_eligible(i, domain=domain, profile_directions=profile_directions,
                           editorial=editorial, now=now)[0]]


def build_shelf(shelf_id: str, items, *, now: datetime | None = None, limit: int = 18,
                domain: str | None = None, profile_directions: tuple = (),
                editorial=None) -> Shelf:
    now = now or datetime.now(timezone.utc)
    pool = _eligible(items, domain=domain, profile_directions=profile_directions,
                     editorial=editorial, now=now)

    if shelf_id == LATEST_ADDED:
        pool = [i for i in pool if i.added_at is not None]
        pool.sort(key=lambda i: (i.added_at, i.content_id), reverse=True)
    elif shelf_id == NEW_RELEASES:
        # Именно дата выхода, а не дата попадания в каталог.
        cutoff = now - timedelta(days=400)
        pool = [i for i in pool if i.release_date is not None and i.release_date >= cutoff]
        pool.sort(key=lambda i: (i.release_date, i.content_id), reverse=True)
    elif shelf_id == UPDATED_SERIES:
        pool = [i for i in pool if i.episode_updated_at is not None]
        pool.sort(key=lambda i: (i.episode_updated_at, i.content_id), reverse=True)
    elif shelf_id == HIGH_RATED:
        rated = [(i, rating_confidence(i)) for i in pool]
        rated = [(i, c) for i, c in rated if c is not None]
        rated.sort(key=lambda pair: (-pair[1], pair[0].content_id))
        pool = [i for i, _ in rated]
    elif shelf_id == MONTHLY_POPULAR:
        pool = [i for i in pool if isinstance(i.events_30d, int)]
        pool.sort(key=lambda i: (-(i.events_30d or 0), i.content_id))
    elif shelf_id == REFERENCE_TRENDING:
        pool = [i for i in pool if i.reference_mentions]

    scored = [score_item(i, now, editorial=editorial) for i in pool]
    if shelf_id in (MONTHLY_POPULAR, REFERENCE_TRENDING, EDITORIAL, SIMILAR):
        scored.sort(key=lambda s: (-round(s.score, 12), s.item.content_id))
    if editorial is not None:
        scored = editorial.apply_pins(scored, now, domain=domain, shelf=shelf_id)
    return Shelf(shelf_id, SHELF_TITLES.get(shelf_id, shelf_id),
                 tuple(diversify(scored, limit, now)))
