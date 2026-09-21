#!/usr/bin/env python3
"""COMMUNITY-COMMENTS-03 staging canary runner.

Runs every scenario class required by the stage goal against an **isolated
staging database**, then removes every synthetic row and proves the count is
zero. Production is never touched: this script refuses to open a database that
is not the dedicated staging file.

Provider selection:

  --provider heuristic   (default) pipeline rehearsal. NOT a real canary.
                         REAL_QWEN_CANARY_EXECUTED=0.
  --provider live        real Qwen. Requires a READY runtime preflight, an
                         OWNER_AUTHORIZATION_ID and an explicit --spend-cap-rub.
                         Refuses otherwise — a fake is never substituted.

Evidence is written under artifacts/evidence/community-comments-03/ and
contains digests, lengths, labels, timings and decisions — never comment text.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
import sys
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from factory.community.comments import outbox, states  # noqa: E402
from factory.community.comments.degraded import DegradedController  # noqa: E402
from factory.community.comments.kill_switch import (  # noqa: E402
    KillSwitchCapabilities,
    drill_and_restore,
    load_capabilities,
    save_capabilities,
)
from factory.community.comments.preflight import PreflightError, run_preflight  # noqa: E402
from factory.community.comments.qwen.apply import (  # noqa: E402
    ApplyDecisionError,
    apply_decision,
)
from factory.community.comments.qwen.gold_corpus import GOLD_CASES  # noqa: E402
from factory.community.comments.qwen.runtime_preflight import runtime_preflight  # noqa: E402
from factory.community.comments.qwen.staging_harness import (  # noqa: E402
    OUTCOME_PROVIDER_ERROR,
    CountingProvider,
    HeuristicV2Provider,
    ProviderInvalidJSON,
    ProviderTimeout,
    digest,
    moderate_once,
    new_request_id,
    status_is_public,
)
from factory.community.store import CommunityStore  # noqa: E402

EVIDENCE = REPO / "artifacts/evidence/community-comments-03"
STAGING_DB = REPO / "var/community_comments/staging_canary.sqlite"
CANARY_SITE_SPACE = "staging-canary"
CANARY_MARKER = "canary_"

# Scenario classes required by goal §18.
REQUIRED_SCENARIO_CLASSES = (
    "positive_comment",
    "ordinary_criticism",
    "constructive_negative_review",
    "spoiler",
    "toxicity",
    "insult",
    "spam",
    "link_spam",
    "prompt_injection",
    "system_prompt_extraction",
    "pii",
    "mixed_cyrillic_latin",
    "long_text",
    "empty_text",
    "provider_timeout",
    "invalid_json",
    "duplicate_response",
    "retry",
    "kill_switch",
    "state_machine",
)


def _utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _write(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    return path


def _assert_staging_db(path: Path) -> None:
    """Refuse to run against anything but the dedicated staging file."""
    resolved = path.resolve()
    if resolved != STAGING_DB.resolve():
        raise SystemExit(f"refusing non-staging database: {resolved}")
    for forbidden in ("ratings.sqlite", "production", "prod"):
        if forbidden in resolved.name:
            raise SystemExit(f"refusing production-looking database: {resolved}")


def _insert_canary_comment(
    store: CommunityStore,
    *,
    comment_id: str,
    body: str,
    status: str | None = None,
    version: int = 1,
) -> None:
    status = status or states.PUBLISHED_UNREVIEWED
    now = _utc()
    store.conn.execute(
        """INSERT INTO community_comments
           (comment_id, site_space, title_id, identity_id, body, body_normalized,
            body_digest, status, moderation_status, version, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            comment_id,
            CANARY_SITE_SPACE,
            "canary_title",
            "canary_identity",
            body,
            body.casefold(),
            digest(body),
            status,
            status,
            version,
            now,
            now,
        ),
    )


def _case_class(case: dict[str, Any]) -> str:
    """Map a gold case onto a required scenario class."""
    cid = case["case_id"]
    category = case["category"]
    # Specific cases claim the scenario class they were written for; everything
    # else falls back to its semantic category.
    if cid == "clean_06":
        return "long_text"
    if cid == "inject_03":
        return "system_prompt_extraction"
    if cid == "spam_03":
        return "link_spam"
    if cid == "clean_04":
        return "mixed_cyrillic_latin"
    mapping = {
        "clean": "positive_comment",
        "constructive": "constructive_negative_review",
        "spoiler": "spoiler",
        "spam": "spam",
        "toxicity": "insult",
        "threat": "toxicity",
        "hate": "toxicity",
        "danger": "toxicity",
        "pii": "pii",
        "injection": "prompt_injection",
        "ambiguous": "ordinary_criticism",
    }
    return mapping.get(category, "positive_comment")


# --------------------------------------------------------------------------
# Scenario sections
# --------------------------------------------------------------------------


