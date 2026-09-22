"""Покрытие каталога оценками.

Знаменатель — уникальные произведения, а не строки. Это не педантизм:
одно произведение с оценками AniList, Kitsu и Shikimori даёт три строки
источников, и «5603 записи» при 53 596 произведениях легко прочитать как
десять процентов покрытия, хотя покрыто вдвое меньше.

Поэтому отчёт всегда разделяет пять разных величин:

* уникальные произведения;
* внешние идентификаторы;
* исходные записи источников;
* оценки (записи со значением, прошедшим валидацию);
* успешно сопоставленные произведения.

Процент считается от полного канонического каталога, а для площадки — от
фактического каталога этой площадки.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from factory.unified_ratings.scale import ScoreState
from factory.unified_ratings.sources import EXTERNAL_DISPLAY_ORDER, REGISTRY
from factory.unified_ratings.store import UnifiedStore

#: SLA свежести по тирам расписания. Запись старше — устаревшая.
SLA_HOURS: dict[str, int] = {
    "ONGOING": 24,
    "RECENT_FINISHED": 24 * 7,
    "ARCHIVE": 24 * 30,
    "RETRY": 24 * 7,
    #: для пар вне расписания берём самый мягкий срок
    "UNSCHEDULED": 24 * 30,
}

#: Классы содержимого каталога. Тип приходит из каталога и может
#: отсутствовать — тогда произведение попадает в UNKNOWN, а не в «фильмы».
KIND_CLASSES: dict[str, tuple[str, ...]] = {
    "movie": ("movie", "film"),
    "series": ("tv", "tv_short", "series", "ona"),
    "ova": ("ova", "oav"),
    "special": ("special", "tv_special", "music"),
}


def classify_kind(kind: str) -> str:
    normalized = (kind or "").strip().lower().replace("-", "_")
    for label, values in KIND_CLASSES.items():
        if normalized in values:
            return label
    return "unknown"


@dataclass
class CoverageSlice:
    """Покрытие одного набора произведений."""

    name: str
    denominator_label: str
    titles_total: int = 0
    titles_with_external_ids: int = 0
    titles_without_external_ids: int = 0
    titles_with_any_rating: int = 0
    titles_with_2plus_ratings: int = 0
    titles_without_any_rating: int = 0
    titles_with_editorial: int = 0
    titles_with_community: int = 0
    titles_in_review: int = 0
    titles_blocked_by_ambiguous_match: int = 0
    titles_stale_by_sla: int = 0
    per_source: dict[str, int] = field(default_factory=dict)
    by_kind: dict[str, int] = field(default_factory=dict)
    #: величины, которые нельзя путать друг с другом
    external_id_count: int = 0
    source_record_count: int = 0
    rating_count: int = 0
    matched_title_count: int = 0

    def percent(self, value: int) -> float:
        if not self.titles_total:
            return 0.0
        return round(value * 100.0 / self.titles_total, 2)

    def as_dict(self) -> dict[str, Any]:
        def pair(value: int) -> dict[str, Any]:
            return {"count": value, "percent": self.percent(value)}

        return {
            "name": self.name,
            "denominator": self.denominator_label,
            "titles_total": self.titles_total,
            "distinct_counts": {
                "unique_titles": self.titles_total,
                "external_ids": self.external_id_count,
                "source_records": self.source_record_count,
                "ratings_with_value": self.rating_count,
                "matched_titles": self.matched_title_count,
            },
            "by_kind": self.by_kind,
            "with_any_external_rating": pair(self.titles_with_any_rating),
            "with_2plus_external_ratings": pair(self.titles_with_2plus_ratings),
            "with_editorial_rating": pair(self.titles_with_editorial),
            "with_community_rating": pair(self.titles_with_community),
            "without_any_rating": pair(self.titles_without_any_rating),
            "with_external_ids": pair(self.titles_with_external_ids),
            "without_external_ids": pair(self.titles_without_external_ids),
            "in_manual_review": pair(self.titles_in_review),
            "blocked_by_ambiguous_match": pair(self.titles_blocked_by_ambiguous_match),
            "stale_by_sla": pair(self.titles_stale_by_sla),
            "per_source": {
                key: pair(self.per_source.get(key, 0)) for key in EXTERNAL_DISPLAY_ORDER
            },
            "coverage_percent": self.percent(self.titles_with_any_rating),
        }


def _parse(stamp: str) -> datetime | None:
    if not stamp:
        return None
    try:
        return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


class CoverageReporter:
    def __init__(self, store: UnifiedStore, *, now: datetime | None = None) -> None:
        self.store = store
        self.now = now or datetime.now(timezone.utc)

    # ------------------------------------------------------------------

    def _ok_by_title(self) -> dict[str, set[str]]:
        """Произведение → множество источников с валидной оценкой."""
        out: dict[str, set[str]] = {}
        for row in self.store.query(
            "SELECT title_id, source_key FROM unified_external_current WHERE validation_state=?",
            (ScoreState.OK.value,),
        ):
            out.setdefault(row["title_id"], set()).add(row["source_key"])
        return out

    def _stale_titles(self) -> set[str]:
        """Произведения, у которых хотя бы одна запись просрочена по SLA."""
        tiers = {
            (r["title_id"], r["source_key"]): r["tier"]
            for r in self.store.query(
                "SELECT title_id, source_key, tier FROM unified_schedule_state"
            )
        }
        stale: set[str] = set()
        for row in self.store.query(
            "SELECT title_id, source_key, last_checked_at FROM unified_external_current"
        ):
            checked = _parse(row["last_checked_at"])
            if checked is None:
                stale.add(row["title_id"])
                continue
            tier = tiers.get((row["title_id"], row["source_key"]), "UNSCHEDULED")
            if self.now - checked > timedelta(hours=SLA_HOURS.get(tier, SLA_HOURS["UNSCHEDULED"])):
                stale.add(row["title_id"])
        return stale

    def _review_titles(self) -> set[str]:
        return {
            r["title_id"]
            for r in self.store.query(
                "SELECT DISTINCT title_id FROM unified_review_queue WHERE status='PENDING'"
            )
        }

    def _ambiguous_titles(self) -> set[str]:
        return {
            r["title_id"]
            for r in self.store.query(
                "SELECT DISTINCT title_id FROM unified_source_links"
                " WHERE status IN ('conflict','pending')"
            )
        }

    def _editorial_titles(self) -> set[str]:
        return {
            r["title_id"]
            for r in self.store.query(
                "SELECT DISTINCT title_id FROM unified_editorial_ratings WHERE status='ACTIVE'"
            )
        }

    def _community_titles(self) -> set[str]:
        return {
            r["title_id"]
            for r in self.store.query(
                "SELECT DISTINCT title_id FROM unified_user_aggregates WHERE vote_count > 0"
            )
        }

    def _matched_titles(self) -> set[str]:
        return {
            r["title_id"]
            for r in self.store.query(
                "SELECT DISTINCT title_id FROM unified_source_links"
                " WHERE status IN ('exact','reviewed')"
            )
        }

    # ------------------------------------------------------------------

    def slice_for(
        self, *, name: str, denominator_label: str, title_ids: set[str] | None
    ) -> CoverageSlice:
        """Покрытие набора произведений. ``None`` — весь каталог."""
        rows = self.store.query(
            "SELECT title_id, content_kind, external_ids_json FROM unified_titles"
        )
        if title_ids is not None:
            rows = [r for r in rows if r["title_id"] in title_ids]

        ok = self._ok_by_title()
        stale = self._stale_titles()
        review = self._review_titles()
        ambiguous = self._ambiguous_titles()
        editorial = self._editorial_titles()
        community = self._community_titles()
        matched = self._matched_titles()

        result = CoverageSlice(name=name, denominator_label=denominator_label)
        per_source: dict[str, int] = {}
        for row in rows:
            title_id = row["title_id"]
            result.titles_total += 1
            result.by_kind[classify_kind(row["content_kind"])] = (
                result.by_kind.get(classify_kind(row["content_kind"]), 0) + 1
            )
            ids = json.loads(row["external_ids_json"] or "{}")
            if ids:
                result.titles_with_external_ids += 1
                result.external_id_count += len(ids)
            else:
                result.titles_without_external_ids += 1

            sources = ok.get(title_id, set())
            if sources:
                result.titles_with_any_rating += 1
                result.rating_count += len(sources)
                if len(sources) >= 2:
                    result.titles_with_2plus_ratings += 1
                for key in sources:
                    per_source[key] = per_source.get(key, 0) + 1
            else:
                result.titles_without_any_rating += 1

            if title_id in editorial:
                result.titles_with_editorial += 1
            if title_id in community:
                result.titles_with_community += 1
            if title_id in review:
                result.titles_in_review += 1
            if title_id in ambiguous:
                result.titles_blocked_by_ambiguous_match += 1
            if title_id in stale:
                result.titles_stale_by_sla += 1
            if title_id in matched:
                result.matched_title_count += 1

        result.per_source = per_source
        scoped = (
            "SELECT COUNT(*) c FROM unified_external_current"
            if title_ids is None
            else None
        )
        if scoped:
            result.source_record_count = self.store.query_one(scoped)["c"]
        else:
            ids_list = list(title_ids or [])
            total = 0
            for start in range(0, len(ids_list), 500):
                chunk = ids_list[start : start + 500]
                marks = ",".join("?" * len(chunk))
                total += self.store.query_one(
                    f"SELECT COUNT(*) c FROM unified_external_current WHERE title_id IN ({marks})",
                    tuple(chunk),
                )["c"]
            result.source_record_count = total
        return result

    # ------------------------------------------------------------------

    def tenant_title_ids(self, tenant_id: str) -> set[str]:
        return {
            r["title_id"]
            for r in self.store.query(
                "SELECT DISTINCT title_id FROM unified_title_tenant_map WHERE tenant_id=?",
                (tenant_id,),
            )
        }

    def report(self, *, site_slices: dict[str, set[str]] | None = None) -> dict[str, Any]:
        slices = {
            "catalog": self.slice_for(
                name="полный канонический каталог",
                denominator_label="все уникальные произведения каталога",
                title_ids=None,
            ).as_dict()
        }
        for label, ids in (site_slices or {}).items():
            slices[label] = self.slice_for(
                name=label,
                denominator_label=f"фактический каталог {label}",
                title_ids=ids,
            ).as_dict()
        return {
            "generated_at": self.now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sla_hours": SLA_HOURS,
            "note": (
                "процент считается по уникальным произведениям; строки источников "
                "и внешние идентификаторы показаны отдельно и покрытием не являются"
            ),
            "sources_registry": {
                key: {
                    "status": REGISTRY[key].status.value,
                    "access_method": REGISTRY[key].access_method.value,
                }
                for key in EXTERNAL_DISPLAY_ORDER
            },
            "slices": slices,
        }


def load_site_title_ids(details_path: Path | str, *, provider: str = "nova") -> set[str]:
    """Произведения площадки из её собственного details-снимка.

    Каталог площадки — единственный честный знаменатель для неё: канон
    содержит 53 596 произведений, а сайт публикует свои семь с небольшим
    тысяч, и процент от каноничного каталога сказал бы о сайте неправду.
    """
    data = json.loads(Path(details_path).read_text(encoding="utf-8"))
    details = data.get("details") or {}
    out: set[str] = set()
    for entry in details.values():
        if not isinstance(entry, dict):
            continue
        internal = entry.get("id")
        if internal:
            out.add(f"{provider}:{internal}")
    return out
