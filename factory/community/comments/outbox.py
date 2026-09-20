"""Transactional moderation outbox for Qwen postmod jobs."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from factory.community.store import COMMENTS_OUTBOX_SQL, CommunityStore

# Re-export for callers / docs
__all__ = (
    "COMMENTS_OUTBOX_SQL",
    "JOB_PENDING",
    "JOB_LEASED",
    "JOB_DONE",
    "JOB_DEAD_LETTER",
    "JOB_CANCELLED",
    "cancel_jobs_for_comment",
    "claim_jobs",
    "complete_job",
    "enqueue_job",
    "fail_job",
    "ensure_outbox_schema",
)

JOB_PENDING = "PENDING"
JOB_LEASED = "LEASED"
JOB_DONE = "DONE"
JOB_DEAD_LETTER = "DEAD_LETTER"
JOB_CANCELLED = "CANCELLED"

DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_BACKOFF_BASE_SEC = 15


def _utc() -> datetime:
    return datetime.now(timezone.utc)


def _utc_str(dt: datetime | None = None) -> str:
    return (dt or _utc()).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def ensure_outbox_schema(store: CommunityStore) -> None:
    store.conn.executescript(COMMENTS_OUTBOX_SQL)


def enqueue_job(
    store: CommunityStore,
    *,
    comment_id: str,
    revision: int,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Enqueue a moderation job. Idempotent on idempotency_key."""
    ensure_outbox_schema(store)
    key = idempotency_key or f"{comment_id}:{int(revision)}"
    now = _utc_str()
    existing = store.conn.execute(
        "SELECT * FROM community_comment_moderation_jobs WHERE idempotency_key=?",
        (key,),
    ).fetchone()
    if existing:
        return {"enqueued": False, "duplicate": True, "job": dict(existing)}
    job_id = _new_id("cmj")
    store.conn.execute(
        """INSERT INTO community_comment_moderation_jobs
           (job_id, comment_id, revision, idempotency_key, status,
            lease_owner, lease_until, attempts, next_attempt_at,
            last_error, created_at, updated_at, result_json)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            job_id,
            comment_id,
            int(revision),
            key,
            JOB_PENDING,
            "",
            "",
            0,
            now,
            "",
            now,
            now,
            "{}",
        ),
    )
    return {
        "enqueued": True,
        "duplicate": False,
        "job": {
            "job_id": job_id,
            "comment_id": comment_id,
            "revision": int(revision),
            "idempotency_key": key,
            "status": JOB_PENDING,
        },
    }


def claim_jobs(
    store: CommunityStore,
    *,
    limit: int = 1,
    lease_ttl_sec: int = 60,
    worker_id: str = "worker-1",
) -> list[dict[str, Any]]:
    """Claim up to ``limit`` PENDING (or expired LEASED) jobs. Concurrency=1 friendly."""
    ensure_outbox_schema(store)
    now = _utc()
    now_s = _utc_str(now)
    lease_until = _utc_str(now + timedelta(seconds=lease_ttl_sec))
    limit = max(1, min(int(limit), 1))  # default concurrency 1 — no burst claim
    claimed: list[dict[str, Any]] = []
    with store._lock:
        rows = store.conn.execute(
            """SELECT * FROM community_comment_moderation_jobs
               WHERE (
                    status=? AND (next_attempt_at='' OR next_attempt_at<=?)
                 ) OR (
                    status=? AND lease_until!='' AND lease_until<?
                 )
               ORDER BY created_at ASC
               LIMIT ?""",
            (JOB_PENDING, now_s, JOB_LEASED, now_s, limit),
        ).fetchall()
        for row in rows:
            job = dict(row)
            cur = store.conn.execute(
                """UPDATE community_comment_moderation_jobs
                   SET status=?, lease_owner=?, lease_until=?, updated_at=?,
                       attempts=attempts+1
                   WHERE job_id=? AND status IN (?, ?)""",
                (
                    JOB_LEASED,
                    worker_id,
                    lease_until,
                    now_s,
                    job["job_id"],
                    JOB_PENDING,
                    JOB_LEASED,
                ),
            )
            if cur.rowcount:
                refreshed = store.conn.execute(
                    "SELECT * FROM community_comment_moderation_jobs WHERE job_id=?",
                    (job["job_id"],),
                ).fetchone()
                claimed.append(dict(refreshed))
    return claimed


def complete_job(
    store: CommunityStore,
    job_id: str,
    result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = _utc_str()
    store.conn.execute(
        """UPDATE community_comment_moderation_jobs
           SET status=?, lease_owner='', lease_until='', last_error='',
               result_json=?, updated_at=?
           WHERE job_id=?""",
        (JOB_DONE, json.dumps(result or {}, ensure_ascii=False), now, job_id),
    )
    return {"job_id": job_id, "status": JOB_DONE}


def fail_job(
    store: CommunityStore,
    job_id: str,
    error: str,
    *,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    backoff_base_sec: int = DEFAULT_BACKOFF_BASE_SEC,
) -> dict[str, Any]:
    row = store.conn.execute(
        "SELECT * FROM community_comment_moderation_jobs WHERE job_id=?", (job_id,)
    ).fetchone()
    if not row:
        return {"job_id": job_id, "status": "MISSING"}
    job = dict(row)
    attempts = int(job.get("attempts") or 0)
    now = _utc()
    if attempts >= max_attempts:
        status = JOB_DEAD_LETTER
        next_at = ""
    else:
        status = JOB_PENDING
        delay = backoff_base_sec * (2 ** max(0, attempts - 1))
        next_at = _utc_str(now + timedelta(seconds=delay))
    store.conn.execute(
        """UPDATE community_comment_moderation_jobs
           SET status=?, lease_owner='', lease_until='', last_error=?,
               next_attempt_at=?, updated_at=?
           WHERE job_id=?""",
        (status, str(error)[:2000], next_at, _utc_str(now), job_id),
    )
    return {"job_id": job_id, "status": status, "attempts": attempts, "next_attempt_at": next_at}


def cancel_jobs_for_comment(store: CommunityStore, comment_id: str) -> int:
    now = _utc_str()
    cur = store.conn.execute(
        """UPDATE community_comment_moderation_jobs
           SET status=?, lease_owner='', lease_until='', updated_at=?,
               last_error='cancelled: comment deleted'
           WHERE comment_id=? AND status IN (?, ?)""",
        (JOB_CANCELLED, now, comment_id, JOB_PENDING, JOB_LEASED),
    )
    return int(cur.rowcount or 0)