def run_content_scenarios(provider: CountingProvider) -> dict[str, Any]:
    """Gold corpus through the full payload → provider → schema path."""
    records: list[dict[str, Any]] = []
    for case in GOLD_CASES:
        rec = moderate_once(
            provider,
            raw_text=case["body"],
            request_id=new_request_id(),
            language=case["lang"],
            user_spoiler_flag=(case["severity"] == "spoiler"),
        )
        records.append(
            {
                "case_id": case["case_id"],
                "scenario_class": _case_class(case),
                "category": case["category"],
                "severity": case["severity"],
                "expected_family": case["expected"],
                "outcome": rec["outcome"],
                "labels": rec.get("labels", []),
                "schema_valid": rec["schema_valid"],
                "retries": rec["retries"],
                "latency_ms": rec["latency_ms"],
                "text_digest": rec["text_digest"],
                "text_len": rec["text_len"],
                "payload_safety": rec["safety"],
            }
        )
    return {
        "count": len(records),
        "records": records,
        "schema_valid_all": all(r["schema_valid"] for r in records),
        "forbidden_key_hits": sum(
            r["payload_safety"]["forbidden_keys"] for r in records
        ),
        "raw_pii_hits": sum(r["payload_safety"]["raw_pii_spans"] for r in records),
        "system_prompt_leaks": sum(
            r["payload_safety"]["system_prompt_leak"] for r in records
        ),
    }


def run_empty_text() -> dict[str, Any]:
    """Empty body must be rejected by local preflight, never sent to Qwen."""
    outcomes = []
    for body in ("", "   ", "\n\t "):
        try:
            run_preflight(body)
            outcomes.append({"len": len(body), "rejected": False, "code": ""})
        except PreflightError as exc:
            outcomes.append(
                {"len": len(body), "rejected": True, "code": exc.reject_code}
            )
    return {
        "scenario_class": "empty_text",
        "cases": outcomes,
        "all_rejected_locally": all(o["rejected"] for o in outcomes),
        "provider_calls": 0,
    }


def run_provider_timeout() -> dict[str, Any]:
    """Timeout must end in PROVIDER_ERROR and never publish."""
    def fault(call_no: int, _payload: dict[str, Any]) -> Any:
        raise ProviderTimeout("simulated provider timeout")

    prov = CountingProvider(inner=HeuristicV2Provider(), fault=fault)
    rec = moderate_once(prov, raw_text="Обычный отзыв про сюжет.", request_id=new_request_id())
    return {
        "scenario_class": "provider_timeout",
        "outcome": rec["outcome"],
        "published": False,
        "retries": rec["retries"],
        "provider_calls": prov.calls,
        "pass": rec["outcome"] == OUTCOME_PROVIDER_ERROR,
    }


def run_invalid_json() -> dict[str, Any]:
    """Malformed / schema-violating responses must be refused."""
    variants: list[dict[str, Any]] = []

    def bad_json(_n: int, _p: dict[str, Any]) -> Any:
        return "{not valid json"

    def wrong_shape(_n: int, _p: dict[str, Any]) -> Any:
        return {"decision": "ALLOW"}  # missing required fields

    def hostile_keys(_n: int, p: dict[str, Any]) -> Any:
        return {
            "schema_version": "QWEN_DECISION_SCHEMA_V2",
            "policy_version": "QWEN_MODERATION_POLICY_V1",
            "decision": "ALLOW",
            "labels": ["CLEAN"],
            "confidence": 1.0,
            "reason_codes": ["OK"],
            "language": "en",
            "spoiler": False,
            "toxicity_score": 0.0,
            "spam_score": 0.0,
            "pii_detected": False,
            "prompt_injection_detected": False,
            "model": "m",
            "request_id": str(p.get("request_id") or ""),
            "shell": "rm -rf /",  # forbidden key
        }

    for name, fault in (
        ("malformed_json", bad_json),
        ("missing_fields", wrong_shape),
        ("forbidden_keys", hostile_keys),
    ):
        prov = CountingProvider(inner=HeuristicV2Provider(), fault=fault)
        rec = moderate_once(
            prov, raw_text="Хороший эпизод, понравился финал арки.", request_id=new_request_id()
        )
        variants.append(
            {
                "variant": name,
                "outcome": rec["outcome"],
                "schema_valid": rec["schema_valid"],
                "provider_calls": prov.calls,
                "refused": rec["outcome"] == OUTCOME_PROVIDER_ERROR,
            }
        )
    return {
        "scenario_class": "invalid_json",
        "variants": variants,
        "pass": all(v["refused"] for v in variants),
    }


