"""Comment lifecycle state machine (COMMUNITY-COMMENTS-02).

Statuses from goal §5. Stage01 aliases kept for migration compatibility.
Physical body deletion is never a normal transition — soft-delete states
retain the body in the DB.
"""

from __future__ import annotations

from typing import Any

# --- Canonical postmod statuses (goal §5) ---
PREFLIGHT_REJECTED = "PREFLIGHT_REJECTED"
PUBLISHED_UNREVIEWED = "PUBLISHED_UNREVIEWED"
VISIBLE_QWEN_APPROVED = "VISIBLE_QWEN_APPROVED"
VISIBLE_SPOILER_COLLAPSED = "VISIBLE_SPOILER_COLLAPSED"
HIDDEN_QWEN_HIGH_CONFIDENCE = "HIDDEN_QWEN_HIGH_CONFIDENCE"
HELD_FOR_REVIEW = "HELD_FOR_REVIEW"
HIDDEN_BY_ADMIN = "HIDDEN_BY_ADMIN"
DELETED_BY_AUTHOR = "DELETED_BY_AUTHOR"
DELETED_BY_ADMIN = "DELETED_BY_ADMIN"
PENDING_MODERATION_DEGRADED = "PENDING_MODERATION_DEGRADED"

COMMENT_STATUSES_V2 = frozenset(
    {
        PREFLIGHT_REJECTED,
        PUBLISHED_UNREVIEWED,
        VISIBLE_QWEN_APPROVED,
        VISIBLE_SPOILER_COLLAPSED,
        HIDDEN_QWEN_HIGH_CONFIDENCE,
        HELD_FOR_REVIEW,
        HIDDEN_BY_ADMIN,
        DELETED_BY_AUTHOR,
        DELETED_BY_ADMIN,
        PENDING_MODERATION_DEGRADED,
    }
)

# Stage01 aliases → canonical V2 (migration / dual-read)
STAGE01_STATUS_ALIASES: dict[str, str] = {
    "PENDING": HELD_FOR_REVIEW,
    "PUBLISHED": VISIBLE_QWEN_APPROVED,
    "QUARANTINED": HELD_FOR_REVIEW,
    "REJECTED": PREFLIGHT_REJECTED,
    "DELETED_BY_USER": DELETED_BY_AUTHOR,
    "REMOVED_BY_MODERATOR": DELETED_BY_ADMIN,
    "DRAFT": PENDING_MODERATION_DEGRADED,
}

# Public surfaces (publication flag still gates production exposure)
PUBLIC_VISIBLE_STATUSES = frozenset(
    {
        PUBLISHED_UNREVIEWED,
        VISIBLE_QWEN_APPROVED,
        VISIBLE_SPOILER_COLLAPSED,
    }
)

# Author can still see these when public cannot
AUTHOR_VISIBLE_EXTRA = frozenset(
    {
        PENDING_MODERATION_DEGRADED,
        HELD_FOR_REVIEW,
        HIDDEN_QWEN_HIGH_CONFIDENCE,
        HIDDEN_BY_ADMIN,
        DELETED_BY_AUTHOR,
        PREFLIGHT_REJECTED,
    }
)

AUTHOR_VISIBLE_STATUSES = PUBLIC_VISIBLE_STATUSES | AUTHOR_VISIBLE_EXTRA

# Soft-delete / hide: body retained in DB (never hard-deleted by automation)
SOFT_DELETE_STATUSES = frozenset(
    {
        HIDDEN_QWEN_HIGH_CONFIDENCE,
        HELD_FOR_REVIEW,
        HIDDEN_BY_ADMIN,
        DELETED_BY_AUTHOR,
        DELETED_BY_ADMIN,
        PENDING_MODERATION_DEGRADED,
        PREFLIGHT_REJECTED,
    }
)

TERMINAL_STATUSES = frozenset({DELETED_BY_ADMIN, PREFLIGHT_REJECTED})

