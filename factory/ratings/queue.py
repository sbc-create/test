"""Планирование ежедневной очереди с жёстким приоритетом."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from factory.ratings.config import (
    PRIORITY_ACTIVE_SEASONAL,
    PRIORITY_ARCHIVE,
    PRIORITY_HOME_TOP_NO_RATING,
    PRIORITY_LABELS,
    PRIORITY_NEW_30_DAYS,
    PRIORITY_NEW_CATALOG,
    PRIORITY_ONGOING_NEW_EPISODE,
    PRIORITY_POPULAR_NO_RATING,
    PRIORITY_RELEASE_180_DAYS,
    PRIORITY_STALE_REFRESH,
    RatingsConfig,
)
from factory.ratings.models import CatalogTitle
from factory.ratings.store import RatingsStore


def classify_priority(title: CatalogTitle, *, has_fresh_rating: bool = False) -> tuple[int, str]:
    """Меньший номер = выше приоритет. Неизменённый rated title → archive/stale."""
    if getattr(title, "is_new_catalog", False):
        return PRIORITY_NEW_CATALOG, PRIORITY_LABELS[PRIORITY_NEW_CATALOG]
    if title.is_ongoing and title.has_new_episode:
        return PRIORITY_ONGOING_NEW_EPISODE, PRIORITY_LABELS[PRIORITY_ONGOING_NEW_EPISODE]
    if title.is_seasonal and title.is_ongoing:
        return PRIORITY_ACTIVE_SEASONAL, PRIORITY_LABELS[PRIORITY_ACTIVE_SEASONAL]
    days = title.days_since_release
    if days is not None and days <= 30:
        return PRIORITY_NEW_30_DAYS, PRIORITY_LABELS[PRIORITY_NEW_30_DAYS]
    if title.on_home_or_top and not title.has_rating:
        return PRIORITY_HOME_TOP_NO_RATING, PRIORITY_LABELS[PRIORITY_HOME_TOP_NO_RATING]
    if title.is_popular and not title.has_rating:
        return PRIORITY_POPULAR_NO_RATING, PRIORITY_LABELS[PRIORITY_POPULAR_NO_RATING]
    if days is not None and days <= 180:
        return PRIORITY_RELEASE_180_DAYS, PRIORITY_LABELS[PRIORITY_RELEASE_180_DAYS]
    if title.has_rating and not has_fresh_rating:
        return PRIORITY_STALE_REFRESH, PRIORITY_LABELS[PRIORITY_STALE_REFRESH]
    return PRIORITY_ARCHIVE, PRIORITY_LABELS[PRIORITY_ARCHIVE]


def plan_queue(
    store: RatingsStore,
    titles: Iterable[CatalogTitle],
    *,
    source_key: str,
    config: RatingsConfig,
    skip_fresh: set[str] | None = None,
) -> dict:
    """Спланировать кандидатов. Не превышает daily_candidate_cap уникальных."""
    skip_fresh = skip_fresh or set()
    ranked: list[tuple[int, str, CatalogTitle]] = []
    for title in titles:
        if title.canonical_title_id in skip_fresh:
            continue
        # Не запрашивать неизменённый title каждый день, если уже свежий.
        current = store.get_current(title.canonical_title_id, source_key)
        has_fresh = bool(current and current[0].get("freshness") == "FRESH")
        if has_fresh and not title.has_new_episode and not getattr(title, "is_new_catalog", False):
            continue
        pr, label = classify_priority(title, has_fresh_rating=has_fresh)
        # Prefer new_catalog flag
        if getattr(title, "is_new_catalog", False):
            pr, label = PRIORITY_NEW_CATALOG, PRIORITY_LABELS[PRIORITY_NEW_CATALOG]
        elif title.is_ongoing and title.has_new_episode:
            pr, label = PRIORITY_ONGOING_NEW_EPISODE, PRIORITY_LABELS[PRIORITY_ONGOING_NEW_EPISODE]
        ranked.append((pr, label, title))

    ranked.sort(key=lambda x: (x[0], x[2].canonical_title_id))
    cap = config.daily_candidate_cap
    selected = ranked[:cap]
    enqueued = 0
    for pr, label, title in selected:
        if store.enqueue(
            canonical_title_id=title.canonical_title_id,
            source_key=source_key,
            priority=pr,
            priority_label=label,
        ):
            enqueued += 1
            # Persist verified mapping hint when external id known
            from factory.ratings.mapping import resolve_mapping

            decision = resolve_mapping(title, source_key=source_key)
            if decision.mapping and decision.auto_publish:
                store.upsert_mapping(decision.mapping)
            elif decision.conflict_reason and decision.review_candidates:
                store.add_review(
                    canonical_title_id=title.canonical_title_id,
                    source_key=source_key,
                    candidates=decision.review_candidates,
                    reason=decision.conflict_reason,
                )
                if decision.conflict_reason.startswith("conflict") or decision.conflict_reason.startswith("multiple"):
                    store.add_conflict(
                        canonical_title_id=title.canonical_title_id,
                        source_key=source_key,
                        reason=decision.conflict_reason,
                        evidence={"candidates": decision.review_candidates},
                    )

    breakdown: dict[str, int] = {}
    for pr, label, _ in selected:
        breakdown[label] = breakdown.get(label, 0) + 1

    return {
        "source": source_key,
        "planned_candidates": len(selected),
        "enqueued": enqueued,
        "candidate_cap": cap,
        "success_target": config.daily_success_target,
        "priority_breakdown": breakdown,
        "backlog_remaining": max(0, len(ranked) - len(selected)),
        "planned_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def enqueue_new_title(store: RatingsStore, title: CatalogTitle, *, source_key: str) -> None:
    """Новый catalog publish сразу ставит title в очередь (не ждёт ночного обхода)."""
    store.enqueue(
        canonical_title_id=title.canonical_title_id,
        source_key=source_key,
        priority=PRIORITY_NEW_CATALOG,
        priority_label=PRIORITY_LABELS[PRIORITY_NEW_CATALOG],
    )
    from factory.ratings.mapping import resolve_mapping

    decision = resolve_mapping(title, source_key=source_key)
    if decision.mapping and decision.auto_publish:
        store.upsert_mapping(decision.mapping)
