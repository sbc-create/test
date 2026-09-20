"""Dark-mode feature flags for community comments.

Public publication / read / SEO remain OFF. Admin preview is the only
UI surface enabled by default. API write stays OFF until a supervised
canary earns a gate pass — never auto-enable from code paths.
"""

from __future__ import annotations

import os
from typing import Any

# --- Public / production gates (must stay 0 in COMMUNITY-COMMENTS-01) ---
COMMENTS_PUBLICATION_ENABLED = 0
COMMENTS_PUBLIC_READ_ENABLED = 0
COMMENTS_SEO_RENDERING_ENABLED = 0
COMMENTS_API_WRITE_ENABLED = 0

# Admin-only dark preview (queue + author-facing preview for operators)
COMMENTS_ADMIN_PREVIEW_ENABLED = 1

# Internal research / schema readiness (does not publish)
COMMENTS_ENABLED = 1
COMMENTS_SCHEMA_READY = 1

# Production counters — hard-locked at zero for this stage
PRODUCTION_COMMENTS_INSERTED = 0
EXTERNAL_COMMENTS_REPUBLISHED = 0
FAKE_COMMENTS_INSERTED = 0

# Forbidden admin capabilities (never enable)
ADMIN_FAKE_COMMENT_INSERT = 0
ADMIN_IMPERSONATE_USER = 0
ADMIN_SILENT_TEXT_REWRITE = 0

# Isolation from ratings
COMMENTS_OR_REACTIONS_AFFECT_RATING = 0

# Soft-delete only; hard delete is never a normal moderation path
COMMENTS_HARD_DELETE_ENABLED = 0

# --- COMMUNITY-COMMENTS-02 Qwen postmod (default OFF — no production enable) ---
COMMENTS_QWEN_POSTMOD_ENABLED = 0
COMMENTS_ROLLOUT_PERCENT = 0
COMMENTS_QWEN_WORKER_ENABLED = 0

STATUS_PENDING = "PENDING"
STATUS_PUBLISHED = "PUBLISHED"
STATUS_QUARANTINED = "QUARANTINED"
STATUS_REJECTED = "REJECTED"
STATUS_DELETED_BY_USER = "DELETED_BY_USER"
STATUS_REMOVED_BY_MODERATOR = "REMOVED_BY_MODERATOR"

COMMENT_STATUSES = frozenset(
    {
        STATUS_PENDING,
        STATUS_PUBLISHED,
        STATUS_QUARANTINED,
        STATUS_REJECTED,
        STATUS_DELETED_BY_USER,
        STATUS_REMOVED_BY_MODERATOR,
    }
)

