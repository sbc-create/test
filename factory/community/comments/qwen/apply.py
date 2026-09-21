"""Apply a validated Qwen decision to a comment row (idempotent, revision-safe)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from factory.community.comments import states
from factory.community.comments.qwen.policy import apply_action_to_status
from factory.community.comments.qwen.schema import validate_decision
from factory.community.store import CommunityStore


class ApplyDecisionError(ValueError):
    code = "ApplyDecisionError"


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def apply_decision(
    store: CommunityStore,
    comment_id: str,
    revision: int,
    decision: dict[str, Any],
    *,
    actor_role: str = "qwen",
    actor_identity_id: str = "qwen:postmod",
) -> dict[str, Any]:
    """Apply moderation decision with idempotency and safety guards.

    Refuses when:
    - revision mismatches current comment.version
    - comment already DELETED_BY_AUTHOR (or Stage01 DELETED_BY_USER)
    - decision fails schema validation
    """
    # Underscore-prefixed keys are our own provenance annotations (e.g. the
    # "_v2" block normalize_v2_to_v1 attaches, and the "_applied_*" stamps
    # written below) — never provider-supplied. The wire contract stays strict:
    # a live provider response is validated unstripped in moderate_comment, so
    # a provider cannot smuggle keys past the schema by underscore-prefixing.
    # Here we validate the decision proper and carry provenance alongside.
    decision_core = {k: v for k, v in decision.items() if not k.startswith("_")}

    check = validate_decision(decision_core)
    if not check["ok"]:
        raise ApplyDecisionError(f"invalid decision: {check['errors']}")

    with store._lock:
        row = store.conn.execute(
            "SELECT * FROM community_comments WHERE comment_id=?", (comment_id,)
        ).fetchone()
        if not row:
            raise ApplyDecisionError("comment not found")
        comment = dict(row)
        current_version = int(comment.get("version") or 1)
        if int(revision) != current_version:
            raise ApplyDecisionError(
                f"revision mismatch: job={revision} current={current_version}"
            )

        prior = comment.get("moderation_status") or comment.get("status") or ""
        try:
            prior_norm = states.normalize_status(prior)
        except states.InvalidTransition:
            prior_norm = prior

        if prior_norm == states.DELETED_BY_AUTHOR or prior in (
            "DELETED_BY_USER",
            states.DELETED_BY_AUTHOR,
        ):
            raise ApplyDecisionError("refused: comment deleted by author")

        # Idempotency: same decision already applied for this revision
        existing = comment.get("qwen_decision_json") or ""
        if existing:
            try:
                prev = json.loads(existing)
            except json.JSONDecodeError:
                prev = {}
            if (
                prev.get("prompt_digest") == decision.get("prompt_digest")
                and prev.get("action") == decision.get("action")
                and prev.get("_applied_revision") == current_version
            ):
                return {
                    "applied": False,
                    "idempotent": True,
                    "comment_id": comment_id,
                    "revision": current_version,
                    "status": prior_norm,
                }

        mapped = apply_action_to_status(
            str(decision.get("action") or ""),
            list(decision.get("labels") or []),
            float(decision.get("confidence") or 0.0),
        )
        new_status = mapped["new_status"]
        # Only transition if allowed; otherwise hold
        try:
            states.validate_transition(prior_norm, new_status)
        except states.InvalidTransition:
            new_status = states.HELD_FOR_REVIEW
            mapped = {
                **mapped,
                "new_status": new_status,
                "reason": "transition_fallback_hold",
                "reason_codes": list(mapped.get("reason_codes") or []) + ["TRANSITION_FALLBACK"],
            }

        now = _utc()
        decision_store = dict(decision)
        decision_store["_applied_revision"] = current_version
        decision_store["_applied_at"] = now
        spoiler_collapsed = 1 if mapped.get("spoiler_collapsed") else 0

        store.conn.execute(
            """UPDATE community_comments
               SET status=?,
                   moderation_status=?,
                   spoiler_collapsed=?,
                   spoiler=CASE WHEN ?=1 THEN 1 ELSE spoiler END,
                   qwen_decision_json=?,
                   last_moderation_at=?,
                   moderation_reason=?,
                   updated_at=?
               WHERE comment_id=?""",
            (
                new_status,
                new_status,
                spoiler_collapsed,
                spoiler_collapsed,
                json.dumps(decision_store, ensure_ascii=False, sort_keys=True),
                now,
                mapped.get("reason") or "",
                now,
                comment_id,
            ),
        )
        store.conn.execute(
            """INSERT INTO community_comment_moderation_events
               (event_id, comment_id, action, actor_role, actor_identity_id,
                reason_code, detail, prior_status, new_status, created_at,
                policy_version, model, prompt_digest, decision_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                _new_id("cme"),
                comment_id,
                mapped.get("effective_action") or decision.get("action") or "QWEN",
                actor_role,
                actor_identity_id,
                ",".join(mapped.get("reason_codes") or [])[:200],
                mapped.get("reason") or "",
                prior_norm,
                new_status,
                now,
                str(decision.get("policy_version") or mapped.get("policy_version") or ""),
                str(decision.get("model") or ""),
                str(decision.get("prompt_digest") or ""),
                json.dumps(decision_store, ensure_ascii=False, sort_keys=True),
            ),
        )
        return {
            "applied": True,
            "idempotent": False,
            "comment_id": comment_id,
            "revision": current_version,
            "prior_status": prior_norm,
            "new_status": new_status,
            "mapped": mapped,
        }