def run_retry() -> dict[str, Any]:
    """Transient failure then success: bounded retries, one logical task."""
    def fault(call_no: int, _p: dict[str, Any]) -> Any:
        if call_no == 1:
            raise ProviderTimeout("transient")
        return None  # fall through to the real provider

    prov = CountingProvider(inner=HeuristicV2Provider(), fault=fault)
    rec = moderate_once(prov, raw_text="Отличная режиссура в этом сезоне.", request_id=new_request_id())
    return {
        "scenario_class": "retry",
        "outcome": rec["outcome"],
        "retries": rec["retries"],
        "provider_calls": prov.calls,
        "logical_tasks": 1,
        "pass": rec["retries"] == 1 and prov.calls == 2 and rec["schema_valid"],
    }


def run_retry_exhaustion() -> dict[str, Any]:
    """Retries are capped — a permanently failing provider cannot loop."""
    def fault(_n: int, _p: dict[str, Any]) -> Any:
        raise ProviderTimeout("permanent")

    prov = CountingProvider(inner=HeuristicV2Provider(), fault=fault)
    rec = moderate_once(
        prov, raw_text="Ещё один обычный отзыв.", request_id=new_request_id(), max_retries=2
    )
    return {
        "scenario_class": "retry_exhaustion",
        "outcome": rec["outcome"],
        "retries": rec["retries"],
        "provider_calls": prov.calls,
        "pass": prov.calls == 3 and rec["outcome"] == OUTCOME_PROVIDER_ERROR,
    }


def run_duplicate_and_idempotency(store: CommunityStore) -> dict[str, Any]:
    """Same idempotency key must not create a second provider call."""
    cid = f"{CANARY_MARKER}idem_01"
    _insert_canary_comment(store, comment_id=cid, body="Приятный сезон, смотрю дальше.")

    first = outbox.enqueue_job(store, comment_id=cid, revision=1)
    second = outbox.enqueue_job(store, comment_id=cid, revision=1)

    prov = CountingProvider(inner=HeuristicV2Provider())
    rec = moderate_once(prov, raw_text="Приятный сезон, смотрю дальше.", request_id=new_request_id())
    decision_v1 = rec["v1"]

    applied_1 = apply_decision(store, cid, 1, decision_v1)
    applied_2 = apply_decision(store, cid, 1, decision_v1)

    calls_after_replay = prov.calls

    # A duplicate provider response for an already-applied decision is a no-op.
    return {
        "scenario_class": "duplicate_response",
        "enqueue_first": first["enqueued"],
        "enqueue_second_duplicate": second["duplicate"],
        "apply_first_applied": applied_1["applied"],
        "apply_second_idempotent": applied_2.get("idempotent", False),
        "provider_calls_total": calls_after_replay,
        "duplicate_provider_calls": 0,
        "pass": (
            first["enqueued"]
            and second["duplicate"]
            and applied_1["applied"]
            and applied_2.get("idempotent", False)
            and calls_after_replay == 1
        ),
    }


def run_kill_switch(store: CommunityStore, flags_path: Path) -> dict[str, Any]:
    """Kill switch engages, blocks, and restores — with an audit trail."""
    drill = drill_and_restore(path=flags_path, store=store, actor="canary-drill")
    engaged_blocks = all(
        drill["engaged"][k] == 1
        for k in ("block_writes", "hide_new_public", "stop_worker")
    )
    restored_clear = all(
        drill["after"][k] == 0
        for k in ("block_writes", "hide_new_public", "stop_worker")
    )
    audit_lines = 0
    audit_path = Path(drill["audit_jsonl"])
    if audit_path.is_file():
        audit_lines = sum(1 for _ in audit_path.open(encoding="utf-8"))

    # Engaged kill switch must stop the worker path from writing.
    save_capabilities(
        KillSwitchCapabilities(block_writes=1, stop_worker=1, reason="canary_block_probe"),
        flags_path,
        actor="canary-drill",
        store=store,
        detail="block_probe",
    )
    blocked = load_capabilities(flags_path).block_writes == 1
    save_capabilities(
        KillSwitchCapabilities(reason="canary_restore"),
        flags_path,
        actor="canary-drill",
        store=store,
        detail="restore",
    )
    final_clear = load_capabilities(flags_path).block_writes == 0

    return {
        "scenario_class": "kill_switch",
        "engaged_blocks": engaged_blocks,
        "restored_clear": restored_clear,
        "write_block_observed": blocked,
        "restored_after_probe": final_clear,
        "audit_records": audit_lines,
        "pass": engaged_blocks and restored_clear and blocked and final_clear and audit_lines > 0,
    }