# Allowed transitions: from → frozenset(to)
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    PREFLIGHT_REJECTED: frozenset(),
    PUBLISHED_UNREVIEWED: frozenset(
        {
            VISIBLE_QWEN_APPROVED,
            VISIBLE_SPOILER_COLLAPSED,
            HIDDEN_QWEN_HIGH_CONFIDENCE,
            HELD_FOR_REVIEW,
            HIDDEN_BY_ADMIN,
            DELETED_BY_AUTHOR,
            DELETED_BY_ADMIN,
        }
    ),
    PENDING_MODERATION_DEGRADED: frozenset(
        {
            PUBLISHED_UNREVIEWED,
            VISIBLE_QWEN_APPROVED,
            VISIBLE_SPOILER_COLLAPSED,
            HIDDEN_QWEN_HIGH_CONFIDENCE,
            HELD_FOR_REVIEW,
            HIDDEN_BY_ADMIN,
            DELETED_BY_AUTHOR,
            DELETED_BY_ADMIN,
        }
    ),
    VISIBLE_QWEN_APPROVED: frozenset(
        {
            VISIBLE_SPOILER_COLLAPSED,
            HIDDEN_QWEN_HIGH_CONFIDENCE,
            HELD_FOR_REVIEW,
            HIDDEN_BY_ADMIN,
            DELETED_BY_AUTHOR,
            DELETED_BY_ADMIN,
        }
    ),
    VISIBLE_SPOILER_COLLAPSED: frozenset(
        {
            VISIBLE_QWEN_APPROVED,
            HIDDEN_QWEN_HIGH_CONFIDENCE,
            HELD_FOR_REVIEW,
            HIDDEN_BY_ADMIN,
            DELETED_BY_AUTHOR,
            DELETED_BY_ADMIN,
        }
    ),
    HIDDEN_QWEN_HIGH_CONFIDENCE: frozenset(
        {
            VISIBLE_QWEN_APPROVED,
            VISIBLE_SPOILER_COLLAPSED,
            HELD_FOR_REVIEW,
            HIDDEN_BY_ADMIN,
            DELETED_BY_AUTHOR,
            DELETED_BY_ADMIN,
        }
    ),
    HELD_FOR_REVIEW: frozenset(
        {
            VISIBLE_QWEN_APPROVED,
            VISIBLE_SPOILER_COLLAPSED,
            HIDDEN_QWEN_HIGH_CONFIDENCE,
            HIDDEN_BY_ADMIN,
            DELETED_BY_AUTHOR,
            DELETED_BY_ADMIN,
        }
    ),
    HIDDEN_BY_ADMIN: frozenset(
        {
            VISIBLE_QWEN_APPROVED,
            VISIBLE_SPOILER_COLLAPSED,
            HELD_FOR_REVIEW,
            DELETED_BY_ADMIN,
            DELETED_BY_AUTHOR,
        }
    ),
    DELETED_BY_AUTHOR: frozenset(
        {
            # Admin restore only (audit required at call site)
            HELD_FOR_REVIEW,
            HIDDEN_BY_ADMIN,
            DELETED_BY_ADMIN,
        }
    ),
    DELETED_BY_ADMIN: frozenset(),
}


class InvalidTransition(ValueError):
    code = "InvalidTransition"


def normalize_status(status: str) -> str:
    """Map Stage01 alias to V2 canonical status; pass through known V2."""
    if status in COMMENT_STATUSES_V2:
        return status
    mapped = STAGE01_STATUS_ALIASES.get(status)
    if mapped:
        return mapped
    raise InvalidTransition(f"unknown status: {status}")


def is_public_visible(status: str) -> bool:
    return normalize_status(status) in PUBLIC_VISIBLE_STATUSES


def is_author_visible(status: str) -> bool:
    return normalize_status(status) in AUTHOR_VISIBLE_STATUSES


def retains_body(status: str) -> bool:
    """True when body must remain in DB (all soft-delete / hide paths)."""
    s = normalize_status(status)
    return s in SOFT_DELETE_STATUSES or s in PUBLIC_VISIBLE_STATUSES


def transition_allowed(from_status: str, to_status: str) -> bool:
    src = normalize_status(from_status)
    dst = normalize_status(to_status)
    if src == dst:
        return True  # idempotent no-op
    return dst in ALLOWED_TRANSITIONS.get(src, frozenset())


def validate_transition(from_status: str, to_status: str) -> str:
    """Return canonical destination status or raise InvalidTransition."""
    src = normalize_status(from_status)
    dst = normalize_status(to_status)
    if src == dst:
        return dst
    if dst not in ALLOWED_TRANSITIONS.get(src, frozenset()):
        raise InvalidTransition(f"transition not allowed: {src} → {dst}")
    return dst


def state_machine_document() -> dict[str, Any]:
    """Serializable SSOT for docs/COMMENT_STATE_MACHINE_V1.json."""
    return {
        "schema_version": "COMMENT_STATE_MACHINE_V1",
        "statuses": sorted(COMMENT_STATUSES_V2),
        "public_visible": sorted(PUBLIC_VISIBLE_STATUSES),
        "author_visible_extra": sorted(AUTHOR_VISIBLE_EXTRA),
        "soft_delete_retain_body": sorted(SOFT_DELETE_STATUSES),
        "stage01_aliases": dict(STAGE01_STATUS_ALIASES),
        "allowed_transitions": {
            k: sorted(v) for k, v in sorted(ALLOWED_TRANSITIONS.items())
        },
        "notes": [
            "Physical deletion of body by automation is forbidden",
            "Qwen decisions never hard-delete",
            "DELETED_BY_ADMIN is terminal",
        ],
    }