PUBLIC_VISIBLE_STATUSES = frozenset({STATUS_PUBLISHED})
AUTHOR_VISIBLE_EXTRA = frozenset({STATUS_PENDING, STATUS_QUARANTINED, STATUS_DELETED_BY_USER})


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def comments_dark_flags() -> dict[str, int]:
    """Runtime flag snapshot. Env overrides are clamped for publication gates."""
    publication = min(_env_int("COMMENTS_PUBLICATION_ENABLED", COMMENTS_PUBLICATION_ENABLED), 0)
    public_read = min(_env_int("COMMENTS_PUBLIC_READ_ENABLED", COMMENTS_PUBLIC_READ_ENABLED), 0)
    seo = min(_env_int("COMMENTS_SEO_RENDERING_ENABLED", COMMENTS_SEO_RENDERING_ENABLED), 0)
    api_write = _env_int("COMMENTS_API_WRITE_ENABLED", COMMENTS_API_WRITE_ENABLED)
    # Stage hard-lock: publication family cannot leave 0 via env.
    return {
        "COMMENTS_ENABLED": COMMENTS_ENABLED,
        "COMMENTS_SCHEMA_READY": COMMENTS_SCHEMA_READY,
        "COMMENTS_PUBLICATION_ENABLED": publication,
        "COMMENTS_PUBLIC_READ_ENABLED": public_read,
        "COMMENTS_SEO_RENDERING_ENABLED": seo,
        "COMMENTS_API_WRITE_ENABLED": int(bool(api_write)),
        "COMMENTS_ADMIN_PREVIEW_ENABLED": COMMENTS_ADMIN_PREVIEW_ENABLED,
        "PRODUCTION_COMMENTS_INSERTED": PRODUCTION_COMMENTS_INSERTED,
        "EXTERNAL_COMMENTS_REPUBLISHED": EXTERNAL_COMMENTS_REPUBLISHED,
        "FAKE_COMMENTS_INSERTED": FAKE_COMMENTS_INSERTED,
        "ADMIN_FAKE_COMMENT_INSERT": ADMIN_FAKE_COMMENT_INSERT,
        "ADMIN_IMPERSONATE_USER": ADMIN_IMPERSONATE_USER,
        "ADMIN_SILENT_TEXT_REWRITE": ADMIN_SILENT_TEXT_REWRITE,
        "COMMENTS_OR_REACTIONS_AFFECT_RATING": COMMENTS_OR_REACTIONS_AFFECT_RATING,
        "COMMENTS_HARD_DELETE_ENABLED": COMMENTS_HARD_DELETE_ENABLED,
        # Postmod / worker stay OFF in production snapshot; staging tests use
        # bypass_write_flag_for_tests / FakeQwenProvider, not these flags.
        "COMMENTS_QWEN_POSTMOD_ENABLED": min(
            _env_int("COMMENTS_QWEN_POSTMOD_ENABLED", COMMENTS_QWEN_POSTMOD_ENABLED), 0
        ),
        "COMMENTS_ROLLOUT_PERCENT": min(
            _env_int("COMMENTS_ROLLOUT_PERCENT", COMMENTS_ROLLOUT_PERCENT), 0
        ),
        "COMMENTS_QWEN_WORKER_ENABLED": min(
            _env_int("COMMENTS_QWEN_WORKER_ENABLED", COMMENTS_QWEN_WORKER_ENABLED), 0
        ),
    }


def assert_comments_dark() -> None:
    flags = comments_dark_flags()
    locked = (
        "COMMENTS_PUBLICATION_ENABLED",
        "COMMENTS_PUBLIC_READ_ENABLED",
        "COMMENTS_SEO_RENDERING_ENABLED",
        "PRODUCTION_COMMENTS_INSERTED",
        "EXTERNAL_COMMENTS_REPUBLISHED",
        "FAKE_COMMENTS_INSERTED",
        "ADMIN_FAKE_COMMENT_INSERT",
        "ADMIN_IMPERSONATE_USER",
        "ADMIN_SILENT_TEXT_REWRITE",
    )
    bad = {k: flags[k] for k in locked if flags[k] != 0}
    if bad:
        raise RuntimeError(f"comments must remain dark: {bad}")


def writes_enabled() -> bool:
    """API write path — OFF by default; never implies public publication."""
    flags = comments_dark_flags()
    return bool(flags["COMMENTS_API_WRITE_ENABLED"]) and not bool(
        flags["COMMENTS_PUBLICATION_ENABLED"]
    )


def public_read_enabled() -> bool:
    return bool(comments_dark_flags()["COMMENTS_PUBLIC_READ_ENABLED"])


def admin_preview_enabled() -> bool:
    return bool(comments_dark_flags()["COMMENTS_ADMIN_PREVIEW_ENABLED"])


FORBIDDEN_ADMIN_CAPABILITIES = frozenset(
    {
        "ADMIN_FAKE_COMMENT_INSERT",
        "ADMIN_IMPERSONATE_USER",
        "ADMIN_SILENT_TEXT_REWRITE",
    }
)


def forbid_admin_capability(name: str) -> None:
    """Always raise for permanently forbidden admin capabilities."""
    if name in FORBIDDEN_ADMIN_CAPABILITIES:
        raise PermissionError(f"forbidden admin capability: {name}")
    raise ValueError(f"unknown capability: {name}")


def isolation_invariants() -> dict[str, Any]:
    return {
        "comments_affect_rating": False,
        "reactions_affect_rating": False,
        "delete_comment_deletes_vote": False,
        "delete_vote_deletes_comment": False,
        "COMMENTS_OR_REACTIONS_AFFECT_RATING": 0,
        "IDENTITY_COOKIE": "yummy_cr_vid",
        "IDENTITY_MODE": "SIGNED_PSEUDONYMOUS_DEVICE_V1",
        "SECOND_COOKIE_FORBIDDEN": True,
    }
