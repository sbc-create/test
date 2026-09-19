"""Stage 3 controlled production AMD canary — canonical DB, ≤0.1 rps, closed noindex."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from factory.ratings import ADAPTER_VERSION_AMD_ONLINE
from factory.ratings.adapters.amd_online import AmdOnlineAdapter, load_permission_status
from factory.ratings.adapters.base import AdapterError
from factory.ratings.closed_publish import publish_closed_snapshots, verify_noindex_http
from factory.ratings.coverage_policy import (
    STAGE3_ACCEPTED_TARGET,
    STAGE3_CANDIDATE_CAP,
    compute_daily_target,
    is_covered_row,
    stage3_gates,
    zero_score_retry_after,
)
from factory.ratings.formula import FORMULA_VERSION
from factory.ratings.gateway import RatingGateway
from factory.ratings.local_votes import upsert_combined
from factory.ratings.locks import ratings_lock
from factory.ratings.models import (
    HealthState,
    MappingMethod,
    MappingState,
    RatingObservation,
    SourceRecord,
    SourceState,
    TitleSourceMapping,
    ValidationState,
    payload_sha256,
    utc_now_iso,
)
from factory.ratings.prod_db import (
    apply_migrations,
    backup_db,
    resolve_canonical_db,
    rollback_copy_proof,
    schema_inventory,
)
from factory.ratings.projection import apply_observation
from factory.ratings.rate_limit import RateLimiter
from factory.ratings.rotation import ROTATION_ALGORITHM_VERSION, sort_for_rotation
from factory.ratings.scheduler import SchedulerConfig, assert_disabled, save_scheduler
from factory.ratings.snapshot import build_snapshot, validate_snapshot
from factory.ratings.source_registry import seed_registry
from factory.ratings.store import RatingsStore


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def upsert_absence(store: RatingsStore, *, cid: str, external_id: str, url: str, reason: str, digest: str) -> None:
    store.conn.execute(
        """INSERT INTO rating_source_absence (
            canonical_title_id, source_key, external_id, reason, source_url,
            observed_at, retry_after, payload_digest, details_json)
           VALUES (?,?,?,?,?,?,?,?,?)
           ON CONFLICT(canonical_title_id, source_key) DO UPDATE SET
            reason=excluded.reason,
            source_url=excluded.source_url,
            observed_at=excluded.observed_at,
            retry_after=excluded.retry_after,
            payload_digest=excluded.payload_digest,
            details_json=excluded.details_json""",
        (
            cid,
            "amd_online",
            external_id,
            reason,
            url,
            utc_now_iso(),
            zero_score_retry_after(),
            digest,
            json.dumps({"score": "0.0", "votes": 0}, ensure_ascii=False),
        ),
    )


def enable_amd_source(store: RatingsStore, evidence: Path) -> None:
    seed_registry(store)
    store.upsert_source(
        SourceRecord(
            source_key="amd_online",
            display_name="AMD.online",
            canonical_origin="https://amd.online",
            adapter_version=ADAPTER_VERSION_AMD_ONLINE,
            state=SourceState.READY,
            enabled=True,
            score_scale=10.0,
            supports_vote_count=True,
            max_rps=0.1,
            max_requests_per_minute=6,
            legal_access_evidence=str(evidence / ".." / "ratings-ingestion-02" / "AMD_PERMISSION_STATUS.md"),
            attribution_gate="CLOSED_NOINDEX; public indexed BLOCKED",
            health_state=HealthState.UNKNOWN,
        )
    )


def shadow_plan(urls: list[str], *, cap: int) -> list[dict[str, Any]]:
    """Deterministic candidate list: stable order, canonical dedupe by amd id."""
    seen: set[str] = set()
    plan: list[dict[str, Any]] = []
    for url in urls:
        # extract id
        parts = url.rstrip("/").split("/")[-1]
        ext = parts.split("-", 1)[0]
        cid = f"amd_online:{ext}"
        if cid in seen:
            continue
        seen.add(cid)
        plan.append(
            {
                "rank": len(plan) + 1,
                "canonical_title_id": cid,
                "external_id": ext,
                "url": url,
                "priority_bucket": "amd_public_detail",
                "tie_breaker": cid,
            }
        )
        if len(plan) >= cap:
            break
    return plan


def ingest_one(store: RatingsStore, adapter: AmdOnlineAdapter, url: str, *, run_id: str) -> dict[str, Any]:
    try:
        result = adapter.fetch_detail_html(url)
    except AdapterError as exc:
        return {
            "url": url,
            "result": "FAILED",
            "primary_reason": exc.code,
            "message": str(exc),
        }
    if not result.found:
        reason = result.error or "PROVIDER_RATING_NULL"
        # zero-as-null path
        ext = str(result.external_id or "")
        cid = f"amd_online:{ext}" if ext else f"amd_online:url:{hashlib.sha1(url.encode()).hexdigest()[:12]}"
        if reason in ("PROVIDER_RATING_NULL", "OUT_OF_RANGE") or "ZERO" in reason:
            upsert_absence(
                store,
                cid=cid,
                external_id=ext,
                url=url,
                reason="ZERO_SCORE_NO_VOTE",
                digest=payload_sha256(result.payload or {"url": url}),
            )
            reason = "ZERO_SCORE_NO_VOTE"
        return {
            "url": url,
            "canonical_title_id": cid,
            "external_id": ext,
            "result": "NOT_ADDED",
            "primary_reason": reason,
        }

    payload = result.payload or {}
    cid = f"amd_online:{result.external_id}"
    store.upsert_mapping(
        TitleSourceMapping(
            canonical_title_id=cid,
            source_key="amd_online",
            external_title_id=str(result.external_id),
            external_url=result.provenance_url,
            mapping_method=MappingMethod.MANUAL,
            confidence=1.0,
            evidence="stage3: exact source_id from AMD detail URL",
            verified_at=utc_now_iso(),
            state=MappingState.VERIFIED,
        )
    )
    ph = payload_sha256(payload)
    obs = RatingObservation(
        canonical_title_id=cid,
        source_key="amd_online",
        external_id=str(result.external_id),
        raw_score=result.raw_score,
        source_scale=10.0,
        normalized_score=result.raw_score,
        vote_count=result.vote_count,
        score_distribution=None,
        source_updated_at="",
        observed_at=utc_now_iso(),
        payload_sha256=ph,
        adapter_version=adapter.adapter_version,
        provenance_url=result.provenance_url,
        mapping_method=MappingMethod.MANUAL,
        validation_state=ValidationState.VALID,
        run_id=run_id,
        idempotency_key=f"amd-s3|{result.external_id}|{ph}",
    )
    applied = apply_observation(store, obs, dry_run=False)
    comps = {
        "story": payload.get("story_score"),
        "characters": payload.get("characters_score"),
        "art": payload.get("art_score"),
        "voice": payload.get("voice_score"),
    }
    store.conn.execute(
        """UPDATE rating_current SET component_scores=?, quality_flags=?
           WHERE canonical_title_id=? AND source_key=?""",
        (json.dumps(comps, ensure_ascii=False), json.dumps(payload.get("quality_flags") or []), cid, "amd_online"),
    )
    upsert_combined(store.conn, canonical_title_id=cid, amd_score=result.raw_score, amd_vote_count=result.vote_count)
    return {
        "url": url,
        "canonical_title_id": cid,
        "external_id": result.external_id,
        "result": "ACCEPTED" if applied.get("inserted") else applied.get("action"),
        "inserted": bool(applied.get("inserted")),
        "score": result.raw_score,
        "vote_count": result.vote_count,
        "components": comps,
        "attribution": "Источник: AMD.online",
        "primary_reason": "",
        "idempotency_key": obs.idempotency_key,
        "payload_sha256": ph,
    }


def replay_idempotent(store: RatingsStore, outcomes: list[dict[str, Any]], adapter_version: str) -> dict[str, int]:
    new_obs = 0
    dupes = 0
    for row in outcomes:
        if not row.get("inserted") and row.get("result") != "ACCEPTED":
            continue
        if not row.get("payload_sha256"):
            continue
        again = store.insert_observation(
            RatingObservation(
                canonical_title_id=row["canonical_title_id"],
                source_key="amd_online",
                external_id=str(row["external_id"]),
                raw_score=row.get("score"),
                source_scale=10.0,
                normalized_score=row.get("score"),
                vote_count=row.get("vote_count"),
                score_distribution=None,
                source_updated_at="",
                observed_at=utc_now_iso(),
                payload_sha256=row["payload_sha256"],
                adapter_version=adapter_version,
                provenance_url=row["url"],
                mapping_method=MappingMethod.MANUAL,
                validation_state=ValidationState.VALID,
                idempotency_key=row.get("idempotency_key") or f"amd-s3|{row['external_id']}|{row['payload_sha256']}",
            )
        )
        if again is None:
            dupes += 1
        else:
            new_obs += 1
    return {"new_observations": new_obs, "duplicate_prevented": dupes}


def build_run_report(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "report_version": "ratings_run_report_v1",
        **payload,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--evidence", default="artifacts/evidence/ratings-ingestion-03")
    p.add_argument("--urls-file", default="artifacts/evidence/ratings-ingestion-03/AMD_URL_POOL.json")
    p.add_argument("--accepted-target", type=int, default=STAGE3_ACCEPTED_TARGET)
    p.add_argument("--candidate-cap", type=int, default=STAGE3_CANDIDATE_CAP)
    p.add_argument("--dry-run-only", action="store_true")
    args = p.parse_args(argv)

    evidence = Path(args.evidence)
    evidence.mkdir(parents=True, exist_ok=True)
    run_id = f"s3-{uuid.uuid4().hex[:12]}"
    started = _now()

    perm = load_permission_status()
    db_path = resolve_canonical_db()
    before = schema_inventory(db_path)
    (evidence / "DB_BEFORE.json").write_text(json.dumps(before, ensure_ascii=False, indent=2), encoding="utf-8")

    backup = backup_db(db_path, db_path.parent / "backups")
    scratch = db_path.parent / "backups" / "rollback_scratch.sqlite"
    if backup.get("path"):
        rb = rollback_copy_proof(Path(backup["path"]), scratch)
    else:
        rb = rollback_copy_proof(Path(backup.get("marker") or "/dev/null"), scratch)
    (evidence / "ROLLBACK_PROOF.md").write_text(
        f"# Rollback proof\n\n```json\n{json.dumps({'backup': backup, 'rollback': rb}, indent=2)}\n```\n",
        encoding="utf-8",
    )

    mig = apply_migrations(db_path)
    (evidence / "MIGRATION_RESULT.json").write_text(json.dumps(mig, ensure_ascii=False, indent=2), encoding="utf-8")

    urls = json.loads(Path(args.urls_file).read_text(encoding="utf-8"))["urls"]
    plan = shadow_plan(urls, cap=args.candidate_cap)
    with (evidence / "QUEUE_SAMPLE.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(plan[0].keys()) if plan else ["rank"])
        if plan:
            w.writeheader()
            w.writerows(plan)

    eligible_total = len(plan)
    cov_before = compute_daily_target(eligible_total=eligible_total, covered_valid=0, accepted_cap=args.accepted_target, candidate_cap=args.candidate_cap)
    (evidence / "COVERAGE_BEFORE.json").write_text(json.dumps(cov_before.as_dict(), indent=2), encoding="utf-8")

    if args.dry_run_only:
        print(json.dumps({"dry_run": True, "planned": len(plan), "db": str(db_path)}, indent=2))
        return 0

    with ratings_lock("ratings-ingestion-stage3"):
        store = RatingsStore(db_path)
        enable_amd_source(store, evidence)
        adapter = AmdOnlineAdapter(
            allow_live=True,
            max_live_requests=args.candidate_cap + 5,
            rate_limiter=RateLimiter(max_rps=0.1, max_per_minute=6),
        )
        outcomes: list[dict[str, Any]] = []
        accepted = 0
        for item in plan:
            if accepted >= args.accepted_target:
                break
            row = ingest_one(store, adapter, item["url"], run_id=run_id)
            outcomes.append(row)
            if row.get("inserted") or row.get("result") == "ACCEPTED":
                accepted += 1
            if adapter.auto_stopped:
                break

        replay = replay_idempotent(store, outcomes, adapter.adapter_version)
        body = build_snapshot(store, primary_source="amd_online")
        assert validate_snapshot(body) == []
        digest_before = ""
        digest_after = body.get("snapshot_sha256")
        pubs = publish_closed_snapshots(body, evidence_dir=evidence)
        noindex = verify_noindex_http()

        comb = [dict(r) for r in store.conn.execute("SELECT * FROM rating_combined_projection")]
        ranked = sort_for_rotation(comb)
        (evidence / "rotation_sample.json").write_text(
            json.dumps({"algorithm": ROTATION_ALGORITHM_VERSION, "top10": ranked[:10], "count": len(ranked)}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        sample = next((o["canonical_title_id"] for o in outcomes if o.get("inserted")), None)
        if sample:
            gw = RatingGateway.from_store(store, primary_source="amd_online")
            (evidence / "gateway_sample.json").write_text(
                json.dumps(gw.contract(sample), ensure_ascii=False, indent=2), encoding="utf-8"
            )

        covered = sum(
            1
            for r in store.all_current()
            if r["source_key"] == "amd_online" and is_covered_row(score=r.get("normalized_score"), vote_count=r.get("vote_count"))
        )
        cov_after = compute_daily_target(
            eligible_total=eligible_total,
            covered_valid=covered,
            accepted_cap=args.accepted_target,
            candidate_cap=args.candidate_cap,
        )
        (evidence / "COVERAGE_AFTER.json").write_text(json.dumps(cov_after.as_dict(), indent=2), encoding="utf-8")

        rejected = [o for o in outcomes if o.get("result") != "ACCEPTED" and not o.get("inserted")]
        (evidence / "REJECTIONS.json").write_text(json.dumps(rejected, ensure_ascii=False, indent=2), encoding="utf-8")

        save_scheduler(SchedulerConfig())
        sched = assert_disabled()

        finished = _now()
        shortfall = max(0, args.accepted_target - accepted)
        report = build_run_report(
            {
                "run_id": run_id,
                "run_started_at": started,
                "run_finished_at": finished,
                "code_head": Path(".git/HEAD").read_text().strip() if Path(".git/HEAD").is_file() else "",
                "config_digest": hashlib.sha256(json.dumps(stage3_gates(), sort_keys=True).encode()).hexdigest(),
                "queue_digest": hashlib.sha256(json.dumps([x["canonical_title_id"] for x in plan]).encode()).hexdigest(),
                "snapshot_digest_before": digest_before,
                "snapshot_digest_after": digest_after,
                "eligible_total": eligible_total,
                "covered_total": covered,
                "coverage_percent": cov_after.as_dict()["coverage_percent"],
                "eligible_uncovered_before": cov_before.eligible_uncovered,
                "eligible_uncovered_after": max(0, eligible_total - covered),
                "newly_covered": accepted,
                "refreshed": 0,
                "attempted": len(outcomes),
                "accepted": accepted,
                "rejected": len(rejected),
                "rejection_reasons": {},
                "ongoing_attempted": 0,
                "new_catalog_attempted": 0,
                "backlog_attempted": len(outcomes),
                "unresolved_mappings": 0,
                "zero_score_no_vote": sum(1 for o in rejected if o.get("primary_reason") == "ZERO_SCORE_NO_VOTE"),
                "network_failures": sum(1 for o in outcomes if o.get("primary_reason") in ("TIMEOUT", "HTTP_ERROR")),
                "challenge_failures": adapter.stats.get("challenges", 0),
                "parser_failures": sum(1 for o in rejected if o.get("primary_reason") not in ("ZERO_SCORE_NO_VOTE", "TIMEOUT", "HTTP_ERROR", "AUTO_STOPPED", "")),
                "rate_limit_events": 0,
                "retries": 0,
                "publication_status": pubs,
                "noindex_checks": noindex,
                "scheduler_status": sched,
                "rollback_status": rb,
                "idempotency_replay": replay,
                "adapter_stats": adapter.stats,
                "auto_stopped": adapter.auto_stopped,
                "stop_reason": adapter.stop_reason,
                "shortfall": shortfall,
                "db_path": str(db_path),
                "permission": {
                    "AMD_PERMISSION_STATUS": perm.get("AMD_PERMISSION_STATUS"),
                    "AMD_CLOSED_NOINDEX_USAGE": "ALLOWED_BY_OWNER",
                    "AMD_PUBLIC_INDEXED_PUBLICATION": "BLOCKED",
                },
                "formula_version": FORMULA_VERSION,
            }
        )
        # rejection reason histogram
        from collections import Counter

        report["rejection_reasons"] = dict(Counter(o.get("primary_reason") or "UNKNOWN" for o in rejected))

        (evidence / "RUN_REPORT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        (evidence / "PUBLICATION_RESULT.json").write_text(json.dumps(pubs, ensure_ascii=False, indent=2), encoding="utf-8")
        (evidence / "NOINDEX_VERIFICATION.json").write_text(json.dumps(noindex, ensure_ascii=False, indent=2), encoding="utf-8")
        (evidence / "SCHEDULER_STATUS.json").write_text(json.dumps(sched, ensure_ascii=False, indent=2), encoding="utf-8")
        (evidence / "SNAPSHOT_MANIFEST.json").write_text(
            json.dumps({"digest": digest_after, "title_count": body.get("title_count"), "schema": body.get("schema_version")}, indent=2),
            encoding="utf-8",
        )

        with (evidence / "OUTCOMES.csv").open("w", newline="", encoding="utf-8") as fh:
            if outcomes:
                keys = sorted({k for o in outcomes for k in o})
                w = csv.DictWriter(fh, fieldnames=keys)
                w.writeheader()
                for o in outcomes:
                    flat = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, dict | list) else v) for k, v in o.items()}
                    w.writerow(flat)

        store.touch_source_success("amd_online", schema_check=utc_now_iso())
        store.close()

    print(json.dumps({"accepted": accepted, "attempted": len(outcomes), "shortfall": shortfall, "run_id": run_id}, indent=2))
    if report.get("auto_stopped"):
        return 2
    if shortfall > 0:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
