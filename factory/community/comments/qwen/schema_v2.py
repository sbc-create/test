"""Qwen decision schema V2 (COMMUNITY-COMMENTS-03 staging canary contract).

Provider returns classification only. Local policy engine maps decisions
to comment states after schema/correlation/revision/idempotency checks.
"""

from __future__ import annotations

from typing import Any

import jsonschema

ALLOWED_DECISIONS_V2 = frozenset(
    {
        "ALLOW",
        "ALLOW_SPOILER_COLLAPSED",
        "HIDE",
        "QUARANTINE",
        "NEEDS_REVIEW",
    }
)

# Map V2 decision → Stage02 action used by apply_action_to_status
V2_TO_V1_ACTION = {
    "ALLOW": "ALLOW",
    "ALLOW_SPOILER_COLLAPSED": "ALLOW_COLLAPSED_SPOILER",
    "HIDE": "HIDE_HIGH_CONFIDENCE",
    "QUARANTINE": "HOLD_FOR_REVIEW",
    "NEEDS_REVIEW": "HOLD_FOR_REVIEW",
}

FORBIDDEN_EXTRA_KEYS = frozenset(
    {
        "sql",
        "url",
        "callback",
        "action_endpoint",
        "tool_call",
        "tools",
        "shell",
        "exec",
    }
)

ALLOWED_LABELS_V2 = frozenset(
    {
        "CLEAN",
        "SPOILER",
        "SPAM",
        "ADVERTISEMENT",
        "OFF_TOPIC",
        "INSULT",
        "HARASSMENT",
        "HATE",
        "THREAT",
        "SEXUAL_CONTENT",
        "SEXUAL_CONTENT_MINORS",
        "SELF_HARM",
        "PERSONAL_DATA",
        "PIRACY_LINK",
        "MALWARE_LINK",
        "LONG_COPYRIGHT_QUOTE",
        "PROMPT_INJECTION",
        "UNKNOWN",
    }
)

QWEN_DECISION_SCHEMA_V2: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "qwen-decision-schema-v2",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version",
        "policy_version",
        "decision",
        "labels",
        "confidence",
        "reason_codes",
        "language",
        "spoiler",
        "toxicity_score",
        "spam_score",
        "pii_detected",
        "prompt_injection_detected",
        "model",
        "request_id",
    ],
    "properties": {
        "schema_version": {"type": "string", "const": "QWEN_DECISION_SCHEMA_V2"},
        "policy_version": {"type": "string", "minLength": 1},
        "decision": {"type": "string", "enum": sorted(ALLOWED_DECISIONS_V2)},
        "labels": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string", "enum": sorted(ALLOWED_LABELS_V2)},
            "uniqueItems": True,
        },
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "reason_codes": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
        },
        "language": {"type": "string", "minLength": 2, "maxLength": 16},
        "spoiler": {"type": "boolean"},
        "toxicity_score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "spam_score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "pii_detected": {"type": "boolean"},
        "prompt_injection_detected": {"type": "boolean"},
        "model": {"type": "string", "minLength": 1},
        "request_id": {"type": "string", "minLength": 8, "maxLength": 128},
        "prompt_digest": {"type": "string", "minLength": 8, "maxLength": 128},
    },
}


def normalize_v2_to_v1(decision_v2: dict[str, Any]) -> dict[str, Any]:
    """Convert a validated V2 decision into Stage02 V1 action shape for apply()."""
    decision = str(decision_v2.get("decision") or "")
    action = V2_TO_V1_ACTION.get(decision)
    if not action:
        raise ValueError(f"unknown V2 decision: {decision}")
    return {
        "schema_version": "QWEN_DECISION_SCHEMA_V1",
        "policy_version": decision_v2.get("policy_version") or "",
        "action": action,
        "labels": list(decision_v2.get("labels") or ["UNKNOWN"]),
        "confidence": float(decision_v2.get("confidence") or 0.0),
        "spoiler_detected": bool(decision_v2.get("spoiler")),
        "language": str(decision_v2.get("language") or "und"),
        "reason_codes": list(decision_v2.get("reason_codes") or []),
        "needs_human_review": decision in ("NEEDS_REVIEW", "QUARANTINE")
        or bool(decision_v2.get("prompt_injection_detected"))
        or bool(decision_v2.get("pii_detected")),
        "model": str(decision_v2.get("model") or ""),
        "prompt_digest": str(
            decision_v2.get("prompt_digest") or decision_v2.get("request_id") or "missing"
        ),
        # Keep V2 provenance for admin/audit (stripped before public DTO)
        "_v2": {
            "decision": decision,
            "request_id": decision_v2.get("request_id"),
            "toxicity_score": decision_v2.get("toxicity_score"),
            "spam_score": decision_v2.get("spam_score"),
            "pii_detected": decision_v2.get("pii_detected"),
            "prompt_injection_detected": decision_v2.get("prompt_injection_detected"),
        },
    }


def validate_decision_v2(
    decision: dict[str, Any],
    *,
    expected_request_id: str | None = None,
    comment_text: str | None = None,
    max_bytes: int = 32_768,
) -> dict[str, Any]:
    """Strict V2 validation. Returns {ok, errors, decision?}."""
    errors: list[str] = []
    if not isinstance(decision, dict):
        return {"ok": False, "errors": ["not_an_object"]}
    raw_size = len(str(decision).encode("utf-8", errors="replace"))
    if raw_size > max_bytes:
        errors.append("response_too_large")
    bad_keys = sorted(set(decision) & FORBIDDEN_EXTRA_KEYS)
    if bad_keys:
        errors.append(f"forbidden_keys:{','.join(bad_keys)}")
    try:
        jsonschema.validate(instance=decision, schema=QWEN_DECISION_SCHEMA_V2)
    except jsonschema.ValidationError as exc:
        errors.append(f"schema:{exc.message}")
    if expected_request_id is not None:
        got = str(decision.get("request_id") or "")
        if got != expected_request_id:
            errors.append("request_id_mismatch")
    if comment_text:
        needle = comment_text.strip()
        if len(needle) >= 12:
            blob = " ".join(str(v) for v in decision.values() if isinstance(v, (str, list)))
            if needle in blob:
                errors.append("echoes_full_comment")
    if errors:
        return {"ok": False, "errors": errors}
    return {"ok": True, "errors": [], "decision": decision}
