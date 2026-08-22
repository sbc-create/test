"""
Детерминированные фикстуры для dry-run и тестов.

Доступны ТОЛЬКО для site_id с префиксом `demo-`. Настоящие сайты никогда
не получают синтетические данные: иначе отчёт покажет несуществующий рост.
Генератор детерминирован (seed от site_id+date), чтобы тесты были воспроизводимы.
"""
from __future__ import annotations

import hashlib
import math
from datetime import date, timedelta
from typing import TYPE_CHECKING

from .base import ConnectorResult

if TYPE_CHECKING:
    from .base import Connector

FIXTURE_TITLES = [
    ("stellar-drift", "Звёздный дрейф", "Stellar Drift", "2026-09-05"),
    ("iron-garden", "Железный сад", "Iron Garden", "2026-08-28"),
    ("quiet-harbor", "Тихая гавань", "Quiet Harbor", None),
    ("last-signal", "Последний сигнал", "The Last Signal", "2026-10-12"),
    ("paper-moon", "Бумажная луна", "Paper Moon", None),
]


def _rand(seed: str) -> float:
    """Детерминированный [0,1) из строки."""
    h = hashlib.sha256(seed.encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big") / 2**64


def _seasonal(d: date) -> float:
    """Недельная сезонность: выходные выше буднего."""
    return 1.0 + 0.18 * math.sin((d.weekday() / 7.0) * 2 * math.pi)


def gsc_rows(conn: "Connector", start: date, end: date) -> ConnectorResult:
    if not conn.site.site_id.startswith("demo-"):
        return conn.not_configured("фикстуры доступны только для demo-* сайтов")

    rows = []
    cutoff = conn.complete_through()
    d = start
    while d <= end:
        base = 400 + 300 * _rand(f"{conn.site.site_id}:{d}")
        clicks = round(base * _seasonal(d))
        impressions = round(clicks * (14 + 6 * _rand(f"imp:{d}")))
        position = round(11.0 - 4.0 * _rand(f"pos:{d}"), 2)
        rows.append({
            "date": d.isoformat(),
            "clicks": clicks,
            "impressions": impressions,
            "ctr": round(clicks / impressions, 4),
            "position": position,
        })
        d += timedelta(days=1)

    for slug, ru, orig, _rel in FIXTURE_TITLES:
        r = _rand(f"{conn.site.site_id}:{slug}")
        rows.append({
            "date": end.isoformat(),
            "query": f"{ru} смотреть",
            "page": f"https://{conn.site.domain}/title/{slug}",
            "clicks": round(40 + 200 * r),
            "impressions": round(900 + 5000 * r),
            "ctr": round(0.02 + 0.05 * r, 4),
            "position": round(4 + 16 * (1 - r), 2),
        })
        rows.append({
            "date": end.isoformat(),
            "query": f"{orig.lower()} 2 сезон",
            "page": f"https://{conn.site.domain}/title/{slug}",
            "clicks": round(5 + 40 * r),
            "impressions": round(300 + 2500 * r),
            "ctr": round(0.01 + 0.03 * r, 4),
            "position": round(9 + 20 * (1 - r), 2),
        })

    return ConnectorResult(
        source=conn.source_id, site_id=conn.site.site_id, rows=rows,
        source_window=f"{start}..{end}", timezone=conn.site.timezone,
        data_freshness=f"complete_through={cutoff}",
        completeness=conn.completeness_for(min(end, cutoff)),
        note="FIXTURE DATA — не производственные показатели.",
    )


def yandex_query_rows(conn: "Connector", start: date, end: date) -> ConnectorResult:
    if not conn.site.site_id.startswith("demo-"):
        return conn.not_configured("фикстуры доступны только для demo-* сайтов")
    rows = []
    for slug, ru, orig, _rel in FIXTURE_TITLES:
        r = _rand(f"ya:{conn.site.site_id}:{slug}")
        rows.append({
            "date": end.isoformat(),
            "query": f"{ru} смотреть онлайн",
            "shows": round(1500 + 9000 * r),
            "clicks": round(60 + 400 * r),
            "position": round(3 + 18 * (1 - r), 2),
        })
    rows.append({"date": end.isoformat(), "metric": "indexed_pages", "value": 4200})
    rows.append({"date": end.isoformat(), "metric": "excluded_pages", "value": 310})
    return ConnectorResult(
        source=conn.source_id, site_id=conn.site.site_id, rows=rows,
        source_window=f"{start}..{end}", timezone=conn.site.timezone,
        data_freshness=f"complete_through={conn.complete_through()}",
        completeness=conn.completeness_for(min(end, conn.complete_through())),
        note="FIXTURE DATA — не производственные показатели.",
    )


def metrika_rows(conn: "Connector", start: date, end: date) -> ConnectorResult:
    if not conn.site.site_id.startswith("demo-"):
        return conn.not_configured("фикстуры доступны только для demo-* сайтов")
    rows = []
    d = start
    while d <= end:
        r = _rand(f"mtr:{conn.site.site_id}:{d}")
        sessions = round((900 + 700 * r) * _seasonal(d))
        rows.append({
            "date": d.isoformat(),
            "organic_sessions": sessions,
            "player_starts": round(sessions * (0.28 + 0.12 * r)),
            "pages_per_session": round(2.1 + 1.4 * r, 2),
            "returning_share": round(0.22 + 0.18 * r, 3),
        })
        d += timedelta(days=1)
    return ConnectorResult(
        source=conn.source_id, site_id=conn.site.site_id, rows=rows,
        source_window=f"{start}..{end}", timezone=conn.site.timezone,
        data_freshness=f"complete_through={conn.complete_through()}",
        completeness=conn.completeness_for(min(end, conn.complete_through())),
        note="FIXTURE DATA — не производственные показатели.",
    )


def catalog_items() -> list[dict]:
    """Синтетический каталог для редакционного discovery."""
    out = []
    for slug, ru, orig, release in FIXTURE_TITLES:
        out.append({
            "external_id": slug,
            "title_ru": ru,
            "title_original": orig,
            "release_date": release,
            "release_date_confirmed": release is not None,
            "status": "announced" if release else "available",
            "rights_ref": f"rights://demo/{slug}",
            "source": "cdnvideohub_fixture",
            "source_confidence": "high" if release else "high",
            "seasons": 2 if slug in {"stellar-drift", "iron-garden"} else 1,
            "media_available": release is None,
        })
    return out
