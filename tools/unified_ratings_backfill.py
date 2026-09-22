#!/usr/bin/env python3
"""Полный первичный backfill по всему каноническому каталогу.

Идёт по произведениям, а не по фиксированному числу записей. Порядок
очереди задан владельцем: сначала произведения площадки-канарейки, затем
остальной каталог — чтобы покрытие росло там, где его первым увидят.

Состояние пишется в файл прогресса после каждого пакета. Остановка на
любом пакете не теряет сделанное: следующий запуск продолжает с
последнего подтверждённого места, а уже собранные и не изменившиеся
значения не скачиваются повторно — их отсекает ``content_hash``.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from factory.ratings.adapters.base import AdapterError  # noqa: E402
from factory.unified_ratings.adapters import build_adapter  # noqa: E402
from factory.unified_ratings.adapters.provider_feed import ProviderFeedAdapter  # noqa: E402
from factory.unified_ratings.coverage import load_site_title_ids  # noqa: E402
from factory.unified_ratings.ingestion import ID_SPACE_BY_SOURCE, Ingestor  # noqa: E402
from factory.unified_ratings.sources import get  # noqa: E402
from factory.unified_ratings.store import UnifiedStore  # noqa: E402
from factory.unified_ratings.titles import TitleRegistry, load_catalog_items  # noqa: E402

CATALOG = "/srv/site-factory/repo/var/lords/lords/catalog-cache/lords-01.json"
SITE_DETAILS = "/srv/lords/.frontend/animedia-01-details.json"

#: Размер пакета обращения к источнику. Ниже лимитов, объявленных источником.
FETCH_BATCH = {
    "anilist": 25,
    "kitsu": 20,
    "shikimori": 50,
    "provider_feed_imdb": 1000,
    "provider_feed_kinopoisk": 1000,
}


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Progress:
    """Персистентный checkpoint. Возобновление — не повтор с нуля."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.data = {}
        if path.is_file():
            self.data = json.loads(path.read_text(encoding="utf-8"))

    def done_for(self, source: str) -> set[str]:
        return set(self.data.get(source, {}).get("completed_title_ids", []))

    def record(self, source: str, title_ids: list[str], counters: dict) -> None:
        # Файл перечитывается перед каждой записью и сливается с тем, что
        # в нём уже есть. Иначе два одновременных прохода по разным
        # источникам затирают прогресс друг друга: каждый держит свою
        # копию всего файла и пишет её целиком.
        on_disk = {}
        if self.path.is_file():
            with contextlib.suppress(json.JSONDecodeError, OSError):
                on_disk = json.loads(self.path.read_text(encoding="utf-8"))
        for other_source, other in on_disk.items():
            if other_source == source:
                continue
            mine = self.data.setdefault(
                other_source, {"completed_title_ids": [], "counters": {}, "updated_at": ""}
            )
            known = set(mine["completed_title_ids"])
            mine["completed_title_ids"].extend(
                t for t in other.get("completed_title_ids", []) if t not in known
            )
            for key, value in (other.get("counters") or {}).items():
                mine["counters"][key] = max(mine["counters"].get(key, 0), value)

        entry = self.data.setdefault(
            source, {"completed_title_ids": [], "counters": {}, "updated_at": ""}
        )
        entry["completed_title_ids"].extend(title_ids)
        for key, value in counters.items():
            entry["counters"][key] = entry["counters"].get(key, 0) + value
        entry["updated_at"] = utc()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    def summary(self) -> dict:
        return {
            source: {
                "completed_titles": len(entry["completed_title_ids"]),
                "counters": entry["counters"],
                "updated_at": entry["updated_at"],
            }
            for source, entry in self.data.items()
        }


def ordered_titles(registry: TitleRegistry, store: UnifiedStore, source: str, site_ids: set[str]):
    """Очередь произведений: сначала площадка-канарейка, затем остальные."""
    id_space = ID_SPACE_BY_SOURCE.get(source, "")
    candidates = registry.with_external_id(id_space)
    quarantined = {
        r["title_id"]
        for r in store.query(
            "SELECT title_id FROM unified_source_links WHERE source_key=?"
            " AND status IN ('conflict','pending','rejected')",
            (source,),
        )
    }
    site, rest = [], []
    for title in candidates:
        if title.title_id in quarantined:
            continue
        (site if title.title_id in site_ids else rest).append(title)
    return site + rest


def feed_items(field: str) -> dict:
    out = {}
    for item in load_catalog_items(CATALOG):
        ext = (item.get("external_ids") or {}).get(field)
        if ext:
            out[str(ext)] = item
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--progress", required=True)
    parser.add_argument("--max-titles", type=int, default=0, help="0 = весь каталог")
    parser.add_argument("--evidence", default="")
    args = parser.parse_args()

    store = UnifiedStore(args.db, apply_migration=False)
    registry = TitleRegistry(store)
    source = get(args.source)
    progress = Progress(Path(args.progress))

    site_ids = set()
    if Path(SITE_DETAILS).is_file():
        site_ids = load_site_title_ids(SITE_DETAILS)

    if args.source.startswith("provider_feed"):
        field = "imdb" if args.source.endswith("imdb") else "kinopoisk"
        adapter = ProviderFeedAdapter(args.source, feed_items(field))
    else:
        adapter = build_adapter(args.source)

    titles = ordered_titles(registry, store, args.source, site_ids)
    already = progress.done_for(args.source)
    titles = [t for t in titles if t.title_id not in already]
    if args.max_titles:
        titles = titles[: args.max_titles]

    batch = FETCH_BATCH.get(args.source, 25)
    ingestor = Ingestor(store, source, adapter, dry_run=False, write_batch_size=250)

    totals = {}
    started = time.monotonic()
    processed = 0
    print(f"[{utc()}] {args.source}: в очереди {len(titles)} произведений "
          f"(площадка-канарейка первой), пакет {batch}")

    for start in range(0, len(titles), batch):
        chunk = titles[start : start + batch]
        try:
            result = ingestor.run(chunk, stage="BACKFILL")
        except AdapterError as exc:
            print(f"[{utc()}] ОСТАНОВ: {exc.code}: {exc.message}")
            print("  прогресс сохранён; возобновление продолжит с этого места")
            break
        counters = result.counters.as_dict()
        for key, value in counters.items():
            totals[key] = totals.get(key, 0) + value
        progress.record(args.source, [t.title_id for t in chunk], counters)
        processed += len(chunk)
        if (start // batch) % 10 == 0 or start + batch >= len(titles):
            rate = processed / max(1e-6, time.monotonic() - started)
            remaining = len(titles) - processed
            eta = remaining / rate if rate else 0
            print(f"[{utc()}] {args.source}: {processed}/{len(titles)} "
                  f"({rate:.1f}/с, осталось ~{eta/60:.1f} мин) "
                  f"inserted={totals.get('inserted',0)} updated={totals.get('updated',0)} "
                  f"unchanged={totals.get('unchanged',0)} pending={totals.get('pending_match',0)} "
                  f"not_found={totals.get('not_found',0)} failed={totals.get('failed',0)}")

    elapsed = time.monotonic() - started
    report = {
        "source": args.source,
        "finished_at": utc(),
        "titles_queued": len(titles),
        "titles_processed": processed,
        "elapsed_seconds": round(elapsed, 1),
        "counters": totals,
        "progress_file": str(args.progress),
    }
    if args.evidence:
        Path(args.evidence).parent.mkdir(parents=True, exist_ok=True)
        Path(args.evidence).write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    print(json.dumps(report, ensure_ascii=False))
    store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
