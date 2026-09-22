#!/usr/bin/env python3
"""Отчёт этапа: покрытие, сводная оценка, очередь проверки, суточная квота.

Все числа берутся из базы. Там, где измерения не было, печатается
UNMEASURED с причиной — прочерк и ноль в отчёте о покрытии выглядят
одинаково, и это ровно та пара, которую нельзя путать.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from factory.unified_ratings.composite import (  # noqa: E402
    FORMULA_VERSION,
    MIN_SOURCES,
    recompute_many,
)
from factory.unified_ratings.coverage import CoverageReporter, load_site_title_ids  # noqa: E402
from factory.unified_ratings.daily_queue import DailyQueue  # noqa: E402
from factory.unified_ratings.sources import EXTERNAL_DISPLAY_ORDER, REGISTRY  # noqa: E402
from factory.unified_ratings.store import UnifiedStore  # noqa: E402

SITE_DETAILS = "/srv/lords/.frontend/animedia-01-details.json"
SPACE = "animedia"


def review_triage(store: UnifiedStore) -> dict:
    """Разбор очереди проверки по причинам с примерами для человека."""
    rows = store.query(
        """SELECT r.review_id, r.title_id, t.title_ru, t.release_year, t.content_kind,
                  r.source_key, r.reason_code, r.detail
           FROM unified_review_queue r
           LEFT JOIN unified_titles t ON t.title_id = r.title_id
           WHERE r.status='PENDING'
           ORDER BY r.reason_code, t.title_ru"""
    )
    by_reason: dict[str, list[dict]] = {}
    for row in rows:
        by_reason.setdefault(row["reason_code"], []).append(dict(row))
    counts = {reason: len(items) for reason, items in by_reason.items()}
    by_source = Counter(r["source_key"] for r in rows)
    return {
        "total_pending": len(rows),
        "by_reason": dict(sorted(counts.items(), key=lambda kv: -kv[1])),
        "by_source": dict(by_source),
        "auto_published": 0,
        "note": (
            "ни одна запись очереди не публикуется автоматически: строка "
            "источника получает состояние PENDING_REVIEW вместо значения"
        ),
        "samples_per_reason": {
            reason: [
                {
                    "title": item["title_ru"],
                    "year": item["release_year"],
                    "kind": item["content_kind"],
                    "source": item["source_key"],
                    "detail": item["detail"][:160],
                }
                for item in items[:5]
            ]
            for reason, items in by_reason.items()
        },
    }


def source_status(store: UnifiedStore) -> dict:
    out = {}
    for key in EXTERNAL_DISPLAY_ORDER:
        source = REGISTRY[key]
        runs = store.query(
            """SELECT COALESCE(SUM(requested),0) req, COALESCE(SUM(received),0) recv,
                      COALESCE(SUM(inserted),0) ins, COALESCE(SUM(updated),0) upd,
                      COALESCE(SUM(unchanged),0) unch, COALESCE(SUM(not_found),0) nf,
                      COALESCE(SUM(failed),0) fail, COUNT(*) runs
               FROM unified_import_runs WHERE source_key=? AND dry_run=0""",
            (key,),
        )[0]
        matched = store.count(
            "unified_source_links", "source_key=? AND status IN ('exact','reviewed')", (key,)
        )
        records = store.count("unified_external_current", "source_key=?", (key,))
        ok = store.count(
            "unified_external_current", "source_key=? AND validation_state='OK'", (key,)
        )
        last = store.query_one(
            "SELECT cursor_out FROM unified_import_runs WHERE source_key=? AND dry_run=0"
            " ORDER BY started_at DESC LIMIT 1",
            (key,),
        )
        out[key] = {
            "SOURCE_NAME": key,
            "ACCESS_TYPE": {
                "OFFICIAL_API": "OFFICIAL_API",
                "EXISTING_PROJECT_CONNECTOR": "AUTHORIZED_CONNECTOR",
            }.get(source.access_method.value, "CONTRACT_FEED")
            if source.status.value != "BLOCKED_SECRET"
            else "BLOCKED",
            "STATUS": source.status.value,
            "TOTAL_FETCHED": int(runs["recv"]),
            "TOTAL_IMPORTED": int(runs["ins"]) + int(runs["upd"]),
            "UNIQUE_TITLES_MATCHED": matched,
            "RECORDS_STORED": records,
            "RECORDS_WITH_VALUE": ok,
            "NOT_FOUND": int(runs["nf"]),
            "FAILED": int(runs["fail"]),
            "RUNS": int(runs["runs"]),
            "LAST_CURSOR": (last or {"cursor_out": ""})["cursor_out"],
            "BLOCKER": source.blocker,
        }
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--recompute-composite", action="store_true")
    args = parser.parse_args()

    store = UnifiedStore(args.db, apply_migration=False)
    site_ids: set[str] = set()
    if Path(SITE_DETAILS).is_file():
        known = {r["title_id"] for r in store.query("SELECT title_id FROM unified_titles")}
        site_ids = load_site_title_ids(SITE_DETAILS) & known

    if args.recompute_composite:
        candidates = [
            r["title_id"]
            for r in store.query(
                """SELECT title_id FROM unified_external_current
                   WHERE validation_state='OK' GROUP BY title_id HAVING COUNT(*) >= ?""",
                (MIN_SOURCES,),
            )
        ]
        print(f"пересчёт сводной оценки: {len(candidates)} произведений"
              f" с >= {MIN_SOURCES} источниками")
        states = recompute_many(store, candidates)
        print("  состояния:", json.dumps(states, ensure_ascii=False))

    coverage = CoverageReporter(store).report(site_slices={"animedia.icu": site_ids})
    composite_total = store.count(
        "unified_composite_ratings", "state='OK' AND formula_version=?", (FORMULA_VERSION,)
    )
    composite_site = 0
    if site_ids:
        ids = list(site_ids)
        for start in range(0, len(ids), 500):
            chunk = ids[start : start + 500]
            marks = ",".join("?" * len(chunk))
            composite_site += store.query_one(
                f"SELECT COUNT(*) c FROM unified_composite_ratings"
                f" WHERE state='OK' AND formula_version=? AND title_id IN ({marks})",
                (FORMULA_VERSION, *chunk),
            )["c"]

    daily = DailyQueue(store, site_title_ids=site_ids).report(
        coverage_before=0.0,
        coverage_after=coverage["slices"]["catalog"]["coverage_percent"],
    )

    catalog = coverage["slices"]["catalog"]
    site = coverage["slices"].get("animedia.icu", {})
    report = {
        "coverage": coverage,
        "composite": {
            "COMPOSITE_FORMULA_VERSION": FORMULA_VERSION,
            "COMPOSITE_MIN_SOURCES": MIN_SOURCES,
            "TITLES_WITH_COMPOSITE_RATING": composite_total,
            "COMPOSITE_COVERAGE_PERCENT": round(
                composite_total * 100.0 / max(1, catalog["titles_total"]), 2
            ),
            "ANIMEDIA_ICU_TITLES_WITH_COMPOSITE": composite_site,
            "ANIMEDIA_ICU_COMPOSITE_COVERAGE_PERCENT": round(
                composite_site * 100.0 / max(1, site.get("titles_total", 1)), 2
            ),
        },
        "sources": source_status(store),
        "review_queue": review_triage(store),
        "daily": daily.as_dict(),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"\nКАТАЛОГ: {catalog['titles_total']} произведений, "
          f"с оценкой {catalog['with_any_external_rating']['count']} "
          f"({catalog['with_any_external_rating']['percent']}%), "
          f"с двумя и более {catalog['with_2plus_external_ratings']['count']} "
          f"({catalog['with_2plus_external_ratings']['percent']}%)")
    if site:
        print(f"ANIMEDIA.ICU: {site['titles_total']} произведений, "
              f"с оценкой {site['with_any_external_rating']['count']} "
              f"({site['with_any_external_rating']['percent']}%), "
              f"с двумя и более {site['with_2plus_external_ratings']['count']} "
              f"({site['with_2plus_external_ratings']['percent']}%)")
    print(f"СВОДНАЯ ОЦЕНКА: {composite_total} произведений "
          f"({report['composite']['COMPOSITE_COVERAGE_PERCENT']}%),"
          f" на animedia.icu {composite_site}")
    print(f"REVIEW QUEUE: {report['review_queue']['total_pending']} — "
          f"{json.dumps(report['review_queue']['by_reason'], ensure_ascii=False)}")
    print(f"СУТКИ: выполнено {daily.completed} из {daily.target}, backlog {daily.pending_backlog}, "
          f"режим {daily.mode}")
    store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
