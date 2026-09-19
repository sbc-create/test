"""Загрузка кандидатов из catalog snapshot (read-only)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from factory.ratings.models import CatalogTitle


def titles_from_catalog_items(
    items: list[dict[str, Any]],
    *,
    provider: str = "nova",
    limit: int | None = None,
    now: datetime | None = None,
) -> list[CatalogTitle]:
    now = now or datetime.now(timezone.utc)
    out: list[CatalogTitle] = []
    for raw in items:
        ext_id = str(raw.get("external_id") or raw.get("id") or "")
        if not ext_id:
            continue
        external_ids = dict(raw.get("external_ids") or {})
        if "myanimelist" not in external_ids and external_ids.get("mal"):
            external_ids["myanimelist"] = str(external_ids["mal"])
        kind = "tv" if raw.get("is_series") or str(raw.get("type") or "").lower() == "tv" else "movie"
        if str(raw.get("type") or "").lower() in ("ova", "ona", "special"):
            kind = str(raw.get("type")).lower()
        year = raw.get("year")
        year_i = int(year) if isinstance(year, int) else None

        created = _parse_ts(raw.get("created_at") or raw.get("createdAt"))
        updated = _parse_ts(raw.get("updated_at") or raw.get("updatedAt"))
        days = None
        if created:
            days = max(0, (now - created).days)
        elif year_i:
            days = max(0, (now.year - year_i) * 365)

        tags = raw.get("tags") or []
        tag_text = " ".join(str(t).lower() for t in tags) if isinstance(tags, list) else str(tags).lower()
        ongoing_hint = bool(raw.get("is_ongoing") or raw.get("ongoing")) or (
            "ongoing" in tag_text or "онгоинг" in tag_text or "выходит" in tag_text
        )
        # New episode heuristic: updated within 48h and series
        has_new_ep = bool(raw.get("has_new_episode"))
        if not has_new_ep and ongoing_hint and updated and (now - updated).total_seconds() < 48 * 3600:
            has_new_ep = True
        is_seasonal = bool(raw.get("is_seasonal")) or ("сезон" in tag_text or "season" in tag_text)
        # New catalog: created within 7 days
        is_new = bool(raw.get("is_new_catalog"))
        if not is_new and created and (now - created).days <= 7:
            is_new = True

        has_rating = bool(raw.get("kinopoisk_rating") or raw.get("imdb_rating"))
        title = CatalogTitle(
            canonical_title_id=f"{provider}:{ext_id}",
            title=str(raw.get("name") or ""),
            original_title=str(raw.get("original_name") or raw.get("name") or ""),
            russian_title=str(raw.get("name") or ""),
            year=year_i,
            kind=kind,
            is_ongoing=ongoing_hint,
            has_new_episode=has_new_ep,
            is_seasonal=is_seasonal,
            days_since_release=days,
            on_home_or_top=bool(raw.get("on_home") or raw.get("on_top")),
            is_popular=bool(raw.get("is_popular")),
            external_ids={k: str(v) for k, v in external_ids.items() if v is not None},
            has_rating=has_rating,
            is_new_catalog=is_new,
            first_seen_at=created.strftime("%Y-%m-%dT%H:%M:%SZ") if created else "",
        )
        out.append(title)
        if limit is not None and len(out) >= limit:
            break
    return out


def _parse_ts(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        # ms or s
        ts = float(value)
        if ts > 1e12:
            ts /= 1000.0
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        text = value.strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return None


def load_catalog_json(path: Path, *, limit: int | None = None) -> list[CatalogTitle]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = data.get("items") if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ValueError(f"catalog {path} has no items list")
    return titles_from_catalog_items(items, limit=limit)


def iter_mal_mapped(titles: list[CatalogTitle]) -> Iterator[CatalogTitle]:
    for t in titles:
        ext = t.external_ids
        if ext.get("myanimelist") or ext.get("shikimori") or ext.get("mal"):
            yield t
