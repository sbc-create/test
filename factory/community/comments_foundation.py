"""Comments foundation (dark launch) — schema ready, all publication flags OFF."""

from __future__ import annotations

from typing import Any

from factory.community.antifraud import (
    COMMENTS_ENABLED,
    COMMENTS_PUBLICATION_ENABLED,
    COMMENTS_SEO_RENDERING_ENABLED,
)


def comments_flags() -> dict[str, int]:
    return {
        "COMMENTS_ENABLED": COMMENTS_ENABLED,
        "COMMENTS_PUBLICATION_ENABLED": COMMENTS_PUBLICATION_ENABLED,
        "COMMENTS_SEO_RENDERING_ENABLED": COMMENTS_SEO_RENDERING_ENABLED,
    }


def assert_comments_dark() -> None:
    flags = comments_flags()
    if any(v != 0 for v in flags.values()):
        raise RuntimeError(f"comments must remain dark: {flags}")


def comments_cannot_mutate_rating() -> dict[str, Any]:
    """Invariant documentation + runtime check hook."""
    return {
        "comments_affect_rating": False,
        "reactions_affect_rating": False,
        "delete_comment_deletes_vote": False,
        "delete_vote_deletes_comment": False,
        "COMMENTS_OR_REACTIONS_AFFECT_RATING": 0,
    }


REQUIRED_COMMENT_TABLES = (
    "community_comments",
    "community_comment_revisions",
    "community_comment_reactions",
    "community_content_reports",
    "community_moderation_cases",
    "community_moderation_actions",
    "community_sanctions",
)
