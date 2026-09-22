#!/usr/bin/env python3
"""Суточное пополнение оценок: очередь по приоритету, цель 500 изменений.

Цель считается в парах «произведение + источник», у которых значение
появилось или изменилось. Повторное чтение неизменившегося в цель не
идёт: «пятьсот проверок» и «пятьсот новых оценок» — разные обещания, и
счётчик, который их путает, выполняется мгновенно и ничего не значит.

Когда законных изменений меньше цели, это не ошибка. Отчёт показывает,
что источник исчерпан или не дал нового, и система переходит из режима
наполнения в режим актуализации, а не создаёт объём ради цифры.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from factory.ratings.adapters.base import AdapterError  # noqa: E402
from factory.unified_ratings.adapters import build_adapter  # noqa: E402
from factory.unified_ratings.adapters.provider_feed import ProviderFeedAdapter  # noqa: E402
from factory.unified_ratings.composite import MIN_SOURCES, recompute_many  # noqa: E402
from factory.unified_ratings.coverage import CoverageReporter, load_site_title_ids  # noqa: E402
from factory.unified_ratings.daily_queue import DAILY_TARGET, DailyQueue  # noqa: E402
from factory.unified_ratings.ingestion import Ingestor  # noqa: E402
from factory.unified_ratings.sources import get  # noqa: E402
from factory.unified_ratings.store import UnifiedStore  # noqa: E402
from factory.unified_ratings.titles import TitleRegistry, load_catalog_items  # noqa: E402

CATALOG = "/srv/site-factory/repo/var/lords/lords/catalog-cache/lords-01.json"
SITE_DETAILS = "/srv/lords/.frontend/animedia-01-details.json"
MIN_FREE_MB = 1024

#: Дольше этого окна без единого нового результата — повод для тревоги,
#: а не для молчания: «ноль изменений» и «сбор сломан» выглядят одинаково.
STALE_ALERT_HOURS = 48


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def feed_items(field: str) -> dict:
    out = {}
    for item in load_catalog_items(CATALOG):
        ext = (item.get("external_ids") or {}).get(field)
        if ext:
            out[str(ext)] = item
    return out


def adapter_for(source_key: str):
    if source_key.startswith("provider_feed"):
        field = "imdb" if source_key.endswith("imdb") else "kinopoisk"
        return ProviderFeedAdapter(source_key, feed_items(field))
    return build_adapter(source_key)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--target", type=int, default=DAILY_TARGET)
    parser.add_argument("--evidence", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    free_mb = shutil.disk_usage(Path(args.db).parent).free // 2**20
    if free_mb < MIN_FREE_MB:
        print(json.dumps({"status": "SKIPPED_LOW_DISK", "free_mb": free_mb}, ensure_ascii=False))
        return 0

    store = UnifiedStore(args.db, apply_migration=False)
    registry = TitleRegistry(store)
    site_ids: set[str] = set()
    if Path(SITE_DETAILS).is_file():
        known = {r["title_id"] for r in store.query("SELECT title_id FROM unified_titles")}
        site_ids = load_site_title_ids(SITE_DETAILS) & known

    before = CoverageReporter(store).slice_for(
        name="catalog", denominator_label="весь каталог", title_ids=None
    )
    coverage_before = before.percent(before.titles_with_any_rating)

    queue = DailyQueue(store, site_title_ids=site_ids)
    items = queue.build(limit=args.target * 3)
    by_source: dict[str, list[str]] = {}
    for item in items:
        by_source.setdefault(item.source_key, []).append(item.title_id)

    print(f"[{utc()}] очередь: {len(items)} пар, источников {len(by_source)}")
    started = time.monotonic()
    achieved = 0
    per_source: dict[str, dict] = {}
    dead_letter: list[dict] = []

    for source_key, title_ids in by_source.items():
        if achieved >= args.target:
            break
        try:
            source = get(source_key)
            adapter = adapter_for(source_key)
        except (KeyError, Exception) as exc:  # noqa: BLE001
            dead_letter.append({"source": source_key, "error": f"{type(exc).__name__}: {exc}"})
            continue
        ingestor = Ingestor(store, source, adapter, dry_run=args.dry_run)
        totals: dict[str, int] = {}
        batch = 25
        for start in range(0, len(title_ids), batch):
            if achieved >= args.target:
                break
            chunk = [registry.get(t) for t in title_ids[start : start + batch]]
            chunk = [t for t in chunk if t is not None]
            if not chunk:
                continue
            try:
                result = ingestor.run(chunk, stage="DAILY")
            except AdapterError as exc:
                dead_letter.append(
                    {"source": source_key, "code": exc.code, "message": exc.message,
                     "retryable": exc.retryable, "hard_circuit": exc.hard_circuit}
                )
                break
            counters = result.counters.as_dict()
            for key, value in counters.items():
                totals[key] = totals.get(key, 0) + value
            # В цель идут только настоящие изменения.
            achieved += counters["inserted"] + counters["updated"]
        per_source[source_key] = totals
        shown = json.dumps({k: v for k, v in totals.items() if v}, ensure_ascii=False)
        print(f"[{utc()}] {source_key}: {shown}")

    # Сводная оценка пересчитывается для тех, у кого источников стало ≥ 2.
    candidates = [
        r["title_id"]
        for r in store.query(
            """SELECT title_id FROM unified_external_current WHERE validation_state='OK'
               GROUP BY title_id HAVING COUNT(*) >= ?""",
            (MIN_SOURCES,),
        )
    ]
    composite_states = {} if args.dry_run else recompute_many(store, candidates)

    report = queue.report()
    coverage = CoverageReporter(store).report(site_slices={"animedia.icu": site_ids})
    payload = {
        "date": utc(),
        "DAILY_TARGET": args.target,
        "DAILY_COMPLETED": achieved,
        "DAILY_PENDING_BACKLOG": report.pending_backlog,
        "DAILY_UNCHANGED_CHECKED": report.unchanged_checked,
        "DAILY_BLOCKED_BY_RATE_LIMIT": report.blocked_by_rate_limit,
        "DAILY_BLOCKED_BY_SECRET": report.blocked_by_secret,
        "DAILY_SHORTFALL_REASON": (
            "" if achieved >= args.target else report.shortfall_reason
        ),
        "mode": report.mode,
        "per_source": per_source,
        "dead_letter": dead_letter,
        "composite_states": composite_states,
        "coverage_percent_catalog": coverage["slices"]["catalog"]["coverage_percent"],
        "coverage_percent_animedia": coverage["slices"]
        .get("animedia.icu", {})
        .get("coverage_percent"),
        "coverage_percent_catalog_before": coverage_before,
        "elapsed_seconds": round(time.monotonic() - started, 1),
        "stale_alert": (
            f"нет новых результатов дольше {STALE_ALERT_HOURS} часов"
            if achieved == 0 and report.pending_backlog > 0
            else ""
        ),

    }
    if args.evidence:
        Path(args.evidence).parent.mkdir(parents=True, exist_ok=True)
        Path(args.evidence).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    print(json.dumps(payload, ensure_ascii=False))
    store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
