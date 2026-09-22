#!/usr/bin/env python3
"""Сбор AMD Online: онгоинги, затем остальной каталог из sitemap.

Один запрос в секунду, checkpoint после каждой страницы. Остановка в
любой момент не теряет собранное, а повторный запуск не скачивает уже
обработанные адреса заново.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from factory.unified_ratings.adapters.amd_online import AmdOnlineAdapter  # noqa: E402
from factory.unified_ratings.amd_ingest import AmdIngestor, AmdRunCounters, TitleIndex  # noqa: E402
from factory.unified_ratings.store import UnifiedStore  # noqa: E402
from factory.unified_ratings.titles import TitleRegistry  # noqa: E402

MIN_FREE_MB = 1024


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_progress(path: Path) -> dict:
    if not path.is_file():
        return {"done": [], "counters": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        print("checkpoint повреждён; продолжаем с пустого")
        return {"done": [], "counters": {}}


def save_progress(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--progress", required=True)
    parser.add_argument("--evidence", default="")
    parser.add_argument("--limit", type=int, default=0, help="0 = весь sitemap")
    parser.add_argument("--ongoing-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    store = UnifiedStore(args.db, apply_migration=False)
    print(f"[{utc()}] индекс каталога…")
    index = TitleIndex.build(TitleRegistry(store))
    print(f"[{utc()}]   ключей названий: {len(index.by_name)}")

    adapter = AmdOnlineAdapter()
    ingestor = AmdIngestor(store, adapter, dry_run=args.dry_run)

    discovery = ingestor.discover(include_catalog=not args.ongoing_only)
    urls = discovery["ordered_urls"]
    section = discovery["section"]
    print(f"[{utc()}] онгоингов с первой страницы: {len(section['first_page_urls'])};"
          f" пагинация заявлена {section['max_page_advertised']} страниц,"
          f" скачано: {section['pagination_fetched']} ({section['pagination_blocked_by']})")
    print(f"[{utc()}] адресов из sitemap: {discovery['sitemap_urls']};"
          f" всего в очереди: {len(urls)}")

    progress = load_progress(Path(args.progress))
    done = set(progress["done"])
    todo = [u for u in urls if u not in done]
    if args.limit:
        todo = todo[: args.limit]
    print(f"[{utc()}] к обработке: {len(todo)} (уже обработано ранее: {len(done)})")

    counters = AmdRunCounters()
    counters.section_pages_fetched = 1
    counters.pagination_pages_advertised = section["max_page_advertised"]
    counters.ongoing_urls_found = len(section["first_page_urls"])
    counters.sitemap_urls_found = discovery["sitemap_urls"]

    started = time.monotonic()

    def on_progress(position: int, total: int, c: AmdRunCounters) -> None:
        rate = position / max(1e-6, time.monotonic() - started)
        eta = (total - position) / rate if rate else 0
        print(f"[{utc()}] {position}/{total} ({rate:.2f}/с, ~{eta/60:.0f} мин) "
              f"оценок={c.with_main_score} совпало={c.exact_matches} "
              f"review={c.sent_to_review} нет в каталоге={c.unmatched} ошибок={c.failed}")
        progress["done"] = sorted(done)
        progress["counters"] = c.as_dict()
        save_progress(Path(args.progress), progress)

    processed: list[str] = []
    batch = 25
    for start in range(0, len(todo), batch):
        free_mb = shutil.disk_usage(Path(args.db).parent).free // 2**20
        if free_mb < MIN_FREE_MB:
            counters.stopped_reason = f"мало места на диске: {free_mb} МБ"
            print(f"[{utc()}] ОСТАНОВ: {counters.stopped_reason}")
            break
        chunk = todo[start : start + batch]
        counters = ingestor.run(chunk, index=index, counters=counters, progress_every=batch,
                                on_progress=None)
        processed.extend(chunk)
        done.update(chunk)
        on_progress(len(processed), len(todo), counters)
        if counters.stopped_reason:
            print(f"[{utc()}] ОСТАНОВ источника: {counters.stopped_reason}")
            break

    progress["done"] = sorted(done)
    progress["counters"] = counters.as_dict()
    save_progress(Path(args.progress), progress)

    report = {
        "finished_at": utc(),
        "dry_run": args.dry_run,
        "section": {k: v for k, v in section.items() if k != "first_page_urls"},
        "ongoing_first_page": len(section["first_page_urls"]),
        "sitemap_urls": discovery["sitemap_urls"],
        "queued": len(todo),
        "processed": len(processed),
        "elapsed_seconds": round(time.monotonic() - started, 1),
        "counters": counters.as_dict(),
        "adapter": {
            "requests": adapter.requests,
            "retries": adapter.retries,
            "kill_switch_active": adapter.kill_switch.active,
            "kill_switch_reason": adapter.kill_switch.reason,
        },
    }
    if args.evidence:
        Path(args.evidence).parent.mkdir(parents=True, exist_ok=True)
        Path(args.evidence).write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    print(json.dumps(report, ensure_ascii=False))
    with contextlib.suppress(Exception):
        store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
