"""Physical schema for the shared comments platform.

The DDL lives here rather than inside the migration so that one text is the
source for both the migration and any freshly created test database. Two
copies of a schema drift, and the drift is only ever discovered in production.

Every table is prefixed `cp_` and every table carries `tenant_id` and
`site_id`. That is not decoration:

* The pair is part of every primary key, so a comment id colliding across
  tenants is structurally impossible rather than statistically unlikely.
* Foreign keys are composite — `(tenant_id, site_id, thread_id)` — so the
  database itself refuses to attach a `lords` comment to a `zona` thread. An
  isolation rule that lives only in application code is one forgotten `WHERE`
  away from being untrue.
* The read index leads with the pair, so the query planner cannot serve a
  thread page by scanning another site's rows.

Nothing here touches the community ratings tables. Ratings keep their own
schema, their own migrations and their own database file; the two products
share no table, no sequence and no lock.
"""

from __future__ import annotations

SCHEMA_VERSION = "COMMENTS_PLATFORM_V1"

# --- Tables ---------------------------------------------------------------

UP: list[str] = [
    # Enforced per connection, not per schema, but stated here so a reader of
    # the DDL knows composite foreign keys are meant to actually bite.
    "PRAGMA foreign_keys = ON",
    """
    CREATE TABLE IF NOT EXISTS cp_sites (
        tenant_id         TEXT NOT NULL,
        site_id           TEXT NOT NULL,
        module_version    TEXT NOT NULL,
        artifact_checksum TEXT NOT NULL,
        moderation_mode   TEXT NOT NULL DEFAULT 'pre',
        seo_mode          TEXT NOT NULL DEFAULT 'user_initiated',
        read_enabled      INTEGER NOT NULL DEFAULT 0,
        write_enabled     INTEGER NOT NULL DEFAULT 0,
        publication_enabled INTEGER NOT NULL DEFAULT 0,
        rollout_percent   INTEGER NOT NULL DEFAULT 0,
        max_depth         INTEGER NOT NULL DEFAULT 3,
        max_length        INTEGER NOT NULL DEFAULT 4000,
        max_links         INTEGER NOT NULL DEFAULT 2,
        created_at        TEXT NOT NULL,
        updated_at        TEXT NOT NULL,
        PRIMARY KEY (tenant_id, site_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cp_threads (
        tenant_id            TEXT NOT NULL,
        site_id              TEXT NOT NULL,
        thread_id            TEXT NOT NULL,
        resource_type        TEXT NOT NULL,
        canonical_content_id TEXT NOT NULL,
        comment_count        INTEGER NOT NULL DEFAULT 0,
        locked               INTEGER NOT NULL DEFAULT 0,
        created_at           TEXT NOT NULL,
        updated_at           TEXT NOT NULL,
        PRIMARY KEY (tenant_id, site_id, thread_id),
        FOREIGN KEY (tenant_id, site_id) REFERENCES cp_sites(tenant_id, site_id)
    )
    """,
    # One thread per piece of content per site. The unique key is the content
    # id, never the URL: renaming a slug must not fork the discussion.
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_cp_threads_resource
        ON cp_threads(tenant_id, site_id, resource_type, canonical_content_id)
    """,
    """
    CREATE TABLE IF NOT EXISTS cp_identities (
        tenant_id     TEXT NOT NULL,
        site_id       TEXT NOT NULL,
        subject_id    TEXT NOT NULL,
        display_name  TEXT NOT NULL DEFAULT '',
        is_guest      INTEGER NOT NULL DEFAULT 1,
        reputation    INTEGER NOT NULL DEFAULT 0,
        banned        INTEGER NOT NULL DEFAULT 0,
        ban_reason    TEXT NOT NULL DEFAULT '',
        banned_at     TEXT NOT NULL DEFAULT '',
        muted_until   TEXT NOT NULL DEFAULT '',
        created_at    TEXT NOT NULL,
        updated_at    TEXT NOT NULL,
        PRIMARY KEY (tenant_id, site_id, subject_id),
        FOREIGN KEY (tenant_id, site_id) REFERENCES cp_sites(tenant_id, site_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cp_comments (
        tenant_id       TEXT NOT NULL,
        site_id         TEXT NOT NULL,
        comment_id      TEXT NOT NULL,
        thread_id       TEXT NOT NULL,
        parent_id       TEXT NOT NULL DEFAULT '',
        depth           INTEGER NOT NULL DEFAULT 0,
        subject_id      TEXT NOT NULL,
        body            TEXT NOT NULL,
        body_html       TEXT NOT NULL,
        state           TEXT NOT NULL,
        revision        INTEGER NOT NULL DEFAULT 1,
        reaction_count  INTEGER NOT NULL DEFAULT 0,
        reply_count     INTEGER NOT NULL DEFAULT 0,
        report_count    INTEGER NOT NULL DEFAULT 0,
        risk_score      INTEGER NOT NULL DEFAULT 0,
        created_at      TEXT NOT NULL,
        updated_at      TEXT NOT NULL,
        edited_at       TEXT NOT NULL DEFAULT '',
        -- Monotonic per site. Cursor pagination orders by this, not by
        -- created_at: two comments in the same millisecond would otherwise
        -- make a cursor skip or repeat a row.
        seq             INTEGER NOT NULL,
        PRIMARY KEY (tenant_id, site_id, comment_id),
        FOREIGN KEY (tenant_id, site_id, thread_id)
            REFERENCES cp_threads(tenant_id, site_id, thread_id),
        FOREIGN KEY (tenant_id, site_id, subject_id)
            REFERENCES cp_identities(tenant_id, site_id, subject_id)
    )
    """,
    # The read path. Leading with the tenant pair is what keeps a thread page
    # from ever touching another site's rows.
    """
    CREATE INDEX IF NOT EXISTS ix_cp_comments_thread_state_seq
        ON cp_comments(tenant_id, site_id, thread_id, state, seq)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_cp_comments_popular
        ON cp_comments(tenant_id, site_id, thread_id, state, reaction_count, seq)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_cp_comments_parent
        ON cp_comments(tenant_id, site_id, thread_id, parent_id, seq)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_cp_comments_author
        ON cp_comments(tenant_id, site_id, subject_id, seq)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_cp_comments_queue
        ON cp_comments(tenant_id, site_id, state, seq)
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_cp_comments_seq
        ON cp_comments(tenant_id, site_id, seq)
    """,
    """
    CREATE TABLE IF NOT EXISTS cp_comment_revisions (
        tenant_id     TEXT NOT NULL,
        site_id       TEXT NOT NULL,
        comment_id    TEXT NOT NULL,
        revision      INTEGER NOT NULL,
        body          TEXT NOT NULL,
        editor_subject_id TEXT NOT NULL,
        reason        TEXT NOT NULL DEFAULT '',
        created_at    TEXT NOT NULL,
        PRIMARY KEY (tenant_id, site_id, comment_id, revision),
        FOREIGN KEY (tenant_id, site_id, comment_id)
            REFERENCES cp_comments(tenant_id, site_id, comment_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cp_reactions (
        tenant_id     TEXT NOT NULL,
        site_id       TEXT NOT NULL,
        comment_id    TEXT NOT NULL,
        subject_id    TEXT NOT NULL,
        reaction      TEXT NOT NULL,
        created_at    TEXT NOT NULL,
        updated_at    TEXT NOT NULL,
        -- One reaction per person per comment. Enforced by the key, so a
        -- double-click cannot inflate a count even under a race.
        PRIMARY KEY (tenant_id, site_id, comment_id, subject_id),
        FOREIGN KEY (tenant_id, site_id, comment_id)
            REFERENCES cp_comments(tenant_id, site_id, comment_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cp_reports (
        tenant_id     TEXT NOT NULL,
        site_id       TEXT NOT NULL,
        comment_id    TEXT NOT NULL,
        reporter_subject_id TEXT NOT NULL,
        reason        TEXT NOT NULL,
        note          TEXT NOT NULL DEFAULT '',
        state         TEXT NOT NULL DEFAULT 'open',
        network_hmac  TEXT NOT NULL DEFAULT '',
        created_at    TEXT NOT NULL,
        resolved_at   TEXT NOT NULL DEFAULT '',
        resolved_by   TEXT NOT NULL DEFAULT '',
        -- One report per person per comment: re-reporting is idempotent, so a
        -- single angry reader cannot manufacture a queue signal.
        PRIMARY KEY (tenant_id, site_id, comment_id, reporter_subject_id),
        FOREIGN KEY (tenant_id, site_id, comment_id)
            REFERENCES cp_comments(tenant_id, site_id, comment_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_cp_reports_open
        ON cp_reports(tenant_id, site_id, state, created_at)
    """,
    """
    CREATE TABLE IF NOT EXISTS cp_moderation_actions (
        tenant_id     TEXT NOT NULL,
        site_id       TEXT NOT NULL,
        action_id     TEXT NOT NULL,
        comment_id    TEXT NOT NULL DEFAULT '',
        subject_id    TEXT NOT NULL DEFAULT '',
        actor_subject_id TEXT NOT NULL,
        actor_role    TEXT NOT NULL,
        action        TEXT NOT NULL,
        from_state    TEXT NOT NULL DEFAULT '',
        to_state      TEXT NOT NULL DEFAULT '',
        reason        TEXT NOT NULL DEFAULT '',
        automatic     INTEGER NOT NULL DEFAULT 0,
        rule_version  TEXT NOT NULL DEFAULT '',
        request_id    TEXT NOT NULL DEFAULT '',
        created_at    TEXT NOT NULL,
        PRIMARY KEY (tenant_id, site_id, action_id),
        FOREIGN KEY (tenant_id, site_id) REFERENCES cp_sites(tenant_id, site_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_cp_moderation_actions_comment
        ON cp_moderation_actions(tenant_id, site_id, comment_id, created_at)
    """,
    """
    CREATE TABLE IF NOT EXISTS cp_policies (
        tenant_id       TEXT NOT NULL,
        site_id         TEXT NOT NULL,
        policy_version  TEXT NOT NULL,
        moderation_mode TEXT NOT NULL DEFAULT 'pre',
        stoplist        TEXT NOT NULL DEFAULT '[]',
        max_links       INTEGER NOT NULL DEFAULT 2,
        max_length      INTEGER NOT NULL DEFAULT 4000,
        max_depth       INTEGER NOT NULL DEFAULT 3,
        rate_per_minute INTEGER NOT NULL DEFAULT 3,
        rate_per_hour   INTEGER NOT NULL DEFAULT 20,
        duplicate_window_seconds INTEGER NOT NULL DEFAULT 3600,
        updated_by      TEXT NOT NULL DEFAULT '',
        updated_at      TEXT NOT NULL,
        PRIMARY KEY (tenant_id, site_id),
        FOREIGN KEY (tenant_id, site_id) REFERENCES cp_sites(tenant_id, site_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cp_rate_events (
        tenant_id     TEXT NOT NULL,
        site_id       TEXT NOT NULL,
        bucket        TEXT NOT NULL,
        principal_key TEXT NOT NULL,
        endpoint      TEXT NOT NULL,
        occurred_at   TEXT NOT NULL,
        event_id      TEXT NOT NULL,
        PRIMARY KEY (tenant_id, site_id, event_id),
        FOREIGN KEY (tenant_id, site_id) REFERENCES cp_sites(tenant_id, site_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_cp_rate_events_window
        ON cp_rate_events(tenant_id, site_id, bucket, principal_key, occurred_at)
    """,
    """
    CREATE TABLE IF NOT EXISTS cp_content_digests (
        tenant_id     TEXT NOT NULL,
        site_id       TEXT NOT NULL,
        subject_id    TEXT NOT NULL,
        thread_id     TEXT NOT NULL,
        digest        TEXT NOT NULL,
        near_digest   TEXT NOT NULL DEFAULT '',
        comment_id    TEXT NOT NULL,
        created_at    TEXT NOT NULL,
        PRIMARY KEY (tenant_id, site_id, subject_id, thread_id, digest),
        FOREIGN KEY (tenant_id, site_id) REFERENCES cp_sites(tenant_id, site_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_cp_content_digests_near
        ON cp_content_digests(tenant_id, site_id, thread_id, near_digest, created_at)
    """,
    """
    CREATE TABLE IF NOT EXISTS cp_idempotency (
        tenant_id       TEXT NOT NULL,
        site_id         TEXT NOT NULL,
        subject_id      TEXT NOT NULL,
        idempotency_key TEXT NOT NULL,
        operation       TEXT NOT NULL,
        request_fingerprint TEXT NOT NULL,
        response_json   TEXT NOT NULL,
        created_at      TEXT NOT NULL,
        PRIMARY KEY (tenant_id, site_id, subject_id, idempotency_key),
        FOREIGN KEY (tenant_id, site_id) REFERENCES cp_sites(tenant_id, site_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cp_audit_events (
        tenant_id     TEXT NOT NULL,
        site_id       TEXT NOT NULL,
        event_id      TEXT NOT NULL,
        occurred_at   TEXT NOT NULL,
        actor_subject_id TEXT NOT NULL DEFAULT '',
        actor_role    TEXT NOT NULL DEFAULT '',
        action        TEXT NOT NULL,
        object_type   TEXT NOT NULL DEFAULT '',
        object_id     TEXT NOT NULL DEFAULT '',
        before_redacted TEXT NOT NULL DEFAULT '{}',
        after_redacted  TEXT NOT NULL DEFAULT '{}',
        reason        TEXT NOT NULL DEFAULT '',
        request_id    TEXT NOT NULL DEFAULT '',
        rule_version  TEXT NOT NULL DEFAULT '',
        artifact_hash TEXT NOT NULL DEFAULT '',
        PRIMARY KEY (tenant_id, site_id, event_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_cp_audit_events_time
        ON cp_audit_events(tenant_id, site_id, occurred_at)
    """,
    """
    CREATE TABLE IF NOT EXISTS cp_outbox (
        tenant_id     TEXT NOT NULL,
        site_id       TEXT NOT NULL,
        event_id      TEXT NOT NULL,
        event_type    TEXT NOT NULL,
        payload_json  TEXT NOT NULL,
        state         TEXT NOT NULL DEFAULT 'pending',
        attempts      INTEGER NOT NULL DEFAULT 0,
        created_at    TEXT NOT NULL,
        processed_at  TEXT NOT NULL DEFAULT '',
        PRIMARY KEY (tenant_id, site_id, event_id),
        FOREIGN KEY (tenant_id, site_id) REFERENCES cp_sites(tenant_id, site_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_cp_outbox_pending
        ON cp_outbox(tenant_id, site_id, state, created_at)
    """,
    """
    CREATE TABLE IF NOT EXISTS cp_sequences (
        tenant_id  TEXT NOT NULL,
        site_id    TEXT NOT NULL,
        name       TEXT NOT NULL,
        value      INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (tenant_id, site_id, name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cp_schema_migrations (
        version     TEXT PRIMARY KEY,
        description TEXT NOT NULL,
        applied_at  TEXT NOT NULL
    )
    """,
]

# Reverse order: children before parents, indexes before their tables.
DOWN: list[str] = [
    "DROP INDEX IF EXISTS ix_cp_outbox_pending",
    "DROP TABLE IF EXISTS cp_outbox",
    "DROP INDEX IF EXISTS ix_cp_audit_events_time",
    "DROP TABLE IF EXISTS cp_audit_events",
    "DROP TABLE IF EXISTS cp_idempotency",
    "DROP INDEX IF EXISTS ix_cp_content_digests_near",
    "DROP TABLE IF EXISTS cp_content_digests",
    "DROP INDEX IF EXISTS ix_cp_rate_events_window",
    "DROP TABLE IF EXISTS cp_rate_events",
    "DROP TABLE IF EXISTS cp_policies",
    "DROP INDEX IF EXISTS ix_cp_moderation_actions_comment",
    "DROP TABLE IF EXISTS cp_moderation_actions",
    "DROP INDEX IF EXISTS ix_cp_reports_open",
    "DROP TABLE IF EXISTS cp_reports",
    "DROP TABLE IF EXISTS cp_reactions",
    "DROP TABLE IF EXISTS cp_comment_revisions",
    "DROP INDEX IF EXISTS uq_cp_comments_seq",
    "DROP INDEX IF EXISTS ix_cp_comments_queue",
    "DROP INDEX IF EXISTS ix_cp_comments_author",
    "DROP INDEX IF EXISTS ix_cp_comments_parent",
    "DROP INDEX IF EXISTS ix_cp_comments_popular",
    "DROP INDEX IF EXISTS ix_cp_comments_thread_state_seq",
    "DROP TABLE IF EXISTS cp_comments",
    "DROP TABLE IF EXISTS cp_identities",
    "DROP INDEX IF EXISTS uq_cp_threads_resource",
    "DROP TABLE IF EXISTS cp_threads",
    "DROP TABLE IF EXISTS cp_sites",
    "DROP TABLE IF EXISTS cp_sequences",
]

# Every table this module owns. The isolation test walks this list and asserts
# that each one carries the tenant pair, so adding a table without scoping it
# fails a test rather than shipping.
TABLES = (
    "cp_sites",
    "cp_threads",
    "cp_identities",
    "cp_comments",
    "cp_comment_revisions",
    "cp_reactions",
    "cp_reports",
    "cp_moderation_actions",
    "cp_policies",
    "cp_rate_events",
    "cp_content_digests",
    "cp_idempotency",
    "cp_audit_events",
    "cp_outbox",
    "cp_sequences",
)

# Tables exempt from the tenant-pair rule. Only the migration bookkeeping table,
# which holds no tenant data at all.
UNSCOPED_TABLES = ("cp_schema_migrations",)