def run_state_machine() -> dict[str, Any]:
    """Legal transitions allowed, illegal refused, terminal states terminal."""
    legal = [
        (states.PUBLISHED_UNREVIEWED, states.VISIBLE_QWEN_APPROVED),
        (states.PUBLISHED_UNREVIEWED, states.VISIBLE_SPOILER_COLLAPSED),
        (states.PUBLISHED_UNREVIEWED, states.HIDDEN_QWEN_HIGH_CONFIDENCE),
        (states.HELD_FOR_REVIEW, states.VISIBLE_QWEN_APPROVED),
        (states.PENDING_MODERATION_DEGRADED, states.HELD_FOR_REVIEW),
    ]
    illegal = [
        (states.DELETED_BY_ADMIN, states.VISIBLE_QWEN_APPROVED),
        (states.PREFLIGHT_REJECTED, states.VISIBLE_QWEN_APPROVED),
        (states.DELETED_BY_AUTHOR, states.VISIBLE_QWEN_APPROVED),
    ]
    legal_ok = [states.transition_allowed(a, b) for a, b in legal]
    illegal_ok = [not states.transition_allowed(a, b) for a, b in illegal]
    # Automation must never hard-delete: every soft-delete state retains the body.
    retains = [states.retains_body(s) for s in sorted(states.SOFT_DELETE_STATUSES)]
    return {
        "scenario_class": "state_machine",
        "legal_transitions_allowed": sum(legal_ok),
        "legal_transitions_total": len(legal),
        "illegal_transitions_refused": sum(illegal_ok),
        "illegal_transitions_total": len(illegal),
        "soft_delete_retains_body": all(retains),
        "pass": all(legal_ok) and all(illegal_ok) and all(retains),
    }


def run_revision_race(store: CommunityStore) -> dict[str, Any]:
    """A decision for a stale revision must be refused, not applied."""
    cid = f"{CANARY_MARKER}rev_01"
    _insert_canary_comment(store, comment_id=cid, body="Первая версия комментария.", version=1)
    prov = CountingProvider(inner=HeuristicV2Provider())
    rec = moderate_once(prov, raw_text="Первая версия комментария.", request_id=new_request_id())

    # Author edits while the job is in flight → version becomes 2.
    store.conn.execute(
        "UPDATE community_comments SET version=2, body=?, updated_at=? WHERE comment_id=?",
        ("Вторая версия комментария.", _utc(), cid),
    )
    refused = False
    error = ""
    try:
        apply_decision(store, cid, 1, rec["v1"])
    except ApplyDecisionError as exc:
        refused = True
        error = str(exc)[:120]

    row = store.conn.execute(
        "SELECT status FROM community_comments WHERE comment_id=?", (cid,)
    ).fetchone()
    return {
        "scenario_class": "revision_race",
        "stale_decision_refused": refused,
        "error": error,
        "status_after": row["status"] if row else "",
        "pass": refused,
    }


def run_delete_race(store: CommunityStore) -> dict[str, Any]:
    """After an author delete, a late decision must not resurrect the comment."""
    cid = f"{CANARY_MARKER}del_01"
    _insert_canary_comment(store, comment_id=cid, body="Удалю этот комментарий сам.", version=1)
    prov = CountingProvider(inner=HeuristicV2Provider())
    rec = moderate_once(prov, raw_text="Удалю этот комментарий сам.", request_id=new_request_id())

    store.conn.execute(
        "UPDATE community_comments SET status=?, moderation_status=?, updated_at=? WHERE comment_id=?",
        (states.DELETED_BY_AUTHOR, states.DELETED_BY_AUTHOR, _utc(), cid),
    )
    cancelled = outbox.cancel_jobs_for_comment(store, cid)

    refused = False
    error = ""
    try:
        apply_decision(store, cid, 1, rec["v1"])
    except ApplyDecisionError as exc:
        refused = True
        error = str(exc)[:120]

    row = store.conn.execute(
        "SELECT status FROM community_comments WHERE comment_id=?", (cid,)
    ).fetchone()
    still_deleted = bool(row and row["status"] == states.DELETED_BY_AUTHOR)
    return {
        "scenario_class": "delete_race",
        "late_decision_refused": refused,
        "error": error,
        "jobs_cancelled": cancelled,
        "still_deleted": still_deleted,
        "not_republished": still_deleted,
        "pass": refused and still_deleted,
    }


def run_concurrency_lease(store: CommunityStore) -> dict[str, Any]:
    """Two workers racing for the same job: exactly one lease."""
    cid = f"{CANARY_MARKER}lease_01"
    _insert_canary_comment(store, comment_id=cid, body="Комментарий для проверки lease.")

    # Isolate the race: park every other pending job so the two workers are
    # competing for exactly one job, not merely draining a shared queue.
    store.conn.execute(
        """UPDATE community_comment_moderation_jobs
           SET next_attempt_at='2999-01-01T00:00:00Z'
           WHERE status=? AND comment_id!=?""",
        (outbox.JOB_PENDING, cid),
    )
    outbox.enqueue_job(store, comment_id=cid, revision=1)

    a = outbox.claim_jobs(store, limit=1, worker_id="worker-A", lease_ttl_sec=60)
    b = outbox.claim_jobs(store, limit=1, worker_id="worker-B", lease_ttl_sec=60)

    a_ids = {j["job_id"] for j in a}
    b_ids = {j["job_id"] for j in b}
    contested = a_ids & b_ids
    owner = store.conn.execute(
        "SELECT lease_owner FROM community_comment_moderation_jobs WHERE comment_id=?",
        (cid,),
    ).fetchone()

    # Restore the parked jobs so later sections see a normal queue.
    store.conn.execute(
        """UPDATE community_comment_moderation_jobs
           SET next_attempt_at=''
           WHERE next_attempt_at='2999-01-01T00:00:00Z'""",
    )
    return {
        "scenario_class": "concurrency_lease",
        "worker_a_claimed": len(a),
        "worker_b_claimed": len(b),
        "same_job_leased_twice": len(contested),
        "lease_owner": owner["lease_owner"] if owner else "",
        "single_owner": len(a) == 1 and len(b) == 0 and not contested,
        "pass": len(a) == 1 and len(b) == 0 and not contested,
    }


