"""Comments foundation (dark launch) — schema ready, all publication flags OFF."""

from __future__ import annotations

from typing import Any

from factory.community.comments.flags import (
    COMMENTS_ADMIN_PREVIEW_ENABLED,
    COMMENTS_API_WRITE_ENABLED,
    COMMENTS_ENABLED,
    COMMENTS_PUBLIC_READ_ENABLED,
    COMMENTS_PUBLICATION_ENABLED,
    COMMENTS_SEO_RENDERING_ENABLED,
    EXTERNAL_COMMENTS_REPUBLISHED,
    FAKE_COMMENTS_INSERTED,
    PRODUCTION_COMMENTS_INSERTED,
    assert_comments_dark,
    comments_dark_flags,
    isolation_invariants,
)

# Re-export for legacy imports from antifraud constants.
REQUIRED_COMMENT_TABLES = (
    "community_comments",
    "community_comment_revisions",
    "community_comment_reactions",
    "community_content_reports",
    "community_comment_moderation_events",
    "community_comment_rate_limit_events",
    "community_comment_risk_signals",
    "community_moderation_cases",
    "community_moderation_actions",
    "community_sanctions",
)


def comments_flags() -> dict[str, int]:
    return comments_dark_flags()


def comments_cannot_mutate_rating() -> dict[str, Any]:
    """Invariant documentation + runtime check hook."""
    return isolation_invariants()


__all__ = (
    "COMMENTS_ENABLED",
    "COMMENTS_PUBLICATION_ENABLED",
    "COMMENTS_PUBLIC_READ_ENABLED",
    "COMMENTS_SEO_RENDERING_ENABLED",
    "COMMENTS_API_WRITE_ENABLED",
    "COMMENTS_ADMIN_PREVIEW_ENABLED",
    "PRODUCTION_COMMENTS_INSERTED",
    "EXTERNAL_COMMENTS_REPUBLISHED",
    "FAKE_COMMENTS_INSERTED",
    "REQUIRED_COMMENT_TABLES",
    "assert_comments_dark",
    "comments_flags",
    "comments_cannot_mutate_rating",
)
