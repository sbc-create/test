"""Isolated community ratings SQLite ledger (not auto-applied to production)."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS community_schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS community_actors (
    actor_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    account_id TEXT NOT NULL DEFAULT '',
    site_profile_id TEXT NOT NULL DEFAULT '',
    merged_into TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS community_vote_events (
    event_id TEXT PRIMARY KEY,
    rating_space_id TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    dimension TEXT NOT NULL DEFAULT 'overall',
    action TEXT NOT NULL,
    old_score INTEGER,
    new_score INTEGER,
    status TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    risk_state TEXT NOT NULL DEFAULT 'CLEAR',
    idempotency_key TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}'
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_community_vote_idem
    ON community_vote_events(idempotency_key);

CREATE TABLE IF NOT EXISTS community_votes (
    rating_space_id TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    dimension TEXT NOT NULL DEFAULT 'overall',
    score INTEGER NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    retracted_at TEXT NOT NULL DEFAULT '',
    policy_version TEXT NOT NULL,
    risk_state TEXT NOT NULL DEFAULT 'CLEAR',
    PRIMARY KEY (rating_space_id, subject_id, actor_id, dimension)
);

CREATE TABLE IF NOT EXISTS community_aggregates (
    rating_space_id TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    dimension TEXT NOT NULL DEFAULT 'overall',
    vote_sum INTEGER NOT NULL DEFAULT 0,
    vote_count INTEGER NOT NULL DEFAULT 0,
    aggregate_version INTEGER NOT NULL DEFAULT 0,
    policy_version TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (rating_space_id, subject_id, dimension)
);

CREATE TABLE IF NOT EXISTS community_outbox (
    outbox_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    dedupe_key TEXT NOT NULL UNIQUE,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    delivered_at TEXT NOT NULL DEFAULT ''
);

-- Comments foundation (dark): full schema, all publication flags OFF
-- Canonical fields: site_space / title_id / identity_id.
-- Legacy aliases discussion_space_id / subject_id / actor_id kept for ratings-era stubs.
CREATE TABLE IF NOT EXISTS community_comments (
    comment_id TEXT PRIMARY KEY,
    site_space TEXT NOT NULL DEFAULT '',
    title_id TEXT NOT NULL DEFAULT '',
    identity_id TEXT NOT NULL DEFAULT '',
    parent_comment_id TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    body_normalized TEXT NOT NULL DEFAULT '',
    spoiler INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'PENDING',
    created_at TEXT NOT NULL,
    edited_at TEXT NOT NULL DEFAULT '',
    deleted_at TEXT NOT NULL DEFAULT '',
    published_at TEXT NOT NULL DEFAULT '',
    moderation_reason TEXT NOT NULL DEFAULT '',
    risk_state TEXT NOT NULL DEFAULT 'CLEAR',
    version INTEGER NOT NULL DEFAULT 1,
    discussion_space_id TEXT NOT NULL DEFAULT '',
    subject_id TEXT NOT NULL DEFAULT '',
    actor_id TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_community_comments_space_title
    ON community_comments(site_space, title_id, created_at);
CREATE INDEX IF NOT EXISTS idx_community_comments_status
    ON community_comments(status);
CREATE INDEX IF NOT EXISTS idx_community_comments_parent
    ON community_comments(parent_comment_id);

-- Immutable edit history (append-only; never UPDATE body rows)
CREATE TABLE IF NOT EXISTS community_comment_revisions (
    revision_id TEXT PRIMARY KEY,
    comment_id TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    body TEXT NOT NULL,
    body_normalized TEXT NOT NULL DEFAULT '',
    editor_identity_id TEXT NOT NULL DEFAULT '',
    edit_reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_community_comment_revisions_comment
    ON community_comment_revisions(comment_id, version);

CREATE TABLE IF NOT EXISTS community_comment_reactions (
    reaction_id TEXT PRIMARY KEY,
    comment_id TEXT NOT NULL,
    identity_id TEXT NOT NULL DEFAULT '',
    actor_id TEXT NOT NULL DEFAULT '',
    reaction TEXT NOT NULL,
    created_at TEXT NOT NULL,
    retracted_at TEXT NOT NULL DEFAULT ''
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_community_comment_reaction
    ON community_comment_reactions(comment_id, identity_id, reaction)
    WHERE retracted_at = '';

CREATE TABLE IF NOT EXISTS community_content_reports (
    report_id TEXT PRIMARY KEY,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    comment_id TEXT NOT NULL DEFAULT '',
    identity_id TEXT NOT NULL DEFAULT '',
    actor_id TEXT NOT NULL DEFAULT '',
    reason_code TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'OPEN',
    created_at TEXT NOT NULL,
    resolved_at TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_community_content_reports_comment
    ON community_content_reports(comment_id, status);

CREATE TABLE IF NOT EXISTS community_comment_moderation_events (
    event_id TEXT PRIMARY KEY,
    comment_id TEXT NOT NULL,
    action TEXT NOT NULL,
    actor_role TEXT NOT NULL DEFAULT 'moderator',
    actor_identity_id TEXT NOT NULL DEFAULT '',
    reason_code TEXT NOT NULL DEFAULT '',
    detail TEXT NOT NULL DEFAULT '',
    prior_status TEXT NOT NULL DEFAULT '',
    new_status TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_community_comment_mod_events
    ON community_comment_moderation_events(comment_id, created_at);

CREATE TABLE IF NOT EXISTS community_comment_rate_limit_events (
    event_id TEXT PRIMARY KEY,
    identity_id TEXT NOT NULL,
    site_space TEXT NOT NULL DEFAULT '',
    title_id TEXT NOT NULL DEFAULT '',
    action TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_community_comment_rate_limit
    ON community_comment_rate_limit_events(identity_id, created_at);

CREATE TABLE IF NOT EXISTS community_comment_risk_signals (
    signal_id TEXT PRIMARY KEY,
    comment_id TEXT NOT NULL DEFAULT '',
    identity_id TEXT NOT NULL DEFAULT '',
    signal_type TEXT NOT NULL,
    score REAL NOT NULL DEFAULT 0,
    detail_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_community_comment_risk
    ON community_comment_risk_signals(comment_id, signal_type);

CREATE TABLE IF NOT EXISTS community_moderation_cases (
    case_id TEXT PRIMARY KEY,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS community_moderation_actions (
    action_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    action TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS community_sanctions (
    sanction_id TEXT PRIMARY KEY,
    actor_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL DEFAULT ''
);
"""

