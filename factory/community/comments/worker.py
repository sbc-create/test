"""Qwen postmod worker — process_once, concurrency=1, no catch-up burst."""

from __future__ import annotations

from typing import Any

from factory.community.comments import outbox
from factory.community.comments.degraded import DegradedController
from factory.community.comments.qwen.apply import ApplyDecisionError, apply_decision
from factory.community.comments.qwen.prompt import build_request_payload
from factory.community.comments.qwen.provider import QwenProvider
from factory.community.comments.qwen.schema import validate_decision
from factory.community.store import CommunityStore


def process_once(
    store: CommunityStore,
    provider: QwenProvider,
    *,
    degraded_controller: DegradedController | None = None,
    worker_id: str = "worker-1",
    lease_ttl_sec: int = 60,
) -> dict[str, int]:
    """Claim at most one job and process it. Returns metrics counters."""
    metrics = {
        "claimed": 0,
        "processed": 0,
        "applied": 0,
        "schema_mismatch": 0,
        "errors": 0,
        "skipped_deleted": 0,
        "cancelled": 0,
        "dead_letter": 0,
    }
    if degraded_controller is not None and degraded_controller.stop_worker:
        return metrics

    jobs = outbox.claim_jobs(
        store, limit=1, lease_ttl_sec=lease_ttl_sec, worker_id=worker_id
    )
    if not jobs:
        return metrics
    metrics["claimed"] = len(jobs)
    job = jobs[0]
    job_id = job["job_id"]
    comment_id = job["comment_id"]
    revision = int(job["revision"])

    row = store.conn.execute(
        "SELECT * FROM community_comments WHERE comment_id=?", (comment_id,)
    ).fetchone()
    if not row:
        outbox.fail_job(store, job_id, "comment missing")
        metrics["errors"] += 1
        return metrics
    comment = dict(row)
    status = comment.get("moderation_status") or comment.get("status") or ""
    if status in ("DELETED_BY_AUTHOR", "DELETED_BY_USER", "DELETED_BY_ADMIN"):
        outbox.cancel_jobs_for_comment(store, comment_id)
        metrics["skipped_deleted"] += 1
        metrics["cancelled"] += 1
        return metrics

    payload = build_request_payload(
        comment.get("body") or "",
        title=comment.get("title_id") or "",
        content_type=comment.get("content_type") or "",
        is_reply=bool(comment.get("parent_comment_id")),
        parent_excerpt=None,
        user_spoiler_flag=bool(comment.get("spoiler")),
        language="und",
    )
    try:
        decision = provider.moderate(payload)
        check = validate_decision(decision, comment_text=comment.get("body") or "")
        if not check["ok"]:
            metrics["schema_mismatch"] += 1
            result = outbox.fail_job(store, job_id, f"schema: {check['errors']}")
            if result.get("status") == outbox.JOB_DEAD_LETTER:
                metrics["dead_letter"] += 1
            if degraded_controller is not None:
                degraded_controller.record_schema_mismatch()
            return metrics
        applied = apply_decision(store, comment_id, revision, decision)
        outbox.complete_job(store, job_id, {"apply": applied, "action": decision.get("action")})
        metrics["processed"] += 1
        if applied.get("applied"):
            metrics["applied"] += 1
        if degraded_controller is not None:
            degraded_controller.record_success()
    except ApplyDecisionError as exc:
        if "deleted by author" in str(exc).lower():
            outbox.cancel_jobs_for_comment(store, comment_id)
            metrics["skipped_deleted"] += 1
            metrics["cancelled"] += 1
        else:
            result = outbox.fail_job(store, job_id, str(exc))
            metrics["errors"] += 1
            if result.get("status") == outbox.JOB_DEAD_LETTER:
                metrics["dead_letter"] += 1
    except Exception as exc:  # noqa: BLE001 — worker must not crash loop
        result = outbox.fail_job(store, job_id, f"{exc.__class__.__name__}: {exc}")
        metrics["errors"] += 1
        if result.get("status") == outbox.JOB_DEAD_LETTER:
            metrics["dead_letter"] += 1
        if degraded_controller is not None:
            degraded_controller.record_provider_error()
    return metrics
