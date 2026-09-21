"""CLI единого модуля оценок.

Ступени запуска разделены командами, а не флагами: ``pilot`` физически не
умеет взять больше двадцати тайтлов, а ``ingest`` отказывается работать,
пока предыдущие ступени не прошли. Разделение флагом позволило бы
запустить массовый сбор опечаткой.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from factory.ratings.adapters.base import AdapterError
from factory.unified_ratings.adapters import build_adapter
from factory.unified_ratings.ingestion import ID_SPACE_BY_SOURCE, Ingestor
from factory.unified_ratings.scheduler import Scheduler, classify
from factory.unified_ratings.sources import REGISTRY, SourceStatus, get
from factory.unified_ratings.store import UnifiedStore
from factory.unified_ratings.titles import (
    CanonicalTitle,
    TitleRegistry,
    from_catalog_item,
    load_catalog_items,
    utc_now,
)

PILOT_MAX = 20
SAMPLE_MAX = 100


def _out(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


# ---------------------------------------------------------------------------
# Этап A — discovery
# ---------------------------------------------------------------------------


def cmd_discover(args: argparse.Namespace) -> int:
    """Read-only проверка доступов, лимитов и контрактов. Сбора нет."""
    report: dict[str, Any] = {"generated_at": utc_now(), "sources": {}}
    for key, source in REGISTRY.items():
        entry: dict[str, Any] = {
            "display_name": source.display_name,
            "ui_label": source.ui_label,
            "access_method": source.access_method.value,
            "status": source.status.value,
            "requires_credential": source.requires_credential,
            "credential_ref": source.credential_ref,
            "documented_rate_limit": source.documented_rate_limit,
            "our_cap": {
                "max_rps": source.max_rps,
                "max_requests_per_minute": source.max_requests_per_minute,
            },
            "legal_basis": source.legal_basis,
            "blocker": source.blocker,
            "scale": {
                "source_scale": source.scale.scale_label,
                "formula": source.scale.formula.value,
                "formula_expression": source.scale.formula_expression,
                "measures": source.scale.measures,
                "raw_field": source.scale.raw_field,
                "vote_count_field": source.scale.vote_count_field,
                "user_count_field": source.scale.user_count_field,
                "verified": source.scale.verified,
                "verified_evidence": source.scale.verified_evidence,
            },
            "not_a_rating": list(source.not_a_rating),
        }
        if args.probe and source.status is SourceStatus.READY:
            try:
                adapter = build_adapter(key)
                entry["health"] = adapter.health()
                entry["capabilities"] = adapter.capabilities().as_dict()
            except AdapterError as exc:
                entry["health"] = {"state": "DEGRADED", "error": str(exc)}
            except Exception as exc:  # noqa: BLE001 — discovery не должен падать целиком
                entry["health"] = {"state": "UNKNOWN", "error": f"{type(exc).__name__}: {exc}"}
        elif args.probe and key == "simkl":
            entry["health"] = build_adapter("simkl").health()
        else:
            entry["health"] = {"state": "UNMEASURED", "reason": "probe не запрашивался"}
        report["sources"][key] = entry
    _out(report)
    return 0


# ---------------------------------------------------------------------------
# каталог
# ---------------------------------------------------------------------------


def _load_titles(args: argparse.Namespace) -> list[CanonicalTitle]:
    items = load_catalog_items(args.catalog)
    titles: list[CanonicalTitle] = []
    for item in items:
        title = from_catalog_item(item)
        if title is None:
            continue
        titles.append(title)
    return titles


def cmd_seed_titles(args: argparse.Namespace) -> int:
    store = UnifiedStore(args.db)
    registry = TitleRegistry(store)
    titles = _load_titles(args)
    if args.limit:
        titles = titles[: args.limit]
    counts = registry.upsert_many(titles)
    _out({"catalog": str(args.catalog), "titles_seen": len(titles), **counts})
    store.close()
    return 0


def _pick_for_ingest(
    store: UnifiedStore, registry: TitleRegistry, source_key: str, *, limit: int
) -> list[CanonicalTitle]:
    """Тайтлы для инкрементального сбора: сначала те, которых ещё нет.

    Брать каждый раз первые N по порядку — не инкрементальный сбор, а
    повторная проверка одного и того же хвоста каталога: счётчик
    ``unchanged`` растёт, а покрытие стоит на месте. Сначала идут тайтлы
    без записи по этому источнику, затем — те, чей срок проверки наступил.
    """
    id_space = ID_SPACE_BY_SOURCE.get(source_key, "")
    known = {
        row["title_id"]
        for row in store.query(
            "SELECT title_id FROM unified_external_current WHERE source_key=?", (source_key,)
        )
    }
    quarantined = {
        row["title_id"]
        for row in store.query(
            "SELECT title_id FROM unified_source_links WHERE source_key=? AND status IN"
            " ('pending','conflict','rejected')",
            (source_key,),
        )
    }
    fresh: list[CanonicalTitle] = []
    for title in registry.with_external_id(id_space):
        if title.title_id in known or title.title_id in quarantined:
            continue
        fresh.append(title)
        if len(fresh) >= limit:
            break
    if len(fresh) >= limit:
        return fresh

    # Добор из тех, кому пора по расписанию.
    due = Scheduler(store).due(source_key=source_key, limit=limit - len(fresh))
    for title_id in due:
        title = registry.get(title_id)
        if title is not None:
            fresh.append(title)
    return fresh


def _pick(
    registry: TitleRegistry, source_key: str, *, limit: int, diverse: bool
) -> list[CanonicalTitle]:
    id_space = ID_SPACE_BY_SOURCE.get(source_key, "")
    candidates = registry.with_external_id(id_space)
    if not diverse:
        return candidates[:limit]
    by_kind: dict[str, list[CanonicalTitle]] = {}
    for title in candidates:
        by_kind.setdefault(title.content_kind or "UNKNOWN", []).append(title)
    picked: list[CanonicalTitle] = []
    index = 0
    while len(picked) < limit and any(index < len(v) for v in by_kind.values()):
        for bucket in by_kind.values():
            if index < len(bucket) and len(picked) < limit:
                picked.append(bucket[index])
        index += 1
    return picked


# ---------------------------------------------------------------------------
# Этапы B / C / D
# ---------------------------------------------------------------------------


def _run_stage(args: argparse.Namespace, *, stage: str, cap: int, diverse: bool) -> int:
    store = UnifiedStore(args.db)
    registry = TitleRegistry(store)
    source = get(args.source)
    limit = min(args.limit or cap, cap)
    titles = (
        _pick_for_ingest(store, registry, args.source, limit=limit)
        if stage == "INGEST"
        else _pick(registry, args.source, limit=limit, diverse=diverse)
    )
    if not titles:
        _out({"stage": stage, "source": args.source, "status": "NOTHING_TO_DO",
              "reason": "в реестре нет тайтлов с нужным внешним идентификатором"})
        store.close()
        return 0
    adapter = build_adapter(args.source)
    ingestor = Ingestor(store, source, adapter, dry_run=args.dry_run)
    result = ingestor.run(titles, stage=stage, cursor_in=args.cursor or "")
    _out(result.as_dict())
    store.close()
    return 0 if result.status in ("OK", "NOTHING_TO_DO") else 1


def cmd_pilot(args: argparse.Namespace) -> int:
    return _run_stage(args, stage="PILOT", cap=PILOT_MAX, diverse=True)


def cmd_sample(args: argparse.Namespace) -> int:
    return _run_stage(args, stage="SAMPLE_100", cap=SAMPLE_MAX, diverse=True)


def cmd_ingest(args: argparse.Namespace) -> int:
    """Инкрементальный сбор. Требует пройденных ступеней B и C."""
    store = UnifiedStore(args.db)
    gates = gate_status(store, args.source)
    if not gates["all_passed"] and not args.force_after_gates:
        _out({"stage": "INGEST", "source": args.source, "status": "GATES_NOT_PASSED",
              "gates": gates})
        store.close()
        return 2
    store.close()
    return _run_stage(args, stage="INGEST", cap=args.limit or 500, diverse=False)


def gate_status(store: UnifiedStore, source_key: str) -> dict[str, Any]:
    """Ворота перед инкрементальным сбором. Считаются по журналу прогонов."""
    runs = {
        row["stage"]: dict(row)
        for row in store.query(
            """SELECT stage, status, requested, received, inserted, updated, unchanged,
                      pending_match, failed
               FROM unified_import_runs
               WHERE source_key=? AND dry_run=0 ORDER BY started_at""",
            (source_key,),
        )
    }
    pilot = runs.get("PILOT")
    sample = runs.get("SAMPLE_100")
    false_matches = store.count(
        "unified_source_links", "source_key=? AND status='exact' AND confidence < 1.0",
        (source_key,),
    )
    gates = {
        "pilot_passed": bool(pilot and pilot["status"] == "OK"),
        "sample_100_passed": bool(sample and sample["status"] == "OK"),
        "false_automatic_matches": false_matches,
        "migration_applied": store.has_schema(),
    }
    gates["all_passed"] = (
        gates["pilot_passed"]
        and gates["sample_100_passed"]
        and gates["false_automatic_matches"] == 0
        and gates["migration_applied"]
    )
    return gates


def cmd_gates(args: argparse.Namespace) -> int:
    store = UnifiedStore(args.db)
    _out({"source": args.source, **gate_status(store, args.source)})
    store.close()
    return 0


# ---------------------------------------------------------------------------
# расписание и отчёт
# ---------------------------------------------------------------------------


def cmd_schedule(args: argparse.Namespace) -> int:
    store = UnifiedStore(args.db)
    registry = TitleRegistry(store)
    scheduler = Scheduler(store)
    if args.enroll:
        source = get(args.source)
        id_space = ID_SPACE_BY_SOURCE.get(source.source_key, "")
        titles = registry.with_external_id(id_space, limit=args.limit)
        for title in titles:
            scheduler.enroll(title=title, source_key=source.source_key,
                             tier=classify(title))
        _out({"enrolled": len(titles), "source": source.source_key})
    else:
        _out(scheduler.plan())
    store.close()
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    from factory.unified_ratings.report import build_report

    store = UnifiedStore(args.db)
    _out(build_report(store))
    store.close()
    return 0


# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="unified-ratings", description=__doc__)
    parser.add_argument("--db", type=Path, default=None, help="путь к БД (обязателен вне production)")
    sub = parser.add_subparsers(dest="command", required=True)

    discover = sub.add_parser("discover", help="Этап A — read-only проверка источников")
    discover.add_argument("--probe", action="store_true", help="выполнить один read-only запрос")
    discover.set_defaults(func=cmd_discover)

    seed = sub.add_parser("seed-titles", help="загрузить канонические тайтлы из каталога")
    seed.add_argument("--catalog", type=Path, required=True)
    seed.add_argument("--limit", type=int, default=0)
    seed.set_defaults(func=cmd_seed_titles)

    for name, func, helptext in (
        ("pilot", cmd_pilot, f"Этап B — не более {PILOT_MAX} тайтлов"),
        ("sample", cmd_sample, f"Этап C — не более {SAMPLE_MAX} тайтлов"),
        ("ingest", cmd_ingest, "Этап D — инкрементальный сбор"),
    ):
        stage = sub.add_parser(name, help=helptext)
        stage.add_argument("--source", required=True, choices=sorted(REGISTRY))
        stage.add_argument("--limit", type=int, default=0)
        stage.add_argument("--cursor", default="")
        stage.add_argument("--dry-run", action="store_true")
        if name == "ingest":
            stage.add_argument(
                "--force-after-gates",
                action="store_true",
                help="запустить, несмотря на непройденные ворота (требует решения оператора)",
            )
        stage.set_defaults(func=func)

    gates = sub.add_parser("gates", help="состояние ворот перед Этапом D")
    gates.add_argument("--source", required=True, choices=sorted(REGISTRY))
    gates.set_defaults(func=cmd_gates)

    schedule = sub.add_parser("schedule", help="план обновлений")
    schedule.add_argument("--source", default="anilist", choices=sorted(REGISTRY))
    schedule.add_argument("--enroll", action="store_true")
    schedule.add_argument("--limit", type=int, default=None)
    schedule.set_defaults(func=cmd_schedule)

    report = sub.add_parser("report", help="сводный отчёт модуля")
    report.set_defaults(func=cmd_report)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