# Additive column migrations for DBs created from earlier stub SCHEMA_SQL.
_COMMENTS_COLUMN_MIGRATIONS: dict[str, tuple[tuple[str, str], ...]] = {
    "community_comments": (
        ("site_space", "TEXT NOT NULL DEFAULT ''"),
        ("title_id", "TEXT NOT NULL DEFAULT ''"),
        ("identity_id", "TEXT NOT NULL DEFAULT ''"),
        ("parent_comment_id", "TEXT NOT NULL DEFAULT ''"),
        ("body_normalized", "TEXT NOT NULL DEFAULT ''"),
        ("spoiler", "INTEGER NOT NULL DEFAULT 0"),
        ("edited_at", "TEXT NOT NULL DEFAULT ''"),
        ("deleted_at", "TEXT NOT NULL DEFAULT ''"),
        ("published_at", "TEXT NOT NULL DEFAULT ''"),
        ("moderation_reason", "TEXT NOT NULL DEFAULT ''"),
        ("risk_state", "TEXT NOT NULL DEFAULT 'CLEAR'"),
        ("version", "INTEGER NOT NULL DEFAULT 1"),
        ("discussion_space_id", "TEXT NOT NULL DEFAULT ''"),
        ("subject_id", "TEXT NOT NULL DEFAULT ''"),
        ("actor_id", "TEXT NOT NULL DEFAULT ''"),
        ("updated_at", "TEXT NOT NULL DEFAULT ''"),
    ),
    "community_comment_revisions": (
        ("version", "INTEGER NOT NULL DEFAULT 1"),
        ("body_normalized", "TEXT NOT NULL DEFAULT ''"),
        ("editor_identity_id", "TEXT NOT NULL DEFAULT ''"),
        ("edit_reason", "TEXT NOT NULL DEFAULT ''"),
    ),
    "community_comment_reactions": (
        ("identity_id", "TEXT NOT NULL DEFAULT ''"),
        ("retracted_at", "TEXT NOT NULL DEFAULT ''"),
    ),
    "community_content_reports": (
        ("comment_id", "TEXT NOT NULL DEFAULT ''"),
        ("identity_id", "TEXT NOT NULL DEFAULT ''"),
        ("detail", "TEXT NOT NULL DEFAULT ''"),
        ("status", "TEXT NOT NULL DEFAULT 'OPEN'"),
        ("resolved_at", "TEXT NOT NULL DEFAULT ''"),
    ),
}