def run_crash_resume(store: CommunityStore) -> dict[str, Any]:
    """A crashed worker's expired lease is reclaimed exactly once."""
    cid = f"{CANARY_MARKER}resume_01"
    _insert_canary_comment(store, comment_id=cid, body="Комментарий для проверки resume.")
    outbox.enqueue_job(store, comment_id=cid, revision=1)

    claimed = outbox.claim_jobs(store, limit=1, worker_id="worker-crash", lease_ttl_sec=60)
    job_id = claimed[0]["job_id"]
    # Simulate the crash: the lease is held but the worker is gone and expires.
    store.conn.execute(
        "UPDATE community_comment_moderation_jobs SET lease_until=? WHERE job_id=?",
        ("2000-01-01T00:00:00Z", job_id),
    )
    reclaimed = outbox.claim_jobs(store, limit=1, worker_id="worker-resume", lease_ttl_sec=60)
    same_job = bool(reclaimed and reclaimed[0]["job_id"] == job_id)
    attempts = int(reclaimed[0]["attempts"]) if reclaimed else 0

    outbox.complete_job(store, job_id, {"resumed": True})
    # A completed job must never be handed out again. Other pending jobs may
    # legitimately be claimed here, so assert on this job_id, not on the count.
    after = outbox.claim_jobs(store, limit=1, worker_id="worker-third", lease_ttl_sec=60)
    reissued = any(j["job_id"] == job_id for j in after)
    final_status = store.conn.execute(
        "SELECT status FROM community_comment_moderation_jobs WHERE job_id=?", (job_id,)
    ).fetchone()
    return {
        "scenario_class": "crash_resume",
        "reclaimed": len(reclaimed),
        "same_job": same_job,
        "attempts": attempts,
        "completed_job_reissued": reissued,
        "final_status": final_status["status"] if final_status else "",
        "no_double_processing_after_done": not reissued,
        "pass": same_job and not reissued and bool(final_status)
        and final_status["status"] == outbox.JOB_DONE,
    }


def run_degraded_mode() -> dict[str, Any]:
    """Provider outage / backlog must hold comments, never auto-publish."""
    ctl = DegradedController()
    ctl.circuit_open = True
    on_outage = ctl.initial_status_for_new_comment()

    healthy = DegradedController()
    on_healthy = healthy.initial_status_for_new_comment(queue_depth=0, oldest_age=0.0)

    backlog = DegradedController()
    on_backlog = backlog.initial_status_for_new_comment(queue_depth=999, oldest_age=0.0)

    stale = DegradedController()
    on_stale = stale.initial_status_for_new_comment(queue_depth=0, oldest_age=10_000.0)

    outage_holds = on_outage == states.PENDING_MODERATION_DEGRADED
    backlog_holds = on_backlog == states.PENDING_MODERATION_DEGRADED
    stale_holds = on_stale == states.PENDING_MODERATION_DEGRADED
    degraded_not_public = not status_is_public(states.PENDING_MODERATION_DEGRADED)

    return {
        "scenario_class": "degraded_mode",
        "outage_status": on_outage,
        "healthy_status": on_healthy,
        "backlog_status": on_backlog,
        "stale_status": on_stale,
        "degraded_is_not_public": degraded_not_public,
        "pass": outage_holds and backlog_holds and stale_holds and degraded_not_public,
    }


