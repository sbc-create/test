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

-- Comments foundation (dark): schema ready, flags off
CREATE TABLE IF NOT EXISTS community_comments (
    comment_id TEXT PRIMARY KEY,
    discussion_space_id TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'DRAFT',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS community_comment_revisions (
    revision_id TEXT PRIMARY KEY,
    comment_id TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS community_comment_reactions (
    reaction_id TEXT PRIMARY KEY,
    comment_id TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    reaction TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS community_content_reports (
    report_id TEXT PRIMARY KEY,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    created_at TEXT NOT NULL
);

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


class CommunityStore:
    """Dedicated community DB file — never the production ratings.sqlite unless owner-approved."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.RLock()
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(
            str(path), timeout=30.0, isolation_level=None, check_same_thread=False
        )
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA_SQL)
        self.conn.execute(
            "INSERT OR REPLACE INTO community_schema_meta(key, value) VALUES ('version', ?)",
            ("community_ratings_v1",),
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
