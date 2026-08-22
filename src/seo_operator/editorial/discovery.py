"""
Редакционный discovery: находит новинки в разрешённых источниках и считает
editorial_opportunity. Владелец не даёт список тем — оператор находит их сам.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from ..connectors import fixtures
from .calendar import CalendarEntry, Status
from .duplicates import distinct_value_check


@dataclass
class EditorialOpportunity:
    external_id: str
    site_id: str
    title_ru: str
    score: float
    factors: dict[str, float]
    blockers: list[str]
    proposed_status: str
    rationale: str


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def editorial_opportunity(*, audience_interest: float, freshness: float, source_confidence: float,
                          rights_and_content_readiness: float, distinct_user_value: float,
                          engagement_potential: float, site_strategy_fit: float,
                          risk_and_effort: float) -> tuple[float, dict[str, float]]:
    factors = {
        "audience_interest": _clamp(audience_interest),
        "freshness": _clamp(freshness),
        "source_confidence": _clamp(source_confidence),
        "rights_and_content_readiness": _clamp(rights_and_content_readiness),
        "distinct_user_value": _clamp(distinct_user_value),
        "engagement_potential": _clamp(engagement_potential),
        "site_strategy_fit": _clamp(site_strategy_fit),
        "risk_and_effort": max(1.0, min(10.0, risk_and_effort)),
    }
    num = 1.0
    for k, v in factors.items():
        if k != "risk_and_effort":
            num *= v
    return round(num / factors["risk_and_effort"] * 1000, 3), factors


CONFIDENCE_NUM = {"unknown": 0.0, "low": 0.25, "medium": 0.55, "high": 0.9, "confirmed": 1.0}


def discover(site, catalog_items: list[dict[str, Any]], strategy: dict[str, Any],
             existing_content: list[dict[str, Any]] | None = None,
             demand_index: dict[str, float] | None = None,
             today: date | None = None) -> tuple[list[CalendarEntry], list[EditorialOpportunity]]:
    """
    Сопоставляет каталог со спросом и стратегией сайта.
    Возвращает записи календаря и приоритизированные редакционные возможности.
    """
    today = today or date.today()
    existing_content = existing_content or []
    demand_index = demand_index or {}
    forbidden = set(strategy.get("forbidden_topics") or [])
    priority_segments = set(strategy.get("priority_segments") or [])

    entries: list[CalendarEntry] = []
    opportunities: list[EditorialOpportunity] = []

    for item in catalog_items:
        blockers: list[str] = []

        if item.get("genre") in forbidden or item.get("external_id") in forbidden:
            continue

        confirmed = bool(item.get("release_date_confirmed"))
        release_date = item.get("release_date")
        status = Status.DISCOVERED
        if item.get("status") == "available":
            status = Status.RELEASED
        elif release_date and confirmed:
            status = Status.ANNOUNCED
        elif item.get("status") == "announced":
            status = Status.UNDATED

        entry = CalendarEntry(
            external_id=item["external_id"], site_id=site.site_id,
            title_ru=item["title_ru"], title_original=item.get("title_original"),
            status=status, release_date=release_date if confirmed else None,
            release_date_confirmed=confirmed,
            source=item.get("source", "unknown"),
            source_confidence=item.get("source_confidence", "unknown"),
            rights_ref=item.get("rights_ref"),
            checked_at=datetime.now(timezone.utc).isoformat(),
        )
        entries.append(entry)

        if not entry.rights_ref:
            blockers.append("нет rights_ref — публикация невозможна (GR-001)")
        if entry.source_confidence not in ("high", "confirmed"):
            blockers.append(f"source_confidence={entry.source_confidence}")

        ok, why = distinct_value_check(
            {"text": item.get("synopsis", ""), "facts": item.get("facts", [])},
            existing_content)
        if not ok:
            blockers.append(f"нет отдельной ценности: {why}")

        demand = demand_index.get(item["external_id"], 0.3)
        if release_date:
            days_to = (date.fromisoformat(release_date) - today).days
            freshness = 1.0 if -14 <= days_to <= 21 else max(0.2, 1 - abs(days_to) / 120)
        else:
            freshness = 0.4

        readiness = 0.0 if not entry.rights_ref else (0.9 if item.get("media_available") else 0.55)
        fit = 1.0 if (priority_segments & {"new_releases", "ongoing"}) else 0.7
        score, factors = editorial_opportunity(
            audience_interest=demand,
            freshness=freshness,
            source_confidence=CONFIDENCE_NUM.get(entry.source_confidence, 0.0),
            rights_and_content_readiness=readiness,
            distinct_user_value=1.0 if ok else 0.0,
            engagement_potential=0.7 if item.get("seasons", 1) > 1 else 0.5,
            site_strategy_fit=fit,
            risk_and_effort=1.0 + (2.0 if not confirmed else 0.0) + (1.0 if not item.get("media_available") else 0.0),
        )

        if blockers:
            proposed = "hold"
            rationale = "Заблокировано: " + "; ".join(blockers)
        elif status is Status.ANNOUNCED:
            proposed = "prepare_announcement"
            rationale = f"Подтверждённый анонс на {entry.date_display}; готовить страницу заранее."
        elif status is Status.UNDATED:
            proposed = "prepare_undated_announcement"
            rationale = "Анонс подтверждён, дата — нет. Публиковать как «дата не объявлена»."
        elif status is Status.RELEASED:
            proposed = "publish_or_improve"
            rationale = "Материал доступен; готовить/улучшать страницу и витрины."
        else:
            proposed = "watch"
            rationale = "Недостаточно подтверждений для анонса, оставить в наблюдении."

        opportunities.append(EditorialOpportunity(
            external_id=item["external_id"], site_id=site.site_id, title_ru=item["title_ru"],
            score=score, factors=factors, blockers=blockers,
            proposed_status=proposed, rationale=rationale,
        ))

    opportunities.sort(key=lambda o: -o.score)
    return entries, opportunities


def discover_from_fixture(site, strategy: dict[str, Any], **kwargs) -> tuple[list[CalendarEntry], list[EditorialOpportunity]]:
    if not site.site_id.startswith("demo-"):
        raise ValueError("Фикстурный каталог доступен только для demo-* сайтов.")
    return discover(site, fixtures.catalog_items(), strategy, **kwargs)