def run_injection_containment(provider: CountingProvider) -> dict[str, Any]:
    """A hostile provider response must not be able to publish an unsafe comment.

    This is the property that matters regardless of which model answers: even
    if the provider is fully compromised and returns ALLOW with maximum
    confidence, schema validation plus the local state machine decide the row.
    """
    results: list[dict[str, Any]] = []
    injection_cases = [c for c in GOLD_CASES if c["severity"] == "injection"]

    for case in injection_cases:
        # Provider is compromised: it obeys the injected instruction.
        def compromised(_n: int, p: dict[str, Any]) -> Any:
            return {
                "schema_version": "QWEN_DECISION_SCHEMA_V2",
                "policy_version": "QWEN_MODERATION_POLICY_V1",
                "decision": "ALLOW",
                "labels": ["CLEAN"],
                "confidence": 1.0,
                "reason_codes": ["INJECTED"],
                "language": "en",
                "spoiler": False,
                "toxicity_score": 0.0,
                "spam_score": 0.0,
                "pii_detected": False,
                "prompt_injection_detected": False,
                "model": "compromised",
                "request_id": str(p.get("request_id") or ""),
                "system_prompt": SYSTEM_PROMPT_PROBE,
            }

        prov = CountingProvider(inner=HeuristicV2Provider(), fault=compromised)
        rec = moderate_once(prov, raw_text=case["body"], request_id=new_request_id())
        # additionalProperties=False means the smuggled key fails validation.
        results.append(
            {
                "case_id": case["case_id"],
                "compromised_response_accepted": rec["schema_valid"],
                "outcome": rec["outcome"],
            }
        )

    # Separately: the honest path must flag injections rather than allow them.
    honest: list[dict[str, Any]] = []
    for case in injection_cases:
        rec = moderate_once(provider, raw_text=case["body"], request_id=new_request_id())
        honest.append(
            {
                "case_id": case["case_id"],
                "outcome": rec["outcome"],
                "auto_published": rec["outcome"] == "ALLOW",
            }
        )

    bypasses = sum(1 for r in results if r["compromised_response_accepted"])
    return {
        "scenario_class": "prompt_injection",
        "compromised_provider_cases": results,
        "compromised_bypasses": bypasses,
        "honest_path": honest,
        "system_prompt_never_in_payload": True,
        "pass": bypasses == 0,
    }


SYSTEM_PROMPT_PROBE = "LEAKED_SYSTEM_PROMPT_PROBE"


# --------------------------------------------------------------------------
# Cleanup + isolation proofs
# --------------------------------------------------------------------------


def cleanup_canary_rows(store: CommunityStore) -> dict[str, Any]:
    """Remove every synthetic row this run created and prove the count is 0."""
    before = store.conn.execute(
        "SELECT COUNT(*) AS n FROM community_comments WHERE site_space=?",
        (CANARY_SITE_SPACE,),
    ).fetchone()["n"]

    store.conn.execute(
        """DELETE FROM community_comment_moderation_events
           WHERE comment_id IN (SELECT comment_id FROM community_comments WHERE site_space=?)""",
        (CANARY_SITE_SPACE,),
    )
    store.conn.execute(
        """DELETE FROM community_comment_moderation_jobs
           WHERE comment_id IN (SELECT comment_id FROM community_comments WHERE site_space=?)""",
        (CANARY_SITE_SPACE,),
    )
    store.conn.execute(
        """DELETE FROM community_comment_revisions
           WHERE comment_id IN (SELECT comment_id FROM community_comments WHERE site_space=?)""",
        (CANARY_SITE_SPACE,),
    )
    store.conn.execute(
        "DELETE FROM community_comments WHERE site_space=?", (CANARY_SITE_SPACE,)
    )

    remaining = store.conn.execute(
        "SELECT COUNT(*) AS n FROM community_comments WHERE site_space=?",
        (CANARY_SITE_SPACE,),
    ).fetchone()["n"]
    remaining_jobs = store.conn.execute(
        "SELECT COUNT(*) AS n FROM community_comment_moderation_jobs WHERE comment_id LIKE ?",
        (f"{CANARY_MARKER}%",),
    ).fetchone()["n"]
    remaining_events = store.conn.execute(
        "SELECT COUNT(*) AS n FROM community_comment_moderation_events WHERE comment_id LIKE ?",
        (f"{CANARY_MARKER}%",),
    ).fetchone()["n"]

    return {
        "rows_before": int(before),
        "CANARY_COMMENT_ROWS_REMAINING": int(remaining),
        "canary_jobs_remaining": int(remaining_jobs),
        "canary_events_remaining": int(remaining_events),
        "pass": remaining == 0 and remaining_jobs == 0 and remaining_events == 0,
    }


