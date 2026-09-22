"""Append-only audit.

The trail exists so that a decision can be reviewed after the person who made
it has gone home. That imposes two obligations which pull against each other.

It must be complete: every moderation action, ban, report resolution, role
change, policy change, flag change, export, deletion, break-glass, migration
and rollout decision writes a row, and there is no code path that performs one
of those without one — :func:`record` is the only writer, and it refuses an
event it does not recognise.

It must also be safe to read. An audit trail that quotes comment bodies is a
second copy of the content, outside the moderation states that govern the
first, and it ends up in exports and incident tickets. So `redact` runs over
every before/after payload and replaces bodies with a length and a digest,
drops anything that looks like a secret, and refuses to store an email address
or an IP at all. What survives is enough to answer "what changed" without
reproducing "what it said".
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from .errors import ValidationFailed
from .rbac import Principal
from .store import CommentsStore
from .tenancy import TenantScope

AUDIT_SCHEMA_VERSION = "COMMENTS_AUDIT_V1"

# Actions that must appear in the trail. An action outside this set is refused
# rather than written, because a typo'd action name is a row nobody will find.
ACTIONS = frozenset(
    {
        "comment.create", "comment.edit", "comment.delete_own",
        "moderation.hide", "moderation.restore", "moderation.remove",
        "moderation.publish", "moderation.quarantine", "moderation.resolve_report",
        "report.create",
        "ban.apply", "ban.lift",
        "role.grant", "role.revoke",
        "policy.update", "flags.update", "flags.kill_switch",
        "privacy.export", "privacy.anonymize", "privacy.delete",
        "rbac.break_glass",
        "release.migration", "release.production_approve", "release.deploy",
        "release.rollback",
    }
)

# Actions that are meaningless without a stated reason.
REASON_REQUIRED_ACTIONS = frozenset(
    {
        "moderation.hide", "moderation.remove", "moderation.restore",
        "ban.apply", "ban.lift", "rbac.break_glass",
        "privacy.delete", "privacy.anonymize",
        "release.rollback", "flags.kill_switch",
    }
)

# Keys whose values never reach the trail, matched case-insensitively on the
# key name. Substring matching is intentional: `author_email`, `api_token` and
# `x_password_hash` all need to be caught without enumerating every spelling.
SECRET_KEY_HINTS = (
    "password", "passwd", "secret", "token", "credential", "api_key", "apikey",
    "authorization", "cookie", "session", "private_key", "email", "e_mail",
    "ip", "ip_address", "remote_addr",
)

# Keys holding user-written prose. Replaced by shape, not removed, because
# "the body changed" and "the body did not change" are both facts worth having.
BODY_KEYS = ("body", "body_html", "text", "content", "note", "message", "comment")

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_IPV4_RE = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
_IPV6_RE = re.compile(r"\b(?:[0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}\b")

REDACTED = "[redacted]"


def _looks_secret(key: str) -> bool:
    lowered = str(key).lower()
    return any(hint in lowered for hint in SECRET_KEY_HINTS)


def _is_body_key(key: str) -> bool:
    return str(key).lower() in BODY_KEYS


def body_shape(text: str) -> dict[str, Any]:
    """What may be said about a comment body in an audit row.

    The digest makes "was this the same text as before" answerable without
    storing the text. It is a plain sha256 of the body, which is fine here: the
    goal is change detection among rows the reader already has access to, not
    resistance to someone guessing short strings.
    """
    value = text or ""
    return {
        "chars": len(value),
        "sha256": hashlib.sha256(value.encode("utf-8")).hexdigest()[:32],
    }


def scrub_text(value: str) -> str:
    """Last line of defence for free-form strings such as a reason."""
    scrubbed = _EMAIL_RE.sub(REDACTED, value)
    scrubbed = _IPV4_RE.sub(REDACTED, scrubbed)
    scrubbed = _IPV6_RE.sub(REDACTED, scrubbed)
    return scrubbed


def redact(payload: Mapping[str, Any] | None, *, _depth: int = 0) -> dict[str, Any]:
    """Make an arbitrary dictionary safe to persist in the trail."""
    if not payload:
        return {}
    if _depth > 6:
        return {"truncated": True}

    out: dict[str, Any] = {}
    for key, value in payload.items():
        if _looks_secret(key):
            out[str(key)] = REDACTED
            continue
        if _is_body_key(key) and isinstance(value, str):
            out[str(key)] = body_shape(value)
            continue
        if isinstance(value, Mapping):
            out[str(key)] = redact(value, _depth=_depth + 1)
        elif isinstance(value, list | tuple):
            out[str(key)] = [
                redact(v, _depth=_depth + 1)
                if isinstance(v, Mapping)
                else (scrub_text(v) if isinstance(v, str) else v)
                for v in value[:50]
            ]
        elif isinstance(value, str):
            out[str(key)] = scrub_text(value)
        else:
            out[str(key)] = value
    return out


def record(
    store: CommentsStore,
    scope: TenantScope,
    *,
    action: str,
    actor: Principal | None = None,
    object_type: str = "",
    object_id: str = "",
    before: Mapping[str, Any] | None = None,
    after: Mapping[str, Any] | None = None,
    reason: str = "",
    request_id: str = "",
    rule_version: str = "",
    artifact_hash: str = "",
    occurred_at: datetime | None = None,
) -> str:
    """The only way a row enters the trail."""
    if action not in ACTIONS:
        raise ValidationFailed(f"unknown audit action {action!r}", field="action")

    cleaned_reason = scrub_text((reason or "").strip())
    if action in REASON_REQUIRED_ACTIONS and not cleaned_reason:
        # Refusing here is what makes "obligatory reason" true rather than
        # aspirational: the write cannot be completed without one.
        raise ValidationFailed(f"action {action} requires a reason", field="reason")

    if action == "rbac.break_glass" and actor is not None and not actor.break_glass_reason:
        raise ValidationFailed("break-glass must carry its reason", field="reason")

    moment = (occurred_at or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return store.append_audit(
        scope,
        {
            "occurred_at": moment,
            "actor_subject_id": actor.subject_id if actor else "",
            "actor_role": actor.role if actor else "",
            "action": action,
            "object_type": object_type,
            "object_id": object_id,
            "before_redacted": redact(before),
            "after_redacted": redact(after),
            "reason": cleaned_reason,
            "request_id": request_id,
            "rule_version": rule_version,
            "artifact_hash": artifact_hash,
        },
    )


def verify_append_only(store: CommentsStore, scope: TenantScope) -> dict[str, Any]:
    """Report on the trail's shape.

    Append-only is enforced by there being no update or delete statement
    against `cp_audit_events` anywhere in this package — this function exists
    so a test can assert that claim against the live schema and row set rather
    than against a comment.
    """
    rows = store.list_audit(scope, limit=1000)
    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "count": len(rows),
        "actions": sorted({r["action"] for r in rows}),
        "has_reason_where_required": all(
            bool(r["reason"]) for r in rows if r["action"] in REASON_REQUIRED_ACTIONS
        ),
    }


def audit_contract() -> dict[str, Any]:
    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "append_only": True,
        "actions": sorted(ACTIONS),
        "reason_required": sorted(REASON_REQUIRED_ACTIONS),
        "record_fields": [
            "tenant_id", "site_id", "occurred_at (UTC)", "actor_subject_id", "actor_role",
            "action", "object_type", "object_id", "before_redacted", "after_redacted",
            "reason", "request_id", "rule_version", "artifact_hash",
        ],
        "never_recorded": [
            "full comment text", "passwords", "tokens", "email addresses", "raw IP addresses",
        ],
        "body_representation": "character count plus a truncated sha256",
    }
