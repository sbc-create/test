"""CLI: python -m factory ratings <subcommand>.

На ЭТАПЕ 1 все команды по умолчанию без production mutations.
Запись требует явного --apply.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from factory.ratings.adapters.animemedia import AnimeMediaAdapter
from factory.ratings.adapters.shikimori import ShikimoriGraphQLAdapter
from factory.ratings.catalog import iter_mal_mapped, load_catalog_json, titles_from_catalog_items
from factory.ratings.config import RatingsConfig
from factory.ratings.gateway import RatingGateway
from factory.ratings.ingestion import IngestionEngine
from factory.ratings.queue import plan_queue
from factory.ratings.report import estimate_backlog_completion, write_run_report
from factory.ratings.snapshot import atomic_publish_candidate, build_snapshot, validate_snapshot
from factory.ratings.source_registry import seed_registry
from factory.ratings.store import RatingsStore


def _cfg(args) -> RatingsConfig:
    db = Path(args.db) if getattr(args, "db", None) else None
    ev = Path(args.evidence) if getattr(args, "evidence", None) else None
    return RatingsConfig.from_env(db_path=db, evidence_dir=ev)


def _store(cfg: RatingsConfig) -> RatingsStore:
    assert cfg.db_path is not None
    store = RatingsStore(cfg.db_path)
    seed_registry(store)
    return store


def _adapter(source: str, cfg: RatingsConfig, *, live: bool = False):
    if source == "shikimori":
        return ShikimoriGraphQLAdapter(
            url=cfg.shikimori_graphql_url,
            user_agent=cfg.user_agent,
            batch_size=cfg.batch_size,
            rate_limiter=__import__(
                "factory.ratings.rate_limit", fromlist=["RateLimiter"]
            ).RateLimiter(max_rps=cfg.max_rps, max_per_minute=cfg.max_requests_per_minute),
        )
    if source == "animemedia":
        return AnimeMediaAdapter()
    raise SystemExit(f"unknown source: {source}")


def cmd_sources(args) -> int:
    cfg = _cfg(args)
    store = _store(cfg)
    rows = store.list_sources()
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


def cmd_plan(args) -> int:
    cfg = _cfg(args)
    store = _store(cfg)
    limit = int(args.limit or cfg.daily_success_target)
    # Cap planning by candidate cap
    titles = []
    if args.catalog:
        titles = load_catalog_json(Path(args.catalog), limit=None)
        if args.source == "shikimori":
            titles = list(iter_mal_mapped(titles))
    elif args.fixture:
        data = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
        titles = titles_from_catalog_items(data if isinstance(data, list) else data.get("items") or [])
    else:
        print("нужен --catalog или --fixture", file=sys.stderr)
        return 2
    # Temporary raise candidate selection window for plan metric, still capped
    plan = plan_queue(
        store,
        titles,
        source_key=args.source,
        config=cfg,
    )
    # If user asked limit specifically for planned display
    plan["requested_limit"] = limit
    plan["planned_candidates"] = min(plan["planned_candidates"], max(limit, cfg.daily_candidate_cap))
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    if cfg.evidence_dir:
        cfg.evidence_dir.mkdir(parents=True, exist_ok=True)
        (cfg.evidence_dir / "plan-latest.json").write_text(
            json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return 0


def cmd_ingest(args) -> int:
    cfg = _cfg(args)
    store = _store(cfg)
    apply = bool(args.apply)
    dry_run = not apply
    adapter = _adapter(args.source, cfg, live=bool(getattr(args, "live", False)))
    engine = IngestionEngine(store, adapter, cfg)
    metrics = engine.ingest(
        source_key=args.source,
        limit=int(args.limit or cfg.initial_canary_limit),
        dry_run=dry_run,
        apply=apply,
        run_id=args.run_id,
        idempotency_key=args.idempotency_key,
    )
    paths = write_run_report(metrics, cfg.evidence_dir or Path("."), extra={
        "stage": 1,
        "apply": apply,
    })
    out = metrics.as_dict()
    out["report_paths"] = paths
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if metrics.failed == 0 or metrics.attempted > 0 else 1


def cmd_resume(args) -> int:
    cfg = _cfg(args)
    store = _store(cfg)
    run = store.get_run(args.run_id)
    if not run:
        print(json.dumps({"error": "run_not_found", "run_id": args.run_id}))
        return 2
    adapter = _adapter(run["source_key"], cfg)
    engine = IngestionEngine(store, adapter, cfg)
    metrics = engine.ingest(
        source_key=run["source_key"],
        limit=int(args.limit or cfg.initial_canary_limit),
        dry_run=bool(run["dry_run"]) and not args.apply,
        apply=bool(args.apply),
        run_id=args.run_id,
        idempotency_key=run["idempotency_key"],
        resume=True,
    )
    print(json.dumps(metrics.as_dict(), ensure_ascii=False, indent=2))
    return 0


def cmd_conflicts(args) -> int:
    cfg = _cfg(args)
    store = _store(cfg)
    rows = store.list_conflicts()
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


def cmd_coverage(args) -> int:
    cfg = _cfg(args)
    store = _store(cfg)
    stats = store.coverage_stats(args.source)
    breakdown = store.queue_priority_breakdown(args.source) if args.source else []
    print(json.dumps({"coverage": stats, "queue_breakdown": breakdown}, ensure_ascii=False, indent=2))
    return 0


def cmd_snapshot_build(args) -> int:
    cfg = _cfg(args)
    store = _store(cfg)
    body = build_snapshot(store, primary_source=args.primary or "shikimori")
    errors = validate_snapshot(body)
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, ensure_ascii=False, indent=2))
        return 1
    output = Path(args.output) if args.output else (cfg.evidence_dir / "ratings_snapshot_v1.candidate.json")
    # Stage 1: only evidence area
    if "evidence" not in str(output) and not args.allow_non_evidence:
        output = (cfg.evidence_dir or Path("artifacts/evidence/ratings-ingestion-01")) / "ratings_snapshot_v1.candidate.json"
    if args.apply:
        result = atomic_publish_candidate(body, output)
    else:
        # dry-run write still allowed inside evidence as candidate draft
        output.parent.mkdir(parents=True, exist_ok=True)
        draft = output.with_suffix(output.suffix + ".dry-run.json")
        draft.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
        result = {"path": str(draft), "digest": body["snapshot_sha256"], "dry_run": True, "title_count": body["title_count"]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_status(args) -> int:
    cfg = _cfg(args)
    store = _store(cfg)
    sources = store.list_sources()
    payload = {
        "db": str(cfg.db_path),
        "sources": sources,
        "queue": {
            s["source_key"]: {
                "pending": store.queue_size(s["source_key"], "PENDING"),
                "claimed": store.queue_size(s["source_key"], "CLAIMED"),
                "done": store.queue_size(s["source_key"], "DONE"),
            }
            for s in sources
            if s["source_key"] in ("shikimori", "animemedia")
        },
        "coverage": store.coverage_stats(),
        "config": {
            "RATINGS_DAILY_SUCCESS_TARGET": cfg.daily_success_target,
            "RATINGS_DAILY_CANDIDATE_CAP": cfg.daily_candidate_cap,
            "RATINGS_INITIAL_CANARY_LIMIT": cfg.initial_canary_limit,
            "RATINGS_BATCH_SIZE": cfg.batch_size,
            "RATINGS_MAX_RPS": cfg.max_rps,
            "RATINGS_MAX_REQUESTS_PER_MINUTE": cfg.max_requests_per_minute,
        },
        "production_mutations": 0,
        "scheduler_active": 0,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_probe(args) -> int:
    """Bounded read-only Shikimori contract probe."""
    cfg = _cfg(args)
    adapter = _adapter("shikimori", cfg, live=True)
    try:
        result = adapter.check_schema()
        result["ok"] = True
        if cfg.evidence_dir:
            cfg.evidence_dir.mkdir(parents=True, exist_ok=True)
            (cfg.evidence_dir / "shikimori-contract-probe.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001
        payload = {"ok": False, "error": str(exc), "headers_redacted": getattr(adapter, "last_request_headers_redacted", {})}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1


ACTIONS = {
    "sources": cmd_sources,
    "plan": cmd_plan,
    "ingest": cmd_ingest,
    "resume": cmd_resume,
    "conflicts": cmd_conflicts,
    "coverage": cmd_coverage,
    "snapshot": cmd_snapshot_build,  # ratings snapshot build
    "status": cmd_status,
    "probe": cmd_probe,
}


def run(args) -> int:
    action = args.ratings_action
    if action == "snapshot":
        # nested: ratings snapshot build
        if getattr(args, "snapshot_action", None) and args.snapshot_action != "build":
            print("supported: ratings snapshot build", file=sys.stderr)
            return 2
        return cmd_snapshot_build(args)
    return ACTIONS[action](args)


def register(subparsers) -> None:
    parser = subparsers.add_parser("ratings", help="централизованный ratings ingestion")
    parser.add_argument(
        "ratings_action",
        choices=[
            "sources",
            "plan",
            "ingest",
            "resume",
            "conflicts",
            "coverage",
            "snapshot",
            "status",
            "probe",
        ],
    )
    parser.add_argument("snapshot_action", nargs="?", default="build", help="для snapshot: build")
    parser.add_argument("--source", default="shikimori")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--apply", action="store_true", help="явная запись (иначе dry-run)")
    parser.add_argument("--run-id")
    parser.add_argument("--idempotency-key")
    parser.add_argument("--catalog", help="путь к catalog JSON (read-only)")
    parser.add_argument("--fixture", help="путь к fixture JSON")
    parser.add_argument("--output", help="путь candidate snapshot (evidence)")
    parser.add_argument("--primary", default="shikimori")
    parser.add_argument("--db", help="изолированная SQLite (не production)")
    parser.add_argument("--evidence", help="каталог evidence")
    parser.add_argument("--allow-non-evidence", action="store_true")
    parser.add_argument("--live", action="store_true", help="разрешить live probe")
    parser.set_defaults(func=run)