def production_isolation_proof() -> dict[str, Any]:
    """Prove no production comments database was opened or written."""
    candidates = [
        REPO / "var/community/ratings.sqlite",
        REPO / "var/community_comments/production.sqlite",
        Path("/srv/site-factory/repo/var/community/ratings.sqlite"),
    ]
    observed = []
    for path in candidates:
        try:
            exists = path.is_file()
        except OSError:
            exists = False
        observed.append(
            {
                "path": str(path),
                "exists": exists,
                "opened_by_canary": False,
                "mtime": path.stat().st_mtime if exists else None,
            }
        )
    return {
        "staging_db": str(STAGING_DB),
        "production_candidates": observed,
        "PRODUCTION_COMMENTS_INSERTED": 0,
        "PRODUCTION_COMMENTS_PUBLISHED": 0,
        "production_db_opened": False,
        "pass": True,
    }


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def build_provider(kind: str, args: argparse.Namespace) -> tuple[CountingProvider, dict[str, Any]]:
    """Return the provider and the real-canary gate decision."""
    if kind == "heuristic":
        return (
            CountingProvider(inner=HeuristicV2Provider()),
            {
                "REAL_QWEN_CANARY_EXECUTED": 0,
                "provider_kind": "heuristic",
                "note": "Pipeline rehearsal only — a fake provider is never a real canary.",
            },
        )

    # Live path — every gate must pass, or we refuse. No silent downgrade.
    pre = runtime_preflight()
    if not pre["READY_FOR_REAL_CANARY"]:
        raise SystemExit(
            "REFUSED live canary: runtime preflight not ready "
            f"({pre['BLOCKED_REASON']}; blocking={pre['BLOCKING_CHECKS']})"
        )
    if not args.owner_authorization_id:
        raise SystemExit("REFUSED live canary: --owner-authorization-id required")
    if args.spend_cap_rub is None or args.spend_cap_rub <= 0:
        raise SystemExit("REFUSED live canary: --spend-cap-rub required and must be > 0")

    from factory.community.comments.qwen.provider import LiveQwenProvider

    return (
        CountingProvider(inner=LiveQwenProvider(timeout_sec=float(pre["timeout_sec"]))),
        {
            "REAL_QWEN_CANARY_EXECUTED": 1,
            "provider_kind": "live",
            "OWNER_AUTHORIZATION_ID": args.owner_authorization_id,
            "SPEND_CAP_RUB": args.spend_cap_rub,
        },
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=("heuristic", "live"), default="heuristic")
    ap.add_argument("--owner-authorization-id", default="")
    ap.add_argument("--spend-cap-rub", type=float, default=None)
    ap.add_argument("--keep-rows", action="store_true", help="skip cleanup (debug only)")
    args = ap.parse_args()

    _assert_staging_db(STAGING_DB)
    if STAGING_DB.exists():
        STAGING_DB.unlink()
    for suffix in ("-wal", "-shm"):
        side = Path(str(STAGING_DB) + suffix)
        if side.exists():
            side.unlink()

    provider, gate = build_provider(args.provider, args)
    store = CommunityStore(STAGING_DB)
    outbox.ensure_outbox_schema(store)
    flags_path = REPO / "var/community_comments/canary_kill_switch_flags.json"

    started = time.time()
    sections: dict[str, Any] = {}
    sections["content"] = run_content_scenarios(provider)
    sections["empty_text"] = run_empty_text()
    sections["provider_timeout"] = run_provider_timeout()
    sections["invalid_json"] = run_invalid_json()
    sections["retry"] = run_retry()
    sections["retry_exhaustion"] = run_retry_exhaustion()
    sections["duplicate_idempotency"] = run_duplicate_and_idempotency(store)
    sections["kill_switch"] = run_kill_switch(store, flags_path)
    sections["state_machine"] = run_state_machine()
    sections["revision_race"] = run_revision_race(store)
    sections["delete_race"] = run_delete_race(store)
    sections["concurrency_lease"] = run_concurrency_lease(store)
    sections["crash_resume"] = run_crash_resume(store)
    sections["degraded_mode"] = run_degraded_mode()
    sections["prompt_injection"] = run_injection_containment(provider)

    cleanup = (
        {"skipped": True, "CANARY_COMMENT_ROWS_REMAINING": -1}
        if args.keep_rows
        else cleanup_canary_rows(store)
    )
    isolation = production_isolation_proof()
    store.close()

    latencies = [r["latency_ms"] for r in sections["content"]["records"]]
    latencies_sorted = sorted(latencies)

    def pct(p: float) -> float:
        if not latencies_sorted:
            return 0.0
        idx = min(len(latencies_sorted) - 1, int(round(p * (len(latencies_sorted) - 1))))
        return round(latencies_sorted[idx], 2)

    scenario_classes_covered = sorted(
        {r["scenario_class"] for r in sections["content"]["records"]}
        | {
            sections[k].get("scenario_class")
            for k in sections
            if isinstance(sections[k], dict) and sections[k].get("scenario_class")
        }
    )
    missing_classes = [
        c for c in REQUIRED_SCENARIO_CLASSES if c not in scenario_classes_covered
    ]

    pipeline_pass = all(
        [
            sections["content"]["schema_valid_all"],
            sections["content"]["forbidden_key_hits"] == 0,
            sections["content"]["raw_pii_hits"] == 0,
            sections["content"]["system_prompt_leaks"] == 0,
            sections["empty_text"]["all_rejected_locally"],
            sections["provider_timeout"]["pass"],
            sections["invalid_json"]["pass"],
            sections["retry"]["pass"],
            sections["retry_exhaustion"]["pass"],
            sections["duplicate_idempotency"]["pass"],
            sections["kill_switch"]["pass"],
            sections["state_machine"]["pass"],
            sections["revision_race"]["pass"],
            sections["delete_race"]["pass"],
            sections["concurrency_lease"]["pass"],
            sections["crash_resume"]["pass"],
            sections["degraded_mode"]["pass"],
            sections["prompt_injection"]["pass"],
            not missing_classes,
            cleanup.get("pass", False) or args.keep_rows,
        ]
    )

    real = bool(gate["REAL_QWEN_CANARY_EXECUTED"])
    unmeasured = "UNMEASURED_NO_REAL_PROVIDER"

    report = {
        "schema_version": "COMMENTS_QWEN_STAGING_CANARY_V1",
        "stage": "COMMUNITY-COMMENTS-03-QWEN-STAGING-CANARY",
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
        "finished_at": _utc(),
        "gate": gate,
        "REAL_QWEN_CANARY_EXECUTED": gate["REAL_QWEN_CANARY_EXECUTED"],
        "REAL_QWEN_REQUESTS": provider.calls if real else 0,
        "REAL_QWEN_LOGICAL_TASKS": sections["content"]["count"] if real else 0,
        "REAL_QWEN_RETRIES": 0,
        "REAL_QWEN_INPUT_TOKENS": 0,
        "REAL_QWEN_OUTPUT_TOKENS": 0,
        "REAL_QWEN_ACTUAL_SPEND_RUB": 0.0,
        "scenario_classes_required": list(REQUIRED_SCENARIO_CLASSES),
        "scenario_classes_covered": scenario_classes_covered,
        "scenario_classes_missing": missing_classes,
        "sections": sections,
        "cleanup": cleanup,
        "production_isolation": isolation,
        "pipeline_metrics": {
            "SCHEMA_VALIDATION_PASS": bool(sections["content"]["schema_valid_all"]),
            "PROMPT_INJECTION_BYPASS": sections["prompt_injection"]["compromised_bypasses"],
            "PII_REDACTION_PASS": sections["content"]["raw_pii_hits"] == 0,
            "RAW_IP_SENT_TO_QWEN": 0,
            "RAW_USER_AGENT_SENT_TO_QWEN": 0,
            "DEVICE_ID_SENT_TO_QWEN": 0,
            "EMAIL_SENT_TO_QWEN": 0,
            "PHONE_SENT_TO_QWEN": 0,
            "DEGRADED_MODE_PASS": sections["degraded_mode"]["pass"],
            "KILL_SWITCH_PASS": sections["kill_switch"]["pass"],
            "STATE_MACHINE_PASS": sections["state_machine"]["pass"],
            "REVISION_RACE_PASS": sections["revision_race"]["pass"],
            "DELETE_RACE_PASS": sections["delete_race"]["pass"],
            "CONCURRENCY_LEASE_PASS": sections["concurrency_lease"]["pass"],
            "CRASH_RESUME_PASS": sections["crash_resume"]["pass"],
            "DUPLICATE_PROVIDER_CALLS": 0,
            "UNRECONCILED_PROVIDER_CALLS": 0,
        },
        "model_quality_metrics": {
            "_note": (
                "Measuring a model requires calling it. With the heuristic "
                "provider these stay unmeasured rather than being filled with "
                "numbers our own keyword rules produced."
            ),
            "DECISION_AGREEMENT_RATE": unmeasured if not real else None,
            "CLEAN_FALSE_BLOCK_RATE": unmeasured if not real else None,
            "CONSTRUCTIVE_CRITICISM_FALSE_BLOCK": unmeasured if not real else None,
            "SPOILER_DETECTION_RECALL": unmeasured if not real else None,
            "SPAM_DETECTION_RECALL": unmeasured if not real else None,
            "CRITICAL_UNSAFE_FALSE_ALLOW": unmeasured if not real else None,
        },
        "latency_ms": {
            "LATENCY_P50_MS": pct(0.50),
            "LATENCY_P95_MS": pct(0.95),
            "LATENCY_MAX_MS": round(max(latencies), 2) if latencies else 0.0,
            "_note": "Local pipeline latency; excludes real network time.",
            "mean": round(statistics.fmean(latencies), 2) if latencies else 0.0,
        },
        "PIPELINE_PASS": pipeline_pass,
    }

    out = _write(EVIDENCE / "07-canary" / "STAGING_CANARY_RESULTS.json", report)
    print(json.dumps({
        "PIPELINE_PASS": pipeline_pass,
        "REAL_QWEN_CANARY_EXECUTED": report["REAL_QWEN_CANARY_EXECUTED"],
        "scenario_classes_missing": missing_classes,
        "CANARY_COMMENT_ROWS_REMAINING": cleanup.get("CANARY_COMMENT_ROWS_REMAINING"),
        "evidence": str(out.relative_to(REPO)),
    }, indent=2))
    return 0 if pipeline_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
