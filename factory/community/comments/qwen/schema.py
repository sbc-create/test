"""Strict JSON Schema for Qwen moderation decisions (goal §12)."""

from __future__ import annotations

from typing import Any

import jsonschema

ALLOWED_ACTIONS = frozenset(
    {
        "ALLOW",
        "ALLOW_COLLAPSED_SPOILER",
        "HIDE_HIGH_CONFIDENCE",
        "HOLD_FOR_REVIEW",
    }
)

ALLOWED_LABELS = frozenset(
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

QWEN_DECISION_SCHEMA_V1: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "qwen-decision-schema-v1",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version",
        "policy_version",
        "action",
        "labels",
        "confidence",
        "spoiler_detected",
        "language",
        "reason_codes",
        "needs_human_review",
        "model",
        "prompt_digest",
    ],
    "properties": {
        "schema_version": {"type": "string", "const": "QWEN_DECISION_SCHEMA_V1"},
        "policy_version": {"type": "string", "minLength": 1},
        "action": {"type": "string", "enum": sorted(ALLOWED_ACTIONS)},
        "labels": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string", "enum": sorted(ALLOWED_LABELS)},
            "uniqueItems": True,
        },
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "spoiler_detected": {"type": "boolean"},
        "language": {"type": "string", "minLength": 2, "maxLength": 16},
        "reason_codes": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
        },
        "needs_human_review": {"type": "boolean"},
        "model": {"type": "string", "minLength": 1},
        "prompt_digest": {"type": "string", "minLength": 8, "maxLength": 128},
    },
}


def _echoes_comment(decision: dict[str, Any], comment_text: str | None) -> bool:
    """Reject responses that echo the full user comment (prompt-injection / leak)."""
    if not comment_text:
        return False
    needle = comment_text.strip()
    if len(needle) < 12:
        return False
    blob = " ".join(str(v) for v in decision.values() if isinstance(v, (str, list)))
    # Also scan nested lists of strings
    for v in decision.values():
        if isinstance(v, list):
            blob += " " + " ".join(str(x) for x in v)
        elif isinstance(v, str):
            blob += " " + v
    return needle in blob


def validate_decision(
    decision: dict[str, Any],
    *,
    comment_text: str | None = None,
) -> dict[str, Any]:
    """Validate against QWEN_DECISION_SCHEMA_V1.

    Returns ``{"ok": True, "errors": []}`` or ``{"ok": False, "errors": [...]}``.
    """
    errors: list[str] = []
    if not isinstance(decision, dict):
        return {"ok": False, "errors": ["decision must be an object"]}
    validator = jsonschema.Draft202012Validator(QWEN_DECISION_SCHEMA_V1)
    for err in sorted(validator.iter_errors(decision), key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in err.path) or "<root>"
        errors.append(f"{path}: {err.message}")
    if decision.get("action") not in ALLOWED_ACTIONS and "action" not in " ".join(errors):
        errors.append(f"action not allowed: {decision.get('action')}")
    labels = decision.get("labels") or []
    if isinstance(labels, list):
        bad = [x for x in labels if x not in ALLOWED_LABELS]
        if bad:
            errors.append(f"unknown labels: {bad}")
    # Forbidden: echo full comment text anywhere in the response payload
    if _echoes_comment(decision, comment_text):
        errors.append("response must not echo full comment text")
    # Extra hard reject: any property named like comment body
    for forbidden_key in ("comment_text", "body", "original_text", "user_message"):
        if forbidden_key in decision:
            errors.append(f"forbidden field: {forbidden_key}")
    return {"ok": not errors, "errors": errors}