def _existing_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(r[1]) for r in rows}


def migrate_comments_schema(conn: sqlite3.Connection) -> None:
    """Additive-only column/index upgrades for comments tables."""
    for table, cols in _COMMENTS_COLUMN_MIGRATIONS.items():
        present = _existing_columns(conn, table)
        if not present:
            continue
        for name, decl in cols:
            if name not in present:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")
    # Backfill canonical fields from legacy aliases when empty.
    if _existing_columns(conn, "community_comments"):
        conn.execute(
            """UPDATE community_comments
               SET site_space = CASE WHEN site_space = '' THEN discussion_space_id ELSE site_space END,
                   title_id = CASE WHEN title_id = '' THEN subject_id ELSE title_id END,
                   identity_id = CASE WHEN identity_id = '' THEN actor_id ELSE identity_id END"""
        )


class CommunityStore:
    """Dedicated community DB file — never the production ratings.sqlite unless owner-approved."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(
            str(path), timeout=30.0, isolation_level=None, check_same_thread=False
        )
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA_SQL)
        migrate_comments_schema(self.conn)
        self.conn.execute(
            "INSERT OR REPLACE INTO community_schema_meta(key, value) VALUES ('version', ?)",
            ("community_ratings_v1",),
        )
        self.conn.execute(
            "INSERT OR REPLACE INTO community_schema_meta(key, value) VALUES ('comments_schema', ?)",
            ("community_comments_v1",),
        )

    def close(self) -> None:
        self.conn.close()

    def get_vote(
        self, *, rating_space_id: str, subject_id: str, actor_id: str, dimension: str = "overall"
    ) -> dict[str, Any] | None:
        row = self.conn.execute(
            """SELECT * FROM community_votes
               WHERE rating_space_id=? AND subject_id=? AND actor_id=? AND dimension=?
                 AND status='ACCEPTED'""",
            (rating_space_id, subject_id, actor_id, dimension),
        ).fetchone()
        return dict(row) if row else None

    def get_vote_row_any_status(
        self, *, rating_space_id: str, subject_id: str, actor_id: str, dimension: str = "overall"
    ) -> dict[str, Any] | None:
        row = self.conn.execute(
            """SELECT * FROM community_votes
               WHERE rating_space_id=? AND subject_id=? AND actor_id=? AND dimension=?""",
            (rating_space_id, subject_id, actor_id, dimension),
        ).fetchone()
        return dict(row) if row else None

    def get_aggregate(
        self, *, rating_space_id: str, subject_id: str, dimension: str = "overall"
    ) -> dict[str, Any]:
        row = self.conn.execute(
            """SELECT * FROM community_aggregates
               WHERE rating_space_id=? AND subject_id=? AND dimension=?""",
            (rating_space_id, subject_id, dimension),
        ).fetchone()
        if not row:
            return {
                "rating_space_id": rating_space_id,
                "subject_id": subject_id,
                "dimension": dimension,
                "vote_sum": 0,
                "vote_count": 0,
                "aggregate_version": 0,
                "policy_version": "",
                "updated_at": "",
            }
        return dict(row)

    def rebuild_aggregate_from_votes(
        self, *, rating_space_id: str, subject_id: str, dimension: str = "overall"
    ) -> dict[str, Any]:
        row = self.conn.execute(
            """SELECT COALESCE(SUM(score),0) AS s, COUNT(*) AS n
               FROM community_votes
               WHERE rating_space_id=? AND subject_id=? AND dimension=?
                 AND status='ACCEPTED' AND risk_state!='QUARANTINED'""",
            (rating_space_id, subject_id, dimension),
        ).fetchone()
        return {"vote_sum": int(row["s"]), "vote_count": int(row["n"])}
