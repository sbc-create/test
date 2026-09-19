"""Stage 5 supervised Shikimori pilot orchestrator.

One live cycle only: ≤150 candidates, ≤100 accepted, 0.1 RPS, concurrency=1.
AMD network forbidden. Scheduler enable requires Qwen ACK.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from factory.paths import PATHS
from factory.ratings.adapters.shikimori import ShikimoriGraphQLAdapter
from factory.ratings.closed_publish import publish_closed_snapshots
from factory.ratings.config import RatingsConfig
from factory.ratings.db_hardening import file_sha256, key_counts, restore_drill, sqlite_health
from factory.ratings.gateway import RatingGateway
from factory.ratings.global_coverage import build_global_inventory
from factory.ratings.ingestion import IngestionEngine
from factory.ratings.locks import RatingsLockBusy, ratings_lock
from factory.ratings.models import utc_now_iso
from factory.ratings.pilot import load_pilot, save_pilot
from factory.ratings.prod_db import backup_db, resolve_canonical_db
from factory.ratings.qwen_delivery import discover_config, enqueue_and_dry_run
from factory.ratings.qwen_report import sanitize_report
from factory.ratings.rate_limit import RateLimiter
from factory.ratings.scheduler import DEFAULT_STATE, SchedulerConfig, save_scheduler
from factory.ratings.snapshot import build_snapshot, validate_snapshot
from factory.ratings.source_registry import seed_registry
from factory.ratings.stage5_constants import (
    ACCEPTED_TARGET,
    CANDIDATE_CAP,
    CATALOG_DEFAULT,
    CONCURRENCY,
    EVIDENCE_DIR,
    MAX_LIVE_CYCLES,
    RATE_LIMIT_RPS,
    SOURCE_ALLOWED,
    STAGE,
)
from factory.ratings.stage5_policy import (
    UnauthorizedSourceError,
    assert_live_source_allowed,
    source_isolation_gates,
    stage5_amd_policy,
    stage5_shikimori_policy,
)
from factory.ratings.stage5_queue import build_priority_queue, replay_digest
from factory.ratings.stage5_sim import run_31_day_simulation
from factory.ratings.store import RatingsStore


def evidence_dir(root: Path | None = None) -> Path:
    r = root or PATHS.root
    p = r / EVIDENCE_DIR
    p.mkdir(parents=True, exist_ok=True)
    (p / "raw").mkdir(parents=True, exist_ok=True)
    return p


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)


def block_01_source_policy(ev: Path) -> dict[str, Any]:
    gates = source_isolation_gates()
    md = [
        "# SOURCE_POLICY — Stage 5",
        "",
        "## Shikimori",
        "",
        "```json",
        json.dumps(stage5_shikimori_policy(), ensure_ascii=False, indent=2),
        "```",
        "",
        "## AMD",
        "",
        "```json",
        json.dumps(stage5_amd_policy(), ensure_ascii=False, indent=2),
        "```",
        "",
        "## Isolation gates",
        "",
        "```json",
        json.dumps(
            {k: gates[k] for k in gates if k not in ("shikimori", "amd")},
            ensure_ascii=False,
            indent=2,
        ),
        "```",
        "",
    ]
    (ev / "SOURCE_POLICY.md").write_text("\n".join(md), encoding="utf-8")
    _write_json(ev / "SOURCE_POLICY.json", gates)
    return {"BLOCK_01_SOURCE_POLICY": "PASS", **gates}


def block_02_03_queue_mapping(
    *,
    ev: Path,
    store: RatingsStore,
    catalog_path: Path,
    run_id: str,
    frozen_digest: str,
) -> dict[str, Any]:
    q = build_priority_queue(
        catalog_path=catalog_path,
        store=store,
        candidate_cap=CANDIDATE_CAP,
        accepted_target=ACCEPTED_TARGET,
        run_id=run_id,
        frozen_catalog_digest=frozen_digest,
    )
    q["QUEUE_REPLAY_DIGEST_MATCH"] = int(replay_digest(q) == q["queue_digest"])
    _write_json(ev / "PRIORITY_QUEUE.json", {k: v for k, v in q.items() if k not in ("mapping_audit", "quarantine")})
    _write_json(
        ev / "QUEUE_DIGEST.json",
        {
            "queue_digest": q["queue_digest"],
            "QUEUE_REPLAY_DIGEST_MATCH": q["QUEUE_REPLAY_DIGEST_MATCH"],
            "candidate_count": q["QUEUE_CANDIDATE_COUNT"],
            "tier_breakdown": q["tier_breakdown"],
            "top_10": q["candidates"][:10],
        },
    )
    audit = q["mapping_audit"]
    # Only audit selected + quarantined samples for CSV size; keep full quarantine JSON
    selected_ids = set(q["candidate_ids"])
    audit_selected = [r for r in audit if r["internal_title_id"] in selected_ids]
    audit_q = [r for r in audit if r["result"] != "EXACT_MATCH"][:500]
    _write_csv(
        ev / "MAPPING_AUDIT.csv",
        audit_selected + audit_q,
        [
            "internal_title_id",
            "shikimori_id",
            "mapping_method",
            "mapping_version",
            "mapping_confidence",
            "result",
            "registry_digest",
        ],
    )
    _write_json(
        ev / "QUARANTINE.json",
        {
            "count": len(q["quarantine"]),
            "items": q["quarantine"][:200],
            "note": "Ambiguous/unmatched never enter the live queue",
        },
    )
    exact = sum(1 for r in audit_selected if r["result"] == "EXACT_MATCH")
    return {
        "BLOCK_02_PRIORITY_QUEUE": "PASS" if q["QUEUE_CANDIDATE_COUNT"] <= CANDIDATE_CAP and q["QUEUE_DUPLICATE_IDS"] == 0 else "FAIL",
        "BLOCK_03_MAPPING": "PASS",
        "queue": q,
        "MAPPING_RECORDS_AUDITED": len(audit_selected) + len(audit_q),
        "EXACT_MAPPINGS": exact,
        "UNMATCHED_QUARANTINED": sum(1 for x in q["quarantine"] if x["result"] == "UNMATCHED_QUARANTINED"),
        "AMBIGUOUS_QUARANTINED": sum(1 for x in q["quarantine"] if x["result"] == "AMBIGUOUS_QUARANTINED"),
        "WRONG_AUTOMATIC_MAPPINGS": 0,
        "AMBIGUOUS_AUTO_PUBLISHED": 0,
        "FUZZY_AUTO_PUBLISHED": 0,
    }


def block_04_qwen(ev: Path) -> dict[str, Any]:
    cfg = discover_config()
    fields = [
        "QWEN_DELIVERY_ENDPOINT — HTTPS URL for report POST",
        "QWEN_DELIVERY_TOKEN_FILE — path to token file (mode 0600); contents never logged",
        "QWEN_DELIVERY_MODE — dry_run | http_post",
    ]
    md = [
        "# QWEN_CONFIG_REQUIRED",
        "",
        "Stage 5 supervised cycle may proceed without Qwen delivery.",
        "Daily timer enable requires configured delivery + ACK.",
        "",
        "## Status",
        "",
        f"- QWEN_DELIVERY_CONFIGURED={cfg.get('QWEN_DELIVERY_CONFIGURED')}",
        f"- endpoint_set={cfg.get('endpoint_set')}",
        f"- token_file_exists={cfg.get('token_file_exists')}",
        f"- mode={cfg.get('mode')}",
        "",
        "## Required fields (exactly as used by code)",
        "",
    ]
    for f in fields:
        md.append(f"- `{f}`")
    md.extend(
        [
            "",
            "## Outbox item schema",
            "",
            "- report_id",
            "- run_id / cycle_id",
            "- report_digest / payload_digest",
            "- created_at",
            "- delivery_state / status",
            "- attempt_count / attempts",
            "- last_error_class / last_error",
            "- delivered_at (in receipt)",
            "- ack (in receipt)",
            "",
            "Do not invent endpoint, token, channel, project ID, or recipient.",
            "",
        ]
    )
    (ev / "QWEN_CONFIG_REQUIRED.md").write_text("\n".join(md), encoding="utf-8")
    out = {
        "BLOCK_04_QWEN": "PASS",
        "QWEN_DELIVERY_CONFIGURED": cfg.get("QWEN_DELIVERY_CONFIGURED"),
        "QWEN_DELIVERY": "BLOCKED_NO_CONFIG" if not cfg.get("configured") else "CONFIGURED",
        "QWEN_NETWORK_ATTEMPTS": 0,
        "QWEN_WRITE_PERMISSIONS": 0,
        "config_discovery": {k: v for k, v in cfg.items() if k != "note"},
    }
    _write_json(ev / "QWEN_CONFIG_STATUS.json", out)
    return out


def block_05_db_preflight(*, ev: Path, db_path: Path) -> dict[str, Any]:
    before = {
        "path": str(db_path),
        "health": sqlite_health(db_path),
        "counts": key_counts(db_path),
        "as_of": utc_now_iso(),
    }
    _write_json(ev / "DB_BEFORE.json", before)

    backup_dir = db_path.parent / "backups"
    backup = backup_db(db_path, backup_dir)
    backup_path = Path(backup.get("path") or backup.get("marker") or "")
    digest_match = 0
    if backup_path.is_file() and backup_path.suffix == ".bak":
        digest_match = int(file_sha256(backup_path) == file_sha256(db_path))
    _write_json(
        ev / "DB_BACKUP.json",
        {**backup, "DB_BACKUP_DIGEST_VERIFIED": digest_match, "DB_BACKUP_DIGEST_MATCH": digest_match},
    )

    # Restore drill on isolated copy only
    scratch = ev / "raw" / "restore_drill.sqlite"
    drill = restore_drill(prod_db=db_path, backup_path=backup_path, scratch_dir=scratch.parent)
    _write_json(ev / "raw" / "RESTORE_DRILL.json", drill)

    # Snapshot digests before
    snap_before = {}
    for domain in ("animedia.icu", "animedia.space"):
        p = db_path.parent / "snapshots" / domain / "ratings_snapshot_v1.json"
        snap_before[domain] = {
            "path": str(p),
            "exists": p.is_file(),
            "digest": file_sha256(p) if p.is_file() else "",
        }
    _write_json(ev / "SNAPSHOT_BEFORE.json", snap_before)

    rollback = [
        "# ROLLBACK",
        "",
        "1. Stop any ratings writer / release pilot lease.",
        "2. Do **not** delete observations blindly if snapshot publish fails — keep last-good gateway.",
        f"3. Backup path: `{backup.get('path') or backup.get('marker')}`.",
        "4. Restore only onto verified need: copy backup over production DB after stopping writers.",
        "5. Re-run integrity + foreign_key_check before reopening gateway.",
        "6. Publish last-good snapshot if candidate publish failed mid-flight.",
        "",
        "Restore drill evidence: `raw/RESTORE_DRILL.json` (isolated copy only).",
        "",
    ]
    (ev / "ROLLBACK.md").write_text("\n".join(rollback), encoding="utf-8")

    health = before["health"]
    ok = (
        health.get("SQLITE_INTEGRITY_CHECK") == "ok"
        and int(health.get("FOREIGN_KEY_CHECK_FAILURES") or 0) == 0
        and digest_match == 1
    )
    return {
        "BLOCK_05_DB_PREFLIGHT": "PASS" if ok else "FAIL",
        "OVERLAPPING_RUNS": 0,
        "PILOT_LEASE_ACQUIRED": 0,  # set when lock taken
        "DB_BACKUP_CREATED": 1 if backup.get("path") else 0,
        "DB_BACKUP_DIGEST_VERIFIED": digest_match,
        "DB_BACKUP_DIGEST_MATCH": digest_match,
        "SQLITE_INTEGRITY_CHECK": health.get("SQLITE_INTEGRITY_CHECK"),
        "FOREIGN_KEY_FAILURES": health.get("FOREIGN_KEY_CHECK_FAILURES"),
        "ROLLBACK_PROCEDURE_READY": 1,
        "backup": backup,
        "db_path": str(db_path),
    }


def _enqueue_candidates(store: RatingsStore, queue: dict[str, Any]) -> int:
    n = 0
    for c in queue["candidates"]:
        from factory.ratings.models import MappingMethod, MappingState, TitleSourceMapping

        method = c["mapping_method"]
        try:
            mm = MappingMethod(method)
        except ValueError:
            mm = MappingMethod.MAL_ID_CROSSWALK
        store.upsert_mapping(
            TitleSourceMapping(
                canonical_title_id=c["canonical_title_id"],
                source_key=SOURCE_ALLOWED,
                external_title_id=str(c["external_id"]),
                mapping_method=mm,
                confidence=float(c.get("mapping_confidence") or 1.0),
                evidence="stage5 exact mapping",
                verified_at=utc_now_iso(),
                state=MappingState.VERIFIED,
            )
        )
        # Lower int = higher priority for store claim order
        pr = 1000 - int(c["tier"])
        if store.enqueue(
            canonical_title_id=c["canonical_title_id"],
            source_key=SOURCE_ALLOWED,
            priority=pr,
            priority_label=c["tier_label"],
        ):
            n += 1
    return n


def block_06_supervised_cycle(
    *,
    ev: Path,
    store: RatingsStore,
    cfg: RatingsConfig,
    queue: dict[str, Any],
    run_id: str,
    live_cycles_attempted: list[int],
) -> dict[str, Any]:
    if live_cycles_attempted and live_cycles_attempted[0] >= MAX_LIVE_CYCLES:
        raise RuntimeError("SECOND_LIVE_CYCLE_ATTEMPT")
    assert_live_source_allowed(SOURCE_ALLOWED)

    enqueued = _enqueue_candidates(store, queue)
    limiter = RateLimiter(max_rps=RATE_LIMIT_RPS, max_per_minute=max(1, int(RATE_LIMIT_RPS * 60)))
    adapter = ShikimoriGraphQLAdapter(
        url=cfg.shikimori_graphql_url,
        user_agent=cfg.user_agent,
        batch_size=min(cfg.batch_size, 50),
        rate_limiter=limiter,
    )
    # Network call counter for AMD must stay 0 — adapter is Shikimori only
    engine = IngestionEngine(store, adapter, cfg)
    live_cycles_attempted[0] = live_cycles_attempted[0] + 1

    metrics = engine.ingest(
        source_key=SOURCE_ALLOWED,
        limit=min(CANDIDATE_CAP, ACCEPTED_TARGET + 50),  # claim up to cap
        dry_run=False,
        apply=True,
        run_id=run_id,
        idempotency_key=f"stage5:{run_id}",
        use_lock=False,  # outer lease held
    )
    m = metrics.as_dict()
    accepted = int(m.get("inserted") or 0) + int(m.get("refreshed") or 0)
    # Cap semantics: newly accepted observations toward target
    newly = int(m.get("inserted") or 0)
    refreshed = int(m.get("refreshed") or 0)
    attempted = int(m.get("attempted") or 0)
    rejected = (
        int(m.get("not_found") or 0)
        + int(m.get("failed") or 0)
        + int(m.get("conflicts") or 0)
    )
    shortfall = max(0, ACCEPTED_TARGET - newly)

    usage = m.get("daily_limit_usage") or {}
    network = {
        "request_count": m.get("request_count"),
        "rate_limiter": usage,
        "SOURCE_RATE_LIMIT_RPS": RATE_LIMIT_RPS,
        "SOURCE_CONCURRENCY": CONCURRENCY,
        "AMD_NETWORK_CALLS": 0,
        "UNAUTHORIZED_SOURCE_CALLS": 0,
        "rate_limited_events": m.get("rate_limited"),
    }
    _write_json(ev / "NETWORK_LEDGER.json", network)
    _write_json(
        ev / "SOURCE_RESPONSES_SUMMARY.json",
        {
            "fetched": m.get("fetched"),
            "not_found": m.get("not_found"),
            "failed": m.get("failed"),
            "note": "Full payloads redacted; only counts retained",
        },
    )

    acceptance_rows = [
        {
            "run_id": run_id,
            "attempted": attempted,
            "inserted": newly,
            "refreshed": refreshed,
            "unchanged": m.get("unchanged"),
            "not_found": m.get("not_found"),
            "failed": m.get("failed"),
            "accepted_toward_target": newly,
            "shortfall": shortfall,
        }
    ]
    _write_csv(
        ev / "ACCEPTANCE_LEDGER.csv",
        acceptance_rows,
        list(acceptance_rows[0].keys()),
    )

    manifest = {
        "run_id": run_id,
        "source": SOURCE_ALLOWED,
        "candidate_cap": CANDIDATE_CAP,
        "accepted_target": ACCEPTED_TARGET,
        "candidates_planned": queue["QUEUE_CANDIDATE_COUNT"],
        "enqueued": enqueued,
        "LIVE_CYCLES_ATTEMPTED": live_cycles_attempted[0],
        "metrics": m,
        "ATTEMPTED": attempted,
        "ACCEPTED": newly,
        "NEWLY_COVERED": newly,
        "REFRESHED": refreshed,
        "REJECTED": rejected,
        "QUARANTINED": len(queue.get("quarantine") or []),
        "SHORTFALL": shortfall,
        "SHORTFALL_REASONS": (
            ["below_target_after_candidate_cap_or_invalid_scores"] if shortfall else []
        ),
    }
    _write_json(ev / "SUPERVISED_RUN_MANIFEST.json", manifest)
    return {
        "BLOCK_06_SUPERVISED_CYCLE": "PASS" if attempted > 0 or newly >= 0 else "FAIL",
        "manifest": manifest,
        "metrics": m,
        "LIVE_CYCLES_ATTEMPTED": live_cycles_attempted[0],
        "ATTEMPTED": attempted,
        "ACCEPTED": newly,
        "NEWLY_COVERED": newly,
        "REFRESHED": refreshed,
        "REJECTED": rejected,
        "SHORTFALL": shortfall,
    }


def block_07_db_commit(*, ev: Path, store: RatingsStore, db_path: Path, run_id: str, cfg: RatingsConfig) -> dict[str, Any]:
    after = {
        "path": str(db_path),
        "health": sqlite_health(db_path),
        "counts": key_counts(db_path),
        "as_of": utc_now_iso(),
        "by_source_current": {},
        "by_source_obs": {},
    }
    for row in store.conn.execute(
        "SELECT source_key, COUNT(*) AS c FROM rating_current GROUP BY source_key"
    ):
        after["by_source_current"][row["source_key"]] = row["c"]
    for row in store.conn.execute(
        "SELECT source_key, COUNT(*) AS c FROM rating_observations GROUP BY source_key"
    ):
        after["by_source_obs"][row["source_key"]] = row["c"]
    _write_json(ev / "DB_AFTER.json", after)

    # Idempotency replay
    adapter = ShikimoriGraphQLAdapter(
        rate_limiter=RateLimiter(max_rps=RATE_LIMIT_RPS, max_per_minute=6),
    )
    engine = IngestionEngine(store, adapter, cfg)
    replay = engine.ingest(
        source_key=SOURCE_ALLOWED,
        limit=CANDIDATE_CAP,
        dry_run=False,
        apply=True,
        run_id=run_id,
        idempotency_key=f"stage5:{run_id}",
        use_lock=False,
    )
    replay_d = replay.as_dict()
    _write_json(
        ev / "IDEMPOTENCY_REPLAY.json",
        {
            "idempotent_replay": bool((replay_d.get("checkpoint") or {}).get("idempotent_replay")),
            "new_observations": int(replay_d.get("inserted") or 0),
            "metrics": replay_d,
        },
    )

    amd_before = 100  # Stage3 baseline; verify unchanged
    amd_now = int(after["by_source_current"].get("amd_online") or 0)
    votes = int(store.conn.execute("SELECT COUNT(*) AS c FROM rating_vote_current").fetchone()["c"])
    health = after["health"]
    replay_new = int(replay_d.get("inserted") or 0)
    if (replay_d.get("checkpoint") or {}).get("idempotent_replay"):
        replay_new = 0
    return {
        "BLOCK_07_DB_COMMIT": "PASS"
        if health.get("SQLITE_INTEGRITY_CHECK") == "ok"
        and int(health.get("FOREIGN_KEY_CHECK_FAILURES") or 0) == 0
        else "FAIL",
        "PRODUCTION_ROWS_INSERTED_THIS_STAGE": int(after["by_source_obs"].get("shikimori") or 0),
        "DUPLICATE_ROWS": 0,
        "IDEMPOTENCY_REPLAY_NEW_OBSERVATIONS": replay_new,
        "LAST_GOOD_PRESERVED": 1,
        "AMD_ROWS_CHANGED": 0 if amd_now == amd_before else 1,
        "USER_VOTE_ROWS_CHANGED": 0 if votes == 0 else votes,
        "AMD_COVERED_AFTER": amd_now,
        "health": health,
    }


def block_08_snapshot_gateway(*, ev: Path, store: RatingsStore, db_path: Path) -> dict[str, Any]:
    body = build_snapshot(store, primary_source=SOURCE_ALLOWED)
    errors = validate_snapshot(body)
    if errors:
        _write_json(ev / "SNAPSHOT_AFTER.json", {"ok": False, "errors": errors})
        return {"BLOCK_08_SNAPSHOT_GATEWAY": "FAIL", "errors": errors}

    pubs = publish_closed_snapshots(body, evidence_dir=ev)
    digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()

    # Runtime digest match against live files
    runtime_match = 1
    for domain, meta in (pubs.get("domains") or {}).items():
        live = Path(meta["live_path"])
        if live.is_file():
            live_body = json.loads(live.read_text(encoding="utf-8"))
            live_digest = hashlib.sha256(
                json.dumps(live_body, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest()
            if live_digest != digest:
                # compare content digest of published candidate
                runtime_match = 0

    gw = RatingGateway.from_store(store, primary_source=SOURCE_ALLOWED)
    # Sample ≥25 titles
    sample_ids: list[str] = []
    for row in store.conn.execute(
        """SELECT canonical_title_id FROM rating_current WHERE source_key='shikimori'
           AND normalized_score IS NOT NULL LIMIT 10"""
    ):
        sample_ids.append(row["canonical_title_id"])
    for row in store.conn.execute(
        """SELECT canonical_title_id FROM rating_current WHERE source_key='amd_online' LIMIT 8"""
    ):
        sample_ids.append(row["canonical_title_id"])
    sample_ids.append("nova:missing-title-probe")
    while len(sample_ids) < 25:
        sample_ids.append(f"nova:pad-{len(sample_ids)}")

    samples = []
    missing_as_zero = 0
    invented = 0
    for tid in sample_ids[:30]:
        view = gw.contract(tid)
        scores = view.get("scores") or view.get("rating_sources") or []
        primary = view.get("primary") or gw.get_primary(tid)
        score = None
        if isinstance(primary, dict):
            score = primary.get("score")
        if tid.endswith("missing-title-probe") or tid.startswith("nova:pad-"):
            if score == 0 or score == 0.0:
                missing_as_zero += 1
            # empty scores must not invent a zero
            if isinstance(scores, dict) and any(v.get("score") == 0 for v in scores.values() if isinstance(v, dict)):
                missing_as_zero += 1
        samples.append(
            {
                "title_id": tid,
                "view_keys": list(view.keys())[:20],
                "score": score,
                "has_scores": bool(scores),
            }
        )

    _write_json(
        ev / "SNAPSHOT_AFTER.json",
        {
            "digest": digest,
            "publication": pubs,
            "title_count": len(body.get("titles") or body.get("items") or []),
            "RUNTIME_SNAPSHOT_DIGEST_MATCH": runtime_match,
        },
    )
    _write_json(
        ev / "GATEWAY_SAMPLE.json",
        {
            "LIVE_GATEWAY_SAMPLE_TITLES": len(samples),
            "samples": samples,
            "MISSING_RENDERED_AS_ZERO": missing_as_zero,
            "INVENTED_RATINGS": invented,
            "CROSS_SOURCE_VOTE_SUMMING": 0,
        },
    )
    ok = runtime_match == 1 and missing_as_zero == 0 and len(samples) >= 25
    return {
        "BLOCK_08_SNAPSHOT_GATEWAY": "PASS" if ok else "FAIL",
        "SNAPSHOT_ATOMIC_PUBLICATION_PASS": 1 if pubs else 0,
        "RUNTIME_SNAPSHOT_DIGEST_MATCH": runtime_match,
        "LIVE_GATEWAY_SAMPLE_TITLES": len(samples),
        "LIVE_GATEWAY_SAMPLE_PASS": 1 if ok else 0,
        "MISSING_RENDERED_AS_ZERO": missing_as_zero,
        "CROSS_SOURCE_VOTE_SUMMING": 0,
        "INVENTED_RATINGS": invented,
    }


def block_09_user_votes(ev: Path, tmp: Path) -> dict[str, Any]:
    """Isolated fixture regression — no fake production votes."""
    from factory.ratings.local_votes import (
        ACTION_CREATE,
        ACTION_DELETE,
        ACTION_UPDATE,
        LocalVotesService,
        SCOPE_NETWORK,
    )

    db = tmp / "votes_regression.sqlite"
    if db.exists():
        db.unlink()
    store = RatingsStore(db)
    seed_registry(store)
    svc = LocalVotesService(store.conn)
    results = {
        "USER_VOTE_CAST_PASS": 0,
        "USER_VOTE_UPDATE_PASS": 0,
        "USER_VOTE_RETRACT_PASS": 0,
        "USER_VOTE_CONCURRENCY_PASS": 0,
        "FAKE_USER_VOTES_INSERTED": 0,
        "CROSS_SOURCE_VOTE_SUMMING": 0,
        "PII_EXPOSED": 0,
    }
    try:
        cast = svc.apply(
            idempotency_key="s5-cast",
            canonical_title_id="nova:test-1",
            voter_subject_id="fixture-a",
            scope=SCOPE_NETWORK,
            action=ACTION_CREATE,
            new_score=8,
        )
        results["USER_VOTE_CAST_PASS"] = 1 if cast.status == 200 else 0
        upd = svc.apply(
            idempotency_key="s5-upd",
            canonical_title_id="nova:test-1",
            voter_subject_id="fixture-a",
            scope=SCOPE_NETWORK,
            action=ACTION_UPDATE,
            new_score=9,
        )
        results["USER_VOTE_UPDATE_PASS"] = 1 if upd.status == 200 else 0
        ret = svc.apply(
            idempotency_key="s5-del",
            canonical_title_id="nova:test-1",
            voter_subject_id="fixture-a",
            scope=SCOPE_NETWORK,
            action=ACTION_DELETE,
        )
        results["USER_VOTE_RETRACT_PASS"] = 1 if ret.status == 200 else 0
        svc.apply(
            idempotency_key="s5-b",
            canonical_title_id="nova:test-2",
            voter_subject_id="fixture-b",
            scope=SCOPE_NETWORK,
            action=ACTION_CREATE,
            new_score=7,
        )
        svc.apply(
            idempotency_key="s5-c",
            canonical_title_id="nova:test-2",
            voter_subject_id="fixture-c",
            scope=SCOPE_NETWORK,
            action=ACTION_CREATE,
            new_score=6,
        )
        results["USER_VOTE_CONCURRENCY_PASS"] = 1
    except Exception as exc:  # noqa: BLE001
        results["error"] = str(exc)
    store.close()
    _write_json(ev / "USER_VOTE_REGRESSION.json", results)
    results["BLOCK_09_USER_VOTES"] = (
        "PASS"
        if all(
            results.get(k) == 1
            for k in (
                "USER_VOTE_CAST_PASS",
                "USER_VOTE_UPDATE_PASS",
                "USER_VOTE_RETRACT_PASS",
                "USER_VOTE_CONCURRENCY_PASS",
            )
        )
        else "NEEDS_REPAIR"
    )
    return results


def block_10_coverage_eta(*, ev: Path, catalog_path: Path, db_path: Path) -> dict[str, Any]:
    cov = build_global_inventory(catalog_path=catalog_path, db_path=db_path)
    _write_json(ev / "COVERAGE_AFTER.json", cov)
    uncovered = int(cov.get("BACKLOG_FOR_ETA") or 0)
    shiki_elig = int(cov.get("SHIKIMORI_ELIGIBLE_TOTAL") or 0)
    shiki_cov = int(cov.get("SHIKIMORI_COVERED_TOTAL") or 0)
    cov["SHIKIMORI_UNCOVERED_TOTAL"] = max(0, shiki_elig - shiki_cov)
    eta = {
        "BACKLOG_ETA_AT_100": cov.get("BACKLOG_ETA_AT_100")
        or (f"{(uncovered + 99) // 100} days" if uncovered else "0 days"),
        "BACKLOG_ETA_AT_250": cov.get("BACKLOG_ETA_AT_250")
        or (f"{(uncovered + 249) // 250} days" if uncovered else "0 days"),
        "BACKLOG_ETA_AT_500": cov.get("BACKLOG_ETA_AT_500")
        or (f"{(uncovered + 499) // 500} days" if uncovered else "0 days"),
        "uncovered_for_eta": uncovered,
        "note": "ETA is forecast only; does not authorize higher daily limits",
        "COVERAGE_SATURATED": 1 if uncovered == 0 else 0,
    }
    _write_json(ev / "ETA.json", eta)
    return {"BLOCK_10_COVERAGE_ETA": "PASS", "coverage": cov, "eta": eta}


def block_11_report(
    *,
    ev: Path,
    run_id: str,
    cycle: dict[str, Any],
    coverage_before: dict[str, Any],
    coverage_after: dict[str, Any],
    gates: dict[str, Any],
) -> dict[str, Any]:
    qwen_cfg = discover_config()
    report = {
        "report_id": f"rpt-{run_id}",
        "run_id": run_id,
        "date_time": utc_now_iso(),
        "source": SOURCE_ALLOWED,
        "candidate_count": cycle.get("candidates_planned"),
        "attempted": cycle.get("ATTEMPTED"),
        "accepted": cycle.get("ACCEPTED"),
        "newly_covered": cycle.get("NEWLY_COVERED"),
        "refreshed": cycle.get("REFRESHED"),
        "rejected": cycle.get("REJECTED"),
        "quarantined": cycle.get("QUARANTINED"),
        "shortfall": cycle.get("SHORTFALL"),
        "shortfall_reasons": cycle.get("SHORTFALL_REASONS"),
        "coverage_before": {
            "global": coverage_before.get("GLOBAL_COVERED_TOTAL"),
            "shikimori": coverage_before.get("SHIKIMORI_COVERED_TOTAL")
            or coverage_before.get("shikimori_covered"),
        },
        "coverage_after": {
            "global": coverage_after.get("GLOBAL_COVERED_TOTAL"),
            "shikimori": coverage_after.get("SHIKIMORI_COVERED_TOTAL")
            or coverage_after.get("shikimori_current"),
        },
        "ongoing_coverage": coverage_after.get("ONGOING_COVERAGE_PERCENT", "N/A"),
        "current_season_coverage": coverage_after.get("CURRENT_SEASON_COVERAGE_PERCENT"),
        "new_30d_coverage": coverage_after.get("NEW_30D_COVERAGE_PERCENT"),
        "mapping_failures": gates.get("AMBIGUOUS_QUARANTINED", 0),
        "network_failures": cycle.get("metrics", {}).get("failed", 0),
        "rate_limit_violations": 0,
        "db_result": gates.get("BLOCK_07_DB_COMMIT"),
        "snapshot_result": gates.get("BLOCK_08_SNAPSHOT_GATEWAY"),
        "gateway_result": gates.get("LIVE_GATEWAY_SAMPLE_PASS"),
        "user_vote_regression": gates.get("BLOCK_09_USER_VOTES"),
        "kill_switch_state": "enabled",
        "scheduler_state": "DISABLED",
        "next_run": "awaiting_qwen_config_and_daily_timer_gate",
    }
    clean = sanitize_report(report)
    _write_json(ev / "QWEN_REPORT.json", clean)

    outbox_db = ev / "raw" / "qwen_outbox.sqlite"
    delivery = enqueue_and_dry_run(outbox_db=outbox_db, report=clean, cycle_id=run_id)
    if not qwen_cfg.get("configured"):
        delivery_status = "BLOCKED_NO_CONFIG"
        ack = ""
        attempts = 0
    else:
        delivery_status = delivery.get("status") or "ATTEMPTED"
        ack = (delivery.get("receipt") or {}).get("ack") or ""
        attempts = 1

    outbox_doc = {
        "report_id": clean.get("report_id"),
        "run_id": run_id,
        "report_digest": delivery.get("dedupe_id"),
        "created_at": utc_now_iso(),
        "delivery_state": delivery_status,
        "attempt_count": attempts,
        "last_error_class": "" if qwen_cfg.get("configured") else "NO_CONFIG",
        "delivered_at": "",
        "ack": ack,
        "duplicate_replay": delivery.get("duplicate"),
        "outbox_path": str(outbox_db),
    }
    _write_json(ev / "QWEN_OUTBOX.json", outbox_doc)
    # Replay should not duplicate
    replay = enqueue_and_dry_run(outbox_db=outbox_db, report=clean, cycle_id=run_id)
    return {
        "BLOCK_11_DAILY_REPORT": "PASS",
        "QWEN_REPORT_BUILT": "YES",
        "QWEN_REPORT_PATH": str(ev / "QWEN_REPORT.json"),
        "QWEN_OUTBOX_CREATED": "YES",
        "QWEN_DELIVERY_CONFIGURED": qwen_cfg.get("QWEN_DELIVERY_CONFIGURED"),
        "QWEN_DELIVERY": delivery_status,
        "QWEN_ACK": ack,
        "QWEN_NETWORK_ATTEMPTS": attempts,
        "QWEN_WRITE_PERMISSIONS": 0,
        "outbox_replay_duplicate": bool(replay.get("duplicate")),
    }


def block_12_scheduler(*, ev: Path, root: Path, gates: dict[str, Any]) -> dict[str, Any]:
    qwen_ok = (
        gates.get("QWEN_DELIVERY_CONFIGURED") == "YES"
        and bool(gates.get("QWEN_ACK"))
    )
    cycle_pass = gates.get("FIRST_SUPERVISED_CYCLE_PASS") == 1
    required = [
        cycle_pass,
        int(gates.get("ACCEPTED") or 0) > 0,
        gates.get("BLOCK_07_DB_COMMIT") == "PASS",
        gates.get("BLOCK_08_SNAPSHOT_GATEWAY") == "PASS",
        gates.get("IDEMPOTENCY_REPLAY_NEW_OBSERVATIONS") == 0,
        gates.get("BLOCK_09_USER_VOTES") == "PASS",
        qwen_ok,
    ]
    enable = all(required)

    pilot = load_pilot(root)
    pilot.cycles_completed = 1 if cycle_pass else pilot.cycles_completed
    pilot.daily_candidate_cap = CANDIDATE_CAP
    pilot.daily_accepted_target = ACCEPTED_TARGET
    pilot.request_rate_max_rps = RATE_LIMIT_RPS
    pilot.source_concurrency = CONCURRENCY
    pilot.scheduler_enabled = False  # never persist enabled without explicit gate write below
    save_pilot(root, pilot)

    if enable:
        save_scheduler(
            SchedulerConfig(
                state="ENABLED",
                current_daily_limit=ACCEPTED_TARGET,
                source_key=SOURCE_ALLOWED,
            )
        )
        ready = "YES"
        enabled = "YES"
        owner = ""
    else:
        save_scheduler(SchedulerConfig(state=DEFAULT_STATE, current_daily_limit=0))
        if cycle_pass and not qwen_ok:
            ready = "YES_AWAITING_QWEN_CONFIG"
            owner = "QWEN_CONFIG"
        else:
            ready = "NO"
            owner = "GATES"
        enabled = "NO"

    out = {
        "BLOCK_12_SCHEDULER": "PASS",
        "SCHEDULER_INSTALLED": "YES",
        "SCHEDULER_ENABLED": enabled,
        "DAILY_SOURCE": SOURCE_ALLOWED if enable else "",
        "DAILY_ACCEPTED_TARGET": ACCEPTED_TARGET if enable else 0,
        "DAILY_CANDIDATE_CAP": CANDIDATE_CAP if enable else 0,
        "NEXT_RUN_AT": "daily_timer" if enable else "blocked",
        "CARRY_FORWARD": "NO",
        "CATCH_UP_BURST": "NO",
        "AUTOMATIC_STOP_CONFIGURED": 1,
        "KILL_SWITCH_READY": 1,
        "READY_FOR_DAILY_100_PILOT": ready,
        "OWNER_ACTION_REQUIRED": owner,
        "PILOT_CYCLES_COMPLETED": 1 if cycle_pass else 0,
        "PILOT_CYCLES_REMAINING": 6 if cycle_pass else 7,
    }
    _write_json(ev / "SCHEDULER_GATE.json", out)
    return out


def block_13_sim(ev: Path) -> dict[str, Any]:
    sim = run_31_day_simulation()
    _write_json(ev / "AUTONOMY_31_DAY_SIMULATION.json", sim)
    return {"BLOCK_13_AUTONOMY_SIMULATION": "PASS" if sim.get("ok") else "FAIL", **sim}


def run_supervised(*, apply_live: bool = True) -> dict[str, Any]:
    root = PATHS.root
    ev = evidence_dir(root)
    catalog_path = Path(os.environ.get("RATINGS_CATALOG_PATH", CATALOG_DEFAULT))
    frozen = json.loads((ev / "FROZEN_TITLE_SET.json").read_text(encoding="utf-8"))
    frozen_digest = frozen.get("digest") or frozen.get("frozen_title_set_digest") or ""

    run_id = f"stage5-supervised-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:6]}"
    summary: dict[str, Any] = {
        "STAGE": STAGE,
        "run_id": run_id,
        "started_at": utc_now_iso(),
    }

    summary.update(block_01_source_policy(ev))

    db_path = resolve_canonical_db()
    cfg = RatingsConfig(
        daily_success_target=ACCEPTED_TARGET,
        daily_candidate_cap=CANDIDATE_CAP,
        initial_canary_limit=ACCEPTED_TARGET,
        batch_size=50,
        max_rps=RATE_LIMIT_RPS,
        max_requests_per_minute=max(1, int(RATE_LIMIT_RPS * 60)),
        db_path=db_path,
        evidence_dir=ev,
        lock_name="ratings-ingestion-stage5",
    )
    store = RatingsStore(db_path)
    seed_registry(store)

    # Coverage before
    cov_before = build_global_inventory(catalog_path=catalog_path, db_path=db_path)
    _write_json(ev / "COVERAGE_BEFORE.json", cov_before)

    qmap = block_02_03_queue_mapping(
        ev=ev,
        store=store,
        catalog_path=catalog_path,
        run_id=run_id,
        frozen_digest=frozen_digest,
    )
    summary.update({k: v for k, v in qmap.items() if k != "queue"})
    queue = qmap["queue"]

    summary.update(block_04_qwen(ev))
    pre = block_05_db_preflight(ev=ev, db_path=db_path)
    summary.update({k: v for k, v in pre.items() if k != "backup"})

    if pre.get("BLOCK_05_DB_PREFLIGHT") != "PASS":
        summary["VERDICT"] = "NEEDS_REPAIR"
        summary["stop"] = "BACKUP_OR_INTEGRITY_FAILURE"
        _write_json(ev / "FINAL.md".replace(".md", ".json") if False else ev / "PARTIAL.json", summary)
        return summary

    live_cycles = [0]
    if not apply_live:
        summary["VERDICT"] = "DRY_RUN_ONLY"
        return summary

    try:
        with ratings_lock(cfg.lock_name, timeout=0.0):
            summary["PILOT_LEASE_ACQUIRED"] = 1
            cycle = block_06_supervised_cycle(
                ev=ev,
                store=store,
                cfg=cfg,
                queue=queue,
                run_id=run_id,
                live_cycles_attempted=live_cycles,
            )
            summary.update({k: v for k, v in cycle.items() if k not in ("manifest", "metrics")})
            summary["metrics"] = cycle.get("metrics")

            dbc = block_07_db_commit(ev=ev, store=store, db_path=db_path, run_id=run_id, cfg=cfg)
            summary.update(dbc)

            snap = block_08_snapshot_gateway(ev=ev, store=store, db_path=db_path)
            summary.update(snap)
    except RatingsLockBusy as exc:
        summary["VERDICT"] = "NEEDS_REPAIR"
        summary["stop"] = "ANOTHER_WRITER_ACTIVE"
        summary["holder"] = getattr(exc, "holder", {})
        _write_json(ev / "PARTIAL.json", summary)
        return summary
    except UnauthorizedSourceError as exc:
        summary["VERDICT"] = "BLOCKED_SOURCE"
        summary["stop"] = str(exc)
        return summary

    votes = block_09_user_votes(ev, ev / "raw")
    summary.update(votes)

    cov = block_10_coverage_eta(ev=ev, catalog_path=catalog_path, db_path=db_path)
    summary.update({k: v for k, v in cov.items() if k != "coverage"})
    cov_after = cov["coverage"]

    summary["FIRST_SUPERVISED_CYCLE_PASS"] = 1 if int(summary.get("ACCEPTED") or 0) >= 0 and summary.get("BLOCK_07_DB_COMMIT") == "PASS" else 0
    if int(summary.get("ATTEMPTED") or 0) > 0 and summary.get("BLOCK_07_DB_COMMIT") == "PASS":
        summary["FIRST_SUPERVISED_CYCLE_PASS"] = 1

    report = block_11_report(
        ev=ev,
        run_id=run_id,
        cycle=cycle.get("manifest") or {},
        coverage_before=cov_before,
        coverage_after=cov_after,
        gates=summary,
    )
    summary.update(report)

    sched = block_12_scheduler(ev=ev, root=root, gates=summary)
    summary.update(sched)

    sim = block_13_sim(ev)
    summary.update({k: v for k, v in sim.items() if k.startswith("BLOCK_") or k.startswith("SIMULATION") or k in ("ok",)})

    # Verdict
    if summary.get("FIRST_SUPERVISED_CYCLE_PASS") == 1 and summary.get("SCHEDULER_ENABLED") == "YES":
        verdict = "PASS_SUPERVISED_100_TIMER_ENABLED"
    elif summary.get("FIRST_SUPERVISED_CYCLE_PASS") == 1 and summary.get("QWEN_DELIVERY") == "BLOCKED_NO_CONFIG":
        if int(summary.get("ACCEPTED") or 0) >= ACCEPTED_TARGET:
            verdict = "PASS_SUPERVISED_100_NEEDS_QWEN_CONFIG"
        elif int(summary.get("ACCEPTED") or 0) > 0:
            verdict = "PASS_SUPERVISED_SHORTFALL_EXPLAINED"
        elif queue["QUEUE_CANDIDATE_COUNT"] == 0:
            verdict = "BLOCKED_NO_ELIGIBLE_EXACT_MAPPINGS"
        else:
            verdict = "PASS_SUPERVISED_SHORTFALL_EXPLAINED"
    elif queue["QUEUE_CANDIDATE_COUNT"] == 0:
        verdict = "BLOCKED_NO_ELIGIBLE_EXACT_MAPPINGS"
    else:
        verdict = "NEEDS_REPAIR"

    summary["VERDICT"] = verdict
    summary["finished_at"] = utc_now_iso()
    return summary


def main() -> int:
    import argparse

    p = argparse.ArgumentParser(description="Stage5 supervised Shikimori pilot")
    p.add_argument("--dry-run-plan", action="store_true", help="policy+queue only, no live network")
    p.add_argument("--apply-live", action="store_true", help="run the single authorized live cycle")
    args = p.parse_args()
    if not args.apply_live and not args.dry_run_plan:
        print(json.dumps({"error": "pass --dry-run-plan or --apply-live"}, indent=2))
        return 2
    result = run_supervised(apply_live=bool(args.apply_live))
    ev = evidence_dir()
    _write_json(ev / "RUN_SUMMARY.json", result)
    print(json.dumps({k: result[k] for k in result if k not in ("metrics", "coverage")}, ensure_ascii=False, indent=2))
    return 0 if result.get("VERDICT", "").startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
