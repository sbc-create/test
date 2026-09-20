"""Unit tests for comment lifecycle state machine (COMMUNITY-COMMENTS-02)."""

from __future__ import annotations

import pytest

from factory.community.comments import states
from factory.community.comments.states import (
    ALLOWED_TRANSITIONS,
    DELETED_BY_ADMIN,
    DELETED_BY_AUTHOR,
    HELD_FOR_REVIEW,
    HIDDEN_BY_ADMIN,
    HIDDEN_QWEN_HIGH_CONFIDENCE,
    PENDING_MODERATION_DEGRADED,
    PREFLIGHT_REJECTED,
    PUBLIC_VISIBLE_STATUSES,
    PUBLISHED_UNREVIEWED,
    STAGE01_STATUS_ALIASES,
    VISIBLE_QWEN_APPROVED,
    VISIBLE_SPOILER_COLLAPSED,
    InvalidTransition,
    is_public_visible,
    normalize_status,
    retains_body,
    transition_allowed,
    validate_transition,
)
from factory.community.store import CommunityStore


def test_all_goal_statuses_defined():
    expected = {
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
    assert expected == states.COMMENT_STATUSES_V2


def test_public_visible_set():
    assert PUBLIC_VISIBLE_STATUSES == {
        PUBLISHED_UNREVIEWED,
        VISIBLE_QWEN_APPROVED,
        VISIBLE_SPOILER_COLLAPSED,
    }
    assert is_public_visible(PUBLISHED_UNREVIEWED)
    assert not is_public_visible(HELD_FOR_REVIEW)
    assert not is_public_visible(PENDING_MODERATION_DEGRADED)


def test_stage01_aliases():
    assert normalize_status("PENDING") == HELD_FOR_REVIEW
    assert normalize_status("DELETED_BY_USER") == DELETED_BY_AUTHOR
    assert normalize_status("REMOVED_BY_MODERATOR") == DELETED_BY_ADMIN
    assert normalize_status(PUBLISHED_UNREVIEWED) == PUBLISHED_UNREVIEWED
    for alias in STAGE01_STATUS_ALIASES:
        assert normalize_status(alias) in states.COMMENT_STATUSES_V2


def test_qwen_allow_path():
    assert validate_transition(PUBLISHED_UNREVIEWED, VISIBLE_QWEN_APPROVED) == VISIBLE_QWEN_APPROVED
    assert validate_transition(PUBLISHED_UNREVIEWED, VISIBLE_SPOILER_COLLAPSED)
    assert validate_transition(PUBLISHED_UNREVIEWED, HIDDEN_QWEN_HIGH_CONFIDENCE)
    assert validate_transition(PUBLISHED_UNREVIEWED, HELD_FOR_REVIEW)


def test_idempotent_same_status():
    assert transition_allowed(VISIBLE_QWEN_APPROVED, VISIBLE_QWEN_APPROVED)
    assert validate_transition(HELD_FOR_REVIEW, HELD_FOR_REVIEW) == HELD_FOR_REVIEW


def test_deleted_by_author_blocks_qwen_reappear():
    assert not transition_allowed(DELETED_BY_AUTHOR, VISIBLE_QWEN_APPROVED)
    assert not transition_allowed(DELETED_BY_AUTHOR, PUBLISHED_UNREVIEWED)
    with pytest.raises(InvalidTransition):
        validate_transition(DELETED_BY_AUTHOR, VISIBLE_QWEN_APPROVED)


def test_soft_delete_retains_body():
    for s in (
        DELETED_BY_AUTHOR,
        DELETED_BY_ADMIN,
        HIDDEN_BY_ADMIN,
        HIDDEN_QWEN_HIGH_CONFIDENCE,
        HELD_FOR_REVIEW,
    ):
        assert retains_body(s)


def test_terminal_admin_delete():
    assert ALLOWED_TRANSITIONS[DELETED_BY_ADMIN] == frozenset()
    with pytest.raises(InvalidTransition):
        validate_transition(DELETED_BY_ADMIN, VISIBLE_QWEN_APPROVED)


def test_schema_v2_columns(tmp_path):
    store = CommunityStore(tmp_path / "sm.sqlite")
    cols = {r[1] for r in store.conn.execute("PRAGMA table_info(community_comments)")}
    for needed in (
        "moderation_status",
        "body_digest",
        "spoiler_collapsed",
        "qwen_decision_json",
        "last_moderation_at",
        "content_type",
    ):
        assert needed in cols
    meta = store.conn.execute(
        "SELECT value FROM community_schema_meta WHERE key='comments_schema'"
    ).fetchone()
    assert meta["value"] == "community_comments_v2"
    tables = {
        r[0]
        for r in store.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "community_comment_moderation_jobs" in tables
    assert "community_comment_kill_switch_audit" in tables
    # Ratings tables untouched
    assert "community_votes" in tables
    assert "community_aggregates" in tables
    store.close()
