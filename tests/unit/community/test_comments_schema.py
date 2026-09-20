"""Comments schema readiness and additive migrations."""

from __future__ import annotations

import sqlite3

import pytest

from factory.community.comments_foundation import REQUIRED_COMMENT_TABLES, comments_flags
from factory.community.store import CommunityStore, migrate_comments_schema


@pytest.fixture()
def store(tmp_path):
    s = CommunityStore(tmp_path / "comments-schema.sqlite")
    yield s
    s.close()


def test_required_tables_exist(store):
    names = {
        r[0]
        for r in store.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    for table in REQUIRED_COMMENT_TABLES:
        assert table in names


def test_comment_columns(store):
    cols = {r[1] for r in store.conn.execute("PRAGMA table_info(community_comments)")}
    for needed in (
        "comment_id",
        "site_space",
        "title_id",
        "identity_id",
        "parent_comment_id",
        "body",
        "body_normalized",
        "spoiler",
        "status",
        "created_at",
        "edited_at",
        "deleted_at",
        "published_at",
        "moderation_reason",
        "risk_state",
        "version",
    ):
        assert needed in cols


def test_comments_schema_meta(store):
    row = store.conn.execute(
        "SELECT value FROM community_schema_meta WHERE key='comments_schema'"
    ).fetchone()
    assert row["value"] == "community_comments_v2"
    ratings = store.conn.execute(
        "SELECT value FROM community_schema_meta WHERE key='version'"
    ).fetchone()
    assert ratings["value"] == "community_ratings_v1"


def test_additive_migration_from_stub(tmp_path):
    path = tmp_path / "stub.sqlite"
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE community_comments (
            comment_id TEXT PRIMARY KEY,
            discussion_space_id TEXT NOT NULL,
            subject_id TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            body TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'DRAFT',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE community_comment_revisions (
            revision_id TEXT PRIMARY KEY,
            comment_id TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE community_comment_reactions (
            reaction_id TEXT PRIMARY KEY,
            comment_id TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            reaction TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE community_content_reports (
            report_id TEXT PRIMARY KEY,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            reason_code TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        INSERT INTO community_comments VALUES
            ('c1','yummy','t1','id1','hello','DRAFT','2026-01-01T00:00:00Z','2026-01-01T00:00:00Z');
        """
    )
    migrate_comments_schema(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(community_comments)")}
    assert "site_space" in cols and "identity_id" in cols
    row = conn.execute("SELECT site_space, title_id, identity_id FROM community_comments").fetchone()
    assert row[0] == "yummy" and row[1] == "t1" and row[2] == "id1"
    conn.close()


def test_dark_flags_locked():
    flags = comments_flags()
    assert flags["COMMENTS_PUBLICATION_ENABLED"] == 0
    assert flags["COMMENTS_PUBLIC_READ_ENABLED"] == 0
    assert flags["COMMENTS_SEO_RENDERING_ENABLED"] == 0
    assert flags["PRODUCTION_COMMENTS_INSERTED"] == 0
    assert flags["EXTERNAL_COMMENTS_REPUBLISHED"] == 0
    assert flags["FAKE_COMMENTS_INSERTED"] == 0
    assert flags["COMMENTS_ADMIN_PREVIEW_ENABLED"] == 1
    assert flags["COMMENTS_API_WRITE_ENABLED"] == 0
