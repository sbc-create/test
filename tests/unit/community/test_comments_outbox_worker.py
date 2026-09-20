"""Outbox lease/retry/dead-letter + worker process_once tests."""

from __future__ import annotations

import pytest

from factory.community.comments import outbox, states
from factory.community.comments.degraded import DegradedController
from factory.community.comments.qwen.apply import ApplyDecisionError, apply_decision
from factory.community.comments.qwen.provider import FakeQwenProvider
from factory.community.comments.worker import process_once
from factory.community.store import CommunityStore


@pytest.fixture()
def store(tmp_path):
    s = CommunityStore(tmp_path / "outbox.sqlite")
    yield s
    s.close()


def _insert_comment(store, cid="c1", body="great episode overall", status=None, version=1):
    status = status or states.PUBLISHED_UNREVIEWED
    store.conn.execute(
        """INSERT INTO community_comments
           (comment_id, site_space, title_id, identity_id, body, body_normalized,
            status, moderation_status, version, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            cid,
            "yummy",
            "t1",
            "id1",
            body,
            body.casefold(),
            status,
            status,
            version,
            "2026-01-01T00:00:00Z",
            "2026-01-01T00:00:00Z",
        ),
    )


def test_enqueue_idempotent(store):
    a = outbox.enqueue_job(store, comment_id="c1", revision=1)
    b = outbox.enqueue_job(store, comment_id="c1", revision=1)
    assert a["enqueued"] is True
    assert b["duplicate"] is True


def test_claim_concurrency_one(store):
    _insert_comment(store, "c1")
    _insert_comment(store, "c2", body="another solid comment here")
    outbox.enqueue_job(store, comment_id="c1", revision=1)
    outbox.enqueue_job(store, comment_id="c2", revision=1)
    claimed = outbox.claim_jobs(store, limit=5, worker_id="w1")
    assert len(claimed) == 1
    assert claimed[0]["status"] == outbox.JOB_LEASED


def test_fail_backoff_then_dead_letter(store):
    outbox.enqueue_job(store, comment_id="c1", revision=1)
    job = outbox.claim_jobs(store, worker_id="w")[0]
    # Simulate many failures
    status = None
    for _ in range(6):
        # re-claim style: set pending manually after fail
        result = outbox.fail_job(store, job["job_id"], "boom", max_attempts=3)
        status = result["status"]
        if status == outbox.JOB_DEAD_LETTER:
            break
        # bump attempts by claiming again
        store.conn.execute(
            "UPDATE community_comment_moderation_jobs SET status=?, attempts=attempts WHERE job_id=?",
            (outbox.JOB_PENDING, job["job_id"]),
        )
        # manually increment attempts to mirror claim
        store.conn.execute(
            "UPDATE community_comment_moderation_jobs SET attempts=attempts+1 WHERE job_id=?",
            (job["job_id"],),
        )
    row = dict(
        store.conn.execute(
            "SELECT * FROM community_comment_moderation_jobs WHERE job_id=?",
            (job["job_id"],),
        ).fetchone()
    )
    assert row["status"] == outbox.JOB_DEAD_LETTER or status == outbox.JOB_DEAD_LETTER


def test_worker_applies_allow(store):
    _insert_comment(store, "c1", body="wonderful animation and music")
    outbox.enqueue_job(store, comment_id="c1", revision=1)
    metrics = process_once(store, FakeQwenProvider(), degraded_controller=DegradedController())
    assert metrics["claimed"] == 1
    assert metrics["applied"] == 1
    row = dict(
        store.conn.execute(
            "SELECT moderation_status, status FROM community_comments WHERE comment_id='c1'"
        ).fetchone()
    )
    assert row["moderation_status"] == states.VISIBLE_QWEN_APPROVED


def test_revision_mismatch_refused(store):
    _insert_comment(store, "c1", body="wonderful animation and music", version=2)
    decision = FakeQwenProvider().moderate(
        {
            "comment_text": "wonderful animation and music",
            "prompt_digest": "d" * 64,
            "context": {"language": "en", "user_spoiler_flag": False},
        }
    )
    with pytest.raises(ApplyDecisionError):
        apply_decision(store, "c1", revision=1, decision=decision)


def test_delete_before_qwen_cancels(store):
    _insert_comment(store, "c1", body="wonderful animation and music", status=states.DELETED_BY_AUTHOR)
    outbox.enqueue_job(store, comment_id="c1", revision=1)
    metrics = process_once(store, FakeQwenProvider())
    assert metrics["skipped_deleted"] == 1
    row = dict(
        store.conn.execute(
            "SELECT status FROM community_comment_moderation_jobs WHERE comment_id='c1'"
        ).fetchone()
    )
    assert row["status"] == outbox.JOB_CANCELLED


def test_apply_idempotent(store):
    _insert_comment(store, "c1", body="wonderful animation and music")
    decision = FakeQwenProvider().moderate(
        {
            "comment_text": "wonderful animation and music",
            "prompt_digest": "e" * 64,
            "context": {"language": "en", "user_spoiler_flag": False},
        }
    )
    a = apply_decision(store, "c1", 1, decision)
    b = apply_decision(store, "c1", 1, decision)
    assert a["applied"] is True
    assert b["idempotent"] is True


def test_cancel_jobs_helper(store):
    outbox.enqueue_job(store, comment_id="c9", revision=1)
    n = outbox.cancel_jobs_for_comment(store, "c9")
    assert n == 1
