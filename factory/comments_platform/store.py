"""Tenant-scoped persistence.

Every public method takes a :class:`TenantScope` as its first argument and
every statement binds it. That is a deliberate ergonomic choice: there is no
overload that omits the scope, so "forgot the WHERE clause" is not a mistake a
caller can make here — it would not compile into a call at all.

Reads that return a row also re-assert ownership of what came back. That looks
redundant next to a `WHERE tenant_id = ?`, and it is, right up until somebody
adds a join, a view or a cache in front of it. The assertion costs a string
comparison and turns a future leak into a 404.

Cursor pagination orders by `seq`, a per-site monotonic counter, not by
`created_at`. Two comments written in the same millisecond under a timestamp
cursor either both appear twice or both vanish, depending on which way the
comparison falls.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import states as state_machine
from .errors import Conflict, IdempotencyConflict, NotFound
from .schema import UP as SCHEMA_UP
from .tenancy import ResourceRef, TenantScope

ISO = "%Y-%m-%dT%H:%M:%SZ"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime(ISO)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:24]}"


@dataclass(frozen=True, slots=True)
class Page:
    """One page of comments plus the cursor that continues it."""

    items: tuple[dict[str, Any], ...]
    next_cursor: str
    has_more: bool


class CommentsStore:
    def __init__(self, db_path: str | Path, *, allow_cross_thread: bool = False) -> None:
        """`allow_cross_thread` is for a server that serialises its own access.

        SQLite's Python binding refuses cross-thread use by default, and that
        default is right: interleaved transactions on one connection corrupt
        each other's units of work. A threaded server may lift the guard only
        if it holds a lock across whole transactions — which is exactly what
        `gateway.py` does, and why the flag is named rather than implied.
        """
        self.db_path = str(db_path)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=not allow_cross_thread)
        self._conn.row_factory = sqlite3.Row
        # Composite foreign keys are the second line of tenant isolation, and
        # SQLite leaves them off unless asked, per connection.
        self._conn.execute("PRAGMA foreign_keys = ON")
        if self.db_path != ":memory:":
            # WAL is pointless for an in-memory database and SQLite silently
            # ignores the request there; asking only for file databases keeps
            # the intent readable.
            self._conn.execute("PRAGMA journal_mode = WAL")

    # --- lifecycle -------------------------------------------------------

    def create_schema(self) -> None:
        for statement in SCHEMA_UP:
            self._conn.execute(statement)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """One unit of work.

        A comment, its digest, its rate event, its audit row and its outbox
        event either all land or none do. A half-written comment with no audit
        row is worse than a refused write.
        """
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    # --- internal helpers -------------------------------------------------

    def _row_owned(self, scope: TenantScope, row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        data = dict(row)
        # Redundant next to the WHERE clause, and kept on purpose: it is what
        # survives a future join or cache landing in front of this method.
        scope.assert_owns(data["tenant_id"], data["site_id"])
        return data

    def _next_seq(self, scope: TenantScope, name: str = "comment") -> int:
        self._conn.execute(
            "INSERT INTO cp_sequences(tenant_id, site_id, name, value) VALUES (?,?,?,0)"
            " ON CONFLICT(tenant_id, site_id, name) DO NOTHING",
            (scope.tenant_id, scope.site_id, name),
        )
        self._conn.execute(
            "UPDATE cp_sequences SET value = value + 1"
            " WHERE tenant_id = ? AND site_id = ? AND name = ?",
            (scope.tenant_id, scope.site_id, name),
        )
        row = self._conn.execute(
            "SELECT value FROM cp_sequences WHERE tenant_id = ? AND site_id = ? AND name = ?",
            (scope.tenant_id, scope.site_id, name),
        ).fetchone()
        return int(row["value"])

    # --- sites ------------------------------------------------------------

    def upsert_site(self, scope: TenantScope, **values: Any) -> None:
        now = utc_now()
        columns = {
            "module_version": values.get("module_version", ""),
            "artifact_checksum": values.get("artifact_checksum", ""),
            "moderation_mode": values.get("moderation_mode", "pre"),
            "seo_mode": values.get("seo_mode", "user_initiated"),
            "read_enabled": int(values.get("read_enabled", 0)),
            "write_enabled": int(values.get("write_enabled", 0)),
            "publication_enabled": int(values.get("publication_enabled", 0)),
            "rollout_percent": int(values.get("rollout_percent", 0)),
            "max_depth": int(values.get("max_depth", 3)),
            "max_length": int(values.get("max_length", 4000)),
            "max_links": int(values.get("max_links", 2)),
        }
        names = ", ".join(columns)
        placeholders = ", ".join("?" for _ in columns)
        updates = ", ".join(f"{k}=excluded.{k}" for k in columns)
        self._conn.execute(
            f"INSERT INTO cp_sites(tenant_id, site_id, {names}, created_at, updated_at)"
            f" VALUES (?,?,{placeholders},?,?)"
            f" ON CONFLICT(tenant_id, site_id) DO UPDATE SET {updates}, updated_at=excluded.updated_at",
            (scope.tenant_id, scope.site_id, *columns.values(), now, now),
        )

    def get_site(self, scope: TenantScope) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM cp_sites WHERE tenant_id = ? AND site_id = ?",
            (scope.tenant_id, scope.site_id),
        ).fetchone()
        return self._row_owned(scope, row)

    # --- identities -------------------------------------------------------

    def upsert_identity(
        self, scope: TenantScope, subject_id: str, *, display_name: str = "", is_guest: bool = True
    ) -> None:
        now = utc_now()
        self._conn.execute(
            "INSERT INTO cp_identities(tenant_id, site_id, subject_id, display_name, is_guest,"
            " created_at, updated_at) VALUES (?,?,?,?,?,?,?)"
            " ON CONFLICT(tenant_id, site_id, subject_id) DO UPDATE SET"
            " display_name=excluded.display_name, updated_at=excluded.updated_at",
            (scope.tenant_id, scope.site_id, subject_id, display_name, int(is_guest), now, now),
        )

    def get_identity(self, scope: TenantScope, subject_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM cp_identities WHERE tenant_id = ? AND site_id = ? AND subject_id = ?",
            (scope.tenant_id, scope.site_id, subject_id),
        ).fetchone()
        return self._row_owned(scope, row)

    def set_ban(
        self, scope: TenantScope, subject_id: str, *, banned: bool, reason: str = ""
    ) -> None:
        """Bans are per site. They do not travel between tenants by design."""
        self._conn.execute(
            "UPDATE cp_identities SET banned = ?, ban_reason = ?, banned_at = ?, updated_at = ?"
            " WHERE tenant_id = ? AND site_id = ? AND subject_id = ?",
            (
                int(banned), reason, utc_now() if banned else "", utc_now(),
                scope.tenant_id, scope.site_id, subject_id,
            ),
        )

    def is_banned(self, scope: TenantScope, subject_id: str) -> bool:
        row = self.get_identity(scope, subject_id)
        return bool(row and row["banned"])

    # --- threads ----------------------------------------------------------

    def get_or_create_thread(self, scope: TenantScope, ref: ResourceRef) -> dict[str, Any]:
        row = self._conn.execute(
            "SELECT * FROM cp_threads WHERE tenant_id = ? AND site_id = ?"
            " AND resource_type = ? AND canonical_content_id = ?",
            (scope.tenant_id, scope.site_id, ref.resource_type, ref.canonical_content_id),
        ).fetchone()
        existing = self._row_owned(scope, row)
        if existing:
            return existing

        now = utc_now()
        thread_id = new_id("th")
        self._conn.execute(
            "INSERT INTO cp_threads(tenant_id, site_id, thread_id, resource_type,"
            " canonical_content_id, comment_count, locked, created_at, updated_at)"
            " VALUES (?,?,?,?,?,0,0,?,?)",
            (
                scope.tenant_id, scope.site_id, thread_id,
                ref.resource_type, ref.canonical_content_id, now, now,
            ),
        )
        return self.get_thread(scope, thread_id)

    def get_thread(self, scope: TenantScope, thread_id: str) -> dict[str, Any]:
        row = self._conn.execute(
            "SELECT * FROM cp_threads WHERE tenant_id = ? AND site_id = ? AND thread_id = ?",
            (scope.tenant_id, scope.site_id, thread_id),
        ).fetchone()
        thread = self._row_owned(scope, row)
        if thread is None:
            raise NotFound("thread not found", thread_id=thread_id)
        return thread

    def find_thread(self, scope: TenantScope, ref: ResourceRef) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM cp_threads WHERE tenant_id = ? AND site_id = ?"
            " AND resource_type = ? AND canonical_content_id = ?",
            (scope.tenant_id, scope.site_id, ref.resource_type, ref.canonical_content_id),
        ).fetchone()
        return self._row_owned(scope, row)

    def refresh_thread_count(self, scope: TenantScope, thread_id: str) -> int:
        """Recompute from rows rather than incrementing a counter.

        A counter that drifts is worse than a slightly slower query, because
        nothing ever tells you it drifted. `states.COUNTED_STATES` is the one
        definition of what counts, shared with the public read path.
        """
        placeholders = ",".join("?" for _ in state_machine.COUNTED_STATES)
        counted = tuple(sorted(state_machine.COUNTED_STATES))
        row = self._conn.execute(
            f"SELECT COUNT(*) AS n FROM cp_comments WHERE tenant_id = ? AND site_id = ?"
            f" AND thread_id = ? AND state IN ({placeholders})",
            (scope.tenant_id, scope.site_id, thread_id, *counted),
        ).fetchone()
        count = int(row["n"])
        self._conn.execute(
            "UPDATE cp_threads SET comment_count = ?, updated_at = ?"
            " WHERE tenant_id = ? AND site_id = ? AND thread_id = ?",
            (count, utc_now(), scope.tenant_id, scope.site_id, thread_id),
        )
        return count

    # --- comments ---------------------------------------------------------

    def insert_comment(
        self,
        scope: TenantScope,
        *,
        thread_id: str,
        subject_id: str,
        body: str,
        body_html: str,
        state: str,
        parent_id: str = "",
        depth: int = 0,
        risk_score: int = 0,
    ) -> dict[str, Any]:
        now = utc_now()
        comment_id = new_id("c")
        seq = self._next_seq(scope)
        self._conn.execute(
            "INSERT INTO cp_comments(tenant_id, site_id, comment_id, thread_id, parent_id, depth,"
            " subject_id, body, body_html, state, revision, reaction_count, reply_count,"
            " report_count, risk_score, created_at, updated_at, edited_at, seq)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,1,0,0,0,?,?,?,'',?)",
            (
                scope.tenant_id, scope.site_id, comment_id, thread_id, parent_id, depth,
                subject_id, body, body_html, state, risk_score, now, now, seq,
            ),
        )
        if parent_id:
            self._conn.execute(
                "UPDATE cp_comments SET reply_count = reply_count + 1"
                " WHERE tenant_id = ? AND site_id = ? AND comment_id = ?",
                (scope.tenant_id, scope.site_id, parent_id),
            )
        return self.get_comment(scope, comment_id)

    def get_comment(self, scope: TenantScope, comment_id: str) -> dict[str, Any]:
        row = self._conn.execute(
            "SELECT * FROM cp_comments WHERE tenant_id = ? AND site_id = ? AND comment_id = ?",
            (scope.tenant_id, scope.site_id, comment_id),
        ).fetchone()
        comment = self._row_owned(scope, row)
        if comment is None:
            # 404 whether it is missing or another tenant's. The caller cannot
            # tell, and that is the point.
            raise NotFound("comment not found", comment_id=comment_id)
        return comment

    def update_comment_body(
        self,
        scope: TenantScope,
        comment_id: str,
        *,
        body: str,
        body_html: str,
        state: str,
        editor_subject_id: str,
        reason: str = "",
    ) -> dict[str, Any]:
        current = self.get_comment(scope, comment_id)
        revision = int(current["revision"]) + 1
        now = utc_now()
        # The previous body is preserved before the update, so the revision
        # history is complete even if the process dies mid-transaction.
        self._conn.execute(
            "INSERT INTO cp_comment_revisions(tenant_id, site_id, comment_id, revision, body,"
            " editor_subject_id, reason, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (
                scope.tenant_id, scope.site_id, comment_id, int(current["revision"]),
                current["body"], editor_subject_id, reason, now,
            ),
        )
        self._conn.execute(
            "UPDATE cp_comments SET body = ?, body_html = ?, state = ?, revision = ?,"
            " updated_at = ?, edited_at = ?"
            " WHERE tenant_id = ? AND site_id = ? AND comment_id = ?",
            (
                body, body_html, state, revision, now, now,
                scope.tenant_id, scope.site_id, comment_id,
            ),
        )
        return self.get_comment(scope, comment_id)

    def list_revisions(self, scope: TenantScope, comment_id: str) -> tuple[dict[str, Any], ...]:
        self.get_comment(scope, comment_id)  # ownership gate before disclosing history
        rows = self._conn.execute(
            "SELECT * FROM cp_comment_revisions WHERE tenant_id = ? AND site_id = ?"
            " AND comment_id = ? ORDER BY revision",
            (scope.tenant_id, scope.site_id, comment_id),
        ).fetchall()
        return tuple(dict(r) for r in rows)

    def set_state(
        self, scope: TenantScope, comment_id: str, new_state: str
    ) -> dict[str, Any]:
        self.get_comment(scope, comment_id)
        self._conn.execute(
            "UPDATE cp_comments SET state = ?, updated_at = ?"
            " WHERE tenant_id = ? AND site_id = ? AND comment_id = ?",
            (new_state, utc_now(), scope.tenant_id, scope.site_id, comment_id),
        )
        return self.get_comment(scope, comment_id)

    # --- reading ----------------------------------------------------------

    SORTS = ("new", "old", "popular")

    def list_comments(
        self,
        scope: TenantScope,
        thread_id: str,
        *,
        visible_states: Iterable[str],
        sort: str = "new",
        limit: int = 20,
        cursor: str = "",
        include_subject_id: str = "",
    ) -> Page:
        """A page of comments the caller is entitled to see.

        `visible_states` is supplied by the caller rather than assumed, so the
        public path and the author path share one query and differ only in what
        they are allowed to ask for. `include_subject_id` widens the set for
        exactly one author's own rows and nobody else's.
        """
        if sort not in self.SORTS:
            sort = "new"
        limit = max(1, min(int(limit), 100))

        states_tuple = tuple(sorted(set(visible_states)))
        if not states_tuple:
            return Page(items=(), next_cursor="", has_more=False)

        placeholders = ",".join("?" for _ in states_tuple)
        where = [
            "tenant_id = ?", "site_id = ?", "thread_id = ?",
            f"state IN ({placeholders})",
        ]
        params: list[Any] = [scope.tenant_id, scope.site_id, thread_id, *states_tuple]

        if include_subject_id:
            # The author's own non-public rows, widened only for that author.
            author_states = tuple(sorted(state_machine.AUTHOR_VISIBLE))
            author_placeholders = ",".join("?" for _ in author_states)
            where[-1] = (
                f"(state IN ({placeholders})"
                f" OR (subject_id = ? AND state IN ({author_placeholders})))"
            )
            params.append(include_subject_id)
            params.extend(author_states)

        order, cursor_op = {
            "new": ("seq DESC", "<"),
            "old": ("seq ASC", ">"),
            "popular": ("reaction_count DESC, seq DESC", "<"),
        }[sort]

        if cursor:
            try:
                cursor_seq = int(cursor)
            except (TypeError, ValueError) as exc:
                raise Conflict("malformed cursor") from exc
            where.append(f"seq {cursor_op} ?")
            params.append(cursor_seq)

        sql = (
            f"SELECT * FROM cp_comments WHERE {' AND '.join(where)}"
            f" ORDER BY {order} LIMIT ?"
        )
        params.append(limit + 1)  # one extra row answers has_more without a second query
        rows = self._conn.execute(sql, params).fetchall()

        items = [self._row_owned(scope, r) for r in rows]
        has_more = len(items) > limit
        items = items[:limit]
        next_cursor = str(items[-1]["seq"]) if (has_more and items) else ""
        return Page(items=tuple(i for i in items if i), next_cursor=next_cursor, has_more=has_more)

    def count_comments(self, scope: TenantScope, thread_id: str) -> int:
        thread = self.get_thread(scope, thread_id)
        return int(thread["comment_count"])

    def moderation_queue(
        self, scope: TenantScope, *, limit: int = 50, cursor: str = ""
    ) -> Page:
        queue_states = tuple(sorted(state_machine.QUEUE_STATES))
        placeholders = ",".join("?" for _ in queue_states)
        where = [
            "tenant_id = ?", "site_id = ?", f"state IN ({placeholders})",
        ]
        params: list[Any] = [scope.tenant_id, scope.site_id, *queue_states]
        if cursor:
            where.append("seq > ?")
            params.append(int(cursor))
        limit = max(1, min(int(limit), 200))
        params.append(limit + 1)
        rows = self._conn.execute(
            f"SELECT * FROM cp_comments WHERE {' AND '.join(where)} ORDER BY seq ASC LIMIT ?",
            params,
        ).fetchall()
        items = [self._row_owned(scope, r) for r in rows]
        has_more = len(items) > limit
        items = items[:limit]
        return Page(
            items=tuple(i for i in items if i),
            next_cursor=str(items[-1]["seq"]) if (has_more and items) else "",
            has_more=has_more,
        )

    # --- reactions --------------------------------------------------------

    def set_reaction(
        self, scope: TenantScope, comment_id: str, subject_id: str, reaction: str
    ) -> None:
        self.get_comment(scope, comment_id)
        now = utc_now()
        self._conn.execute(
            "INSERT INTO cp_reactions(tenant_id, site_id, comment_id, subject_id, reaction,"
            " created_at, updated_at) VALUES (?,?,?,?,?,?,?)"
            " ON CONFLICT(tenant_id, site_id, comment_id, subject_id) DO UPDATE SET"
            " reaction=excluded.reaction, updated_at=excluded.updated_at",
            (scope.tenant_id, scope.site_id, comment_id, subject_id, reaction, now, now),
        )
        self.refresh_reaction_count(scope, comment_id)

    def clear_reaction(self, scope: TenantScope, comment_id: str, subject_id: str) -> None:
        self.get_comment(scope, comment_id)
        self._conn.execute(
            "DELETE FROM cp_reactions WHERE tenant_id = ? AND site_id = ?"
            " AND comment_id = ? AND subject_id = ?",
            (scope.tenant_id, scope.site_id, comment_id, subject_id),
        )
        self.refresh_reaction_count(scope, comment_id)

    def get_reaction(
        self, scope: TenantScope, comment_id: str, subject_id: str
    ) -> str:
        row = self._conn.execute(
            "SELECT reaction FROM cp_reactions WHERE tenant_id = ? AND site_id = ?"
            " AND comment_id = ? AND subject_id = ?",
            (scope.tenant_id, scope.site_id, comment_id, subject_id),
        ).fetchone()
        return str(row["reaction"]) if row else ""

    def refresh_reaction_count(self, scope: TenantScope, comment_id: str) -> int:
        """Deterministic recount, never an increment."""
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM cp_reactions WHERE tenant_id = ? AND site_id = ?"
            " AND comment_id = ?",
            (scope.tenant_id, scope.site_id, comment_id),
        ).fetchone()
        count = int(row["n"])
        self._conn.execute(
            "UPDATE cp_comments SET reaction_count = ? WHERE tenant_id = ? AND site_id = ?"
            " AND comment_id = ?",
            (count, scope.tenant_id, scope.site_id, comment_id),
        )
        return count

    # --- reports ----------------------------------------------------------

    def add_report(
        self,
        scope: TenantScope,
        comment_id: str,
        reporter_subject_id: str,
        *,
        reason: str,
        note: str = "",
        network_hmac: str = "",
    ) -> bool:
        """Returns True if this is a new report, False if the person repeated one."""
        self.get_comment(scope, comment_id)
        cursor = self._conn.execute(
            "INSERT INTO cp_reports(tenant_id, site_id, comment_id, reporter_subject_id, reason,"
            " note, state, network_hmac, created_at) VALUES (?,?,?,?,?,?,'open',?,?)"
            " ON CONFLICT(tenant_id, site_id, comment_id, reporter_subject_id) DO NOTHING",
            (
                scope.tenant_id, scope.site_id, comment_id, reporter_subject_id,
                reason, note, network_hmac, utc_now(),
            ),
        )
        created = cursor.rowcount > 0
        if created:
            self.refresh_report_count(scope, comment_id)
        return created

    def refresh_report_count(self, scope: TenantScope, comment_id: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM cp_reports WHERE tenant_id = ? AND site_id = ?"
            " AND comment_id = ? AND state = 'open'",
            (scope.tenant_id, scope.site_id, comment_id),
        ).fetchone()
        count = int(row["n"])
        self._conn.execute(
            "UPDATE cp_comments SET report_count = ? WHERE tenant_id = ? AND site_id = ?"
            " AND comment_id = ?",
            (count, scope.tenant_id, scope.site_id, comment_id),
        )
        return count

    def list_reports(
        self, scope: TenantScope, comment_id: str = "", *, state: str = "open"
    ) -> tuple[dict[str, Any], ...]:
        sql = "SELECT * FROM cp_reports WHERE tenant_id = ? AND site_id = ? AND state = ?"
        params: list[Any] = [scope.tenant_id, scope.site_id, state]
        if comment_id:
            sql += " AND comment_id = ?"
            params.append(comment_id)
        sql += " ORDER BY created_at"
        rows = self._conn.execute(sql, params).fetchall()
        return tuple(self._row_owned(scope, r) or {} for r in rows)

    def resolve_reports(
        self, scope: TenantScope, comment_id: str, *, resolved_by: str
    ) -> int:
        cursor = self._conn.execute(
            "UPDATE cp_reports SET state = 'resolved', resolved_at = ?, resolved_by = ?"
            " WHERE tenant_id = ? AND site_id = ? AND comment_id = ? AND state = 'open'",
            (utc_now(), resolved_by, scope.tenant_id, scope.site_id, comment_id),
        )
        self.refresh_report_count(scope, comment_id)
        return cursor.rowcount

    def distinct_reporters(self, scope: TenantScope, comment_id: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(DISTINCT reporter_subject_id) AS n FROM cp_reports"
            " WHERE tenant_id = ? AND site_id = ? AND comment_id = ? AND state = 'open'",
            (scope.tenant_id, scope.site_id, comment_id),
        ).fetchone()
        return int(row["n"])

    def distinct_report_networks(self, scope: TenantScope, comment_id: str) -> int:
        """How many *distinct places* reported this.

        Brigading looks like many reporters; it is distinguishable from real
        outrage mostly by those reporters sharing one network identifier.
        """
        row = self._conn.execute(
            "SELECT COUNT(DISTINCT network_hmac) AS n FROM cp_reports"
            " WHERE tenant_id = ? AND site_id = ? AND comment_id = ?"
            " AND state = 'open' AND network_hmac != ''",
            (scope.tenant_id, scope.site_id, comment_id),
        ).fetchone()
        return int(row["n"])

    # --- moderation actions (append-only) ---------------------------------

    def record_moderation_action(
        self,
        scope: TenantScope,
        *,
        action: str,
        actor_subject_id: str,
        actor_role: str,
        comment_id: str = "",
        subject_id: str = "",
        from_state: str = "",
        to_state: str = "",
        reason: str = "",
        automatic: bool = False,
        rule_version: str = "",
        request_id: str = "",
    ) -> str:
        action_id = new_id("ma")
        self._conn.execute(
            "INSERT INTO cp_moderation_actions(tenant_id, site_id, action_id, comment_id,"
            " subject_id, actor_subject_id, actor_role, action, from_state, to_state, reason,"
            " automatic, rule_version, request_id, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                scope.tenant_id, scope.site_id, action_id, comment_id, subject_id,
                actor_subject_id, actor_role, action, from_state, to_state, reason,
                int(automatic), rule_version, request_id, utc_now(),
            ),
        )
        return action_id

    def list_moderation_actions(
        self, scope: TenantScope, comment_id: str = ""
    ) -> tuple[dict[str, Any], ...]:
        sql = "SELECT * FROM cp_moderation_actions WHERE tenant_id = ? AND site_id = ?"
        params: list[Any] = [scope.tenant_id, scope.site_id]
        if comment_id:
            sql += " AND comment_id = ?"
            params.append(comment_id)
        sql += " ORDER BY created_at, action_id"
        rows = self._conn.execute(sql, params).fetchall()
        return tuple(self._row_owned(scope, r) or {} for r in rows)

    # --- policies ---------------------------------------------------------

    def upsert_policy(self, scope: TenantScope, **values: Any) -> None:
        columns = {
            "policy_version": values.get("policy_version", "v1"),
            "moderation_mode": values.get("moderation_mode", "pre"),
            "stoplist": json.dumps(values.get("stoplist", []), ensure_ascii=False),
            "max_links": int(values.get("max_links", 2)),
            "max_length": int(values.get("max_length", 4000)),
            "max_depth": int(values.get("max_depth", 3)),
            "rate_per_minute": int(values.get("rate_per_minute", 3)),
            "rate_per_hour": int(values.get("rate_per_hour", 20)),
            "duplicate_window_seconds": int(values.get("duplicate_window_seconds", 3600)),
            "updated_by": values.get("updated_by", ""),
        }
        names = ", ".join(columns)
        placeholders = ", ".join("?" for _ in columns)
        updates = ", ".join(f"{k}=excluded.{k}" for k in columns)
        self._conn.execute(
            f"INSERT INTO cp_policies(tenant_id, site_id, {names}, updated_at)"
            f" VALUES (?,?,{placeholders},?)"
            f" ON CONFLICT(tenant_id, site_id) DO UPDATE SET {updates},"
            f" updated_at=excluded.updated_at",
            (scope.tenant_id, scope.site_id, *columns.values(), utc_now()),
        )

    def get_policy(self, scope: TenantScope) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM cp_policies WHERE tenant_id = ? AND site_id = ?",
            (scope.tenant_id, scope.site_id),
        ).fetchone()
        policy = self._row_owned(scope, row)
        if policy:
            policy["stoplist"] = json.loads(policy["stoplist"] or "[]")
        return policy

    # --- rate limiting ----------------------------------------------------

    def record_rate_event(
        self, scope: TenantScope, *, bucket: str, principal_key: str, endpoint: str
    ) -> None:
        self._conn.execute(
            "INSERT INTO cp_rate_events(tenant_id, site_id, bucket, principal_key, endpoint,"
            " occurred_at, event_id) VALUES (?,?,?,?,?,?,?)",
            (
                scope.tenant_id, scope.site_id, bucket, principal_key, endpoint,
                utc_now(), new_id("re"),
            ),
        )

    def count_rate_events(
        self, scope: TenantScope, *, bucket: str, principal_key: str, since_iso: str
    ) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM cp_rate_events WHERE tenant_id = ? AND site_id = ?"
            " AND bucket = ? AND principal_key = ? AND occurred_at >= ?",
            (scope.tenant_id, scope.site_id, bucket, principal_key, since_iso),
        ).fetchone()
        return int(row["n"])

    def purge_rate_events_before(self, scope: TenantScope, before_iso: str) -> int:
        """Retention enforcement for network-derived rows."""
        cursor = self._conn.execute(
            "DELETE FROM cp_rate_events WHERE tenant_id = ? AND site_id = ? AND occurred_at < ?",
            (scope.tenant_id, scope.site_id, before_iso),
        )
        return cursor.rowcount

    # --- duplicate detection ---------------------------------------------

    def record_digest(
        self,
        scope: TenantScope,
        *,
        subject_id: str,
        thread_id: str,
        digest: str,
        near_digest: str,
        comment_id: str,
    ) -> None:
        self._conn.execute(
            "INSERT INTO cp_content_digests(tenant_id, site_id, subject_id, thread_id, digest,"
            " near_digest, comment_id, created_at) VALUES (?,?,?,?,?,?,?,?)"
            " ON CONFLICT(tenant_id, site_id, subject_id, thread_id, digest) DO NOTHING",
            (
                scope.tenant_id, scope.site_id, subject_id, thread_id, digest,
                near_digest, comment_id, utc_now(),
            ),
        )

    def digest_seen(
        self, scope: TenantScope, *, subject_id: str, thread_id: str, digest: str, since_iso: str
    ) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM cp_content_digests WHERE tenant_id = ? AND site_id = ?"
            " AND subject_id = ? AND thread_id = ? AND digest = ? AND created_at >= ?",
            (scope.tenant_id, scope.site_id, subject_id, thread_id, digest, since_iso),
        ).fetchone()
        return row is not None

    def near_digest_count(
        self, scope: TenantScope, *, thread_id: str, near_digest: str, since_iso: str
    ) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM cp_content_digests WHERE tenant_id = ? AND site_id = ?"
            " AND thread_id = ? AND near_digest = ? AND created_at >= ?",
            (scope.tenant_id, scope.site_id, thread_id, near_digest, since_iso),
        ).fetchone()
        return int(row["n"])

    # --- idempotency ------------------------------------------------------

    def idempotent_replay(
        self, scope: TenantScope, *, subject_id: str, key: str, fingerprint: str
    ) -> dict[str, Any] | None:
        """Return the first response for this key, or raise if the body differs."""
        row = self._conn.execute(
            "SELECT * FROM cp_idempotency WHERE tenant_id = ? AND site_id = ?"
            " AND subject_id = ? AND idempotency_key = ?",
            (scope.tenant_id, scope.site_id, subject_id, key),
        ).fetchone()
        record = self._row_owned(scope, row)
        if record is None:
            return None
        if record["request_fingerprint"] != fingerprint:
            # Same key, different content: one of the two writes would be lost.
            raise IdempotencyConflict(
                "idempotency key reused with a different payload", key=key
            )
        return json.loads(record["response_json"])

    def remember_idempotent(
        self,
        scope: TenantScope,
        *,
        subject_id: str,
        key: str,
        operation: str,
        fingerprint: str,
        response: dict[str, Any],
    ) -> None:
        self._conn.execute(
            "INSERT INTO cp_idempotency(tenant_id, site_id, subject_id, idempotency_key,"
            " operation, request_fingerprint, response_json, created_at) VALUES (?,?,?,?,?,?,?,?)"
            " ON CONFLICT(tenant_id, site_id, subject_id, idempotency_key) DO NOTHING",
            (
                scope.tenant_id, scope.site_id, subject_id, key, operation, fingerprint,
                json.dumps(response, ensure_ascii=False), utc_now(),
            ),
        )

    # --- audit (append-only) ----------------------------------------------

    def append_audit(self, scope: TenantScope, event: dict[str, Any]) -> str:
        event_id = event.get("event_id") or new_id("ae")
        self._conn.execute(
            "INSERT INTO cp_audit_events(tenant_id, site_id, event_id, occurred_at,"
            " actor_subject_id, actor_role, action, object_type, object_id, before_redacted,"
            " after_redacted, reason, request_id, rule_version, artifact_hash)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                scope.tenant_id, scope.site_id, event_id,
                event.get("occurred_at") or utc_now(),
                event.get("actor_subject_id", ""), event.get("actor_role", ""),
                event["action"], event.get("object_type", ""), event.get("object_id", ""),
                json.dumps(event.get("before_redacted", {}), ensure_ascii=False),
                json.dumps(event.get("after_redacted", {}), ensure_ascii=False),
                event.get("reason", ""), event.get("request_id", ""),
                event.get("rule_version", ""), event.get("artifact_hash", ""),
            ),
        )
        return event_id

    def list_audit(
        self, scope: TenantScope, *, limit: int = 100
    ) -> tuple[dict[str, Any], ...]:
        rows = self._conn.execute(
            "SELECT * FROM cp_audit_events WHERE tenant_id = ? AND site_id = ?"
            " ORDER BY occurred_at, event_id LIMIT ?",
            (scope.tenant_id, scope.site_id, max(1, min(int(limit), 1000))),
        ).fetchall()
        return tuple(self._row_owned(scope, r) or {} for r in rows)

    # --- outbox -----------------------------------------------------------

    def enqueue_event(
        self, scope: TenantScope, *, event_type: str, payload: dict[str, Any]
    ) -> str:
        event_id = new_id("ev")
        self._conn.execute(
            "INSERT INTO cp_outbox(tenant_id, site_id, event_id, event_type, payload_json,"
            " state, attempts, created_at) VALUES (?,?,?,?,?,'pending',0,?)",
            (
                scope.tenant_id, scope.site_id, event_id, event_type,
                json.dumps(payload, ensure_ascii=False), utc_now(),
            ),
        )
        return event_id

    def claim_events(
        self, scope: TenantScope, *, limit: int = 10
    ) -> tuple[dict[str, Any], ...]:
        """A background worker's view is scoped too.

        A worker that drains "all pending events" is the classic way isolation
        is lost after the API got it right.
        """
        rows = self._conn.execute(
            "SELECT * FROM cp_outbox WHERE tenant_id = ? AND site_id = ? AND state = 'pending'"
            " ORDER BY created_at LIMIT ?",
            (scope.tenant_id, scope.site_id, max(1, min(int(limit), 100))),
        ).fetchall()
        return tuple(self._row_owned(scope, r) or {} for r in rows)

    def mark_event_processed(self, scope: TenantScope, event_id: str) -> None:
        self._conn.execute(
            "UPDATE cp_outbox SET state = 'processed', processed_at = ?, attempts = attempts + 1"
            " WHERE tenant_id = ? AND site_id = ? AND event_id = ?",
            (utc_now(), scope.tenant_id, scope.site_id, event_id),
        )

    # --- privacy ----------------------------------------------------------

    def export_subject(self, scope: TenantScope, subject_id: str) -> dict[str, Any]:
        """Everything this site holds about one person. Nothing from elsewhere."""
        comments = self._conn.execute(
            "SELECT comment_id, thread_id, body, state, created_at, updated_at"
            " FROM cp_comments WHERE tenant_id = ? AND site_id = ? AND subject_id = ?"
            " ORDER BY seq",
            (scope.tenant_id, scope.site_id, subject_id),
        ).fetchall()
        reactions = self._conn.execute(
            "SELECT comment_id, reaction, created_at FROM cp_reactions"
            " WHERE tenant_id = ? AND site_id = ? AND subject_id = ?",
            (scope.tenant_id, scope.site_id, subject_id),
        ).fetchall()
        reports = self._conn.execute(
            "SELECT comment_id, reason, state, created_at FROM cp_reports"
            " WHERE tenant_id = ? AND site_id = ? AND reporter_subject_id = ?",
            (scope.tenant_id, scope.site_id, subject_id),
        ).fetchall()
        return {
            "tenant_id": scope.tenant_id,
            "site_id": scope.site_id,
            "subject_id": subject_id,
            "identity": self.get_identity(scope, subject_id) or {},
            "comments": [dict(r) for r in comments],
            "reactions": [dict(r) for r in reactions],
            "reports": [dict(r) for r in reports],
        }

    def anonymize_subject(self, scope: TenantScope, subject_id: str) -> int:
        """Detach a person from their comments without destroying the thread.

        Deleting the rows outright would punch holes in every conversation the
        person took part in. Replacing the author and clearing the profile
        satisfies the erasure request while leaving the replies legible.
        """
        anon = f"anon_{uuid.uuid4().hex[:16]}"
        # The placeholder identity must exist *before* any comment points at
        # it: `cp_comments` carries a composite foreign key to `cp_identities`,
        # so reassigning first fails with an integrity error. The original
        # order did exactly that, and only a file database with foreign keys
        # enforced revealed it.
        self._conn.execute(
            "INSERT INTO cp_identities(tenant_id, site_id, subject_id, display_name, is_guest,"
            " created_at, updated_at) VALUES (?,?,?,'',1,?,?)"
            " ON CONFLICT(tenant_id, site_id, subject_id) DO NOTHING",
            (scope.tenant_id, scope.site_id, anon, utc_now(), utc_now()),
        )
        cursor = self._conn.execute(
            "UPDATE cp_comments SET subject_id = ? WHERE tenant_id = ? AND site_id = ?"
            " AND subject_id = ?",
            (anon, scope.tenant_id, scope.site_id, subject_id),
        )
        self._conn.execute(
            "DELETE FROM cp_reactions WHERE tenant_id = ? AND site_id = ? AND subject_id = ?",
            (scope.tenant_id, scope.site_id, subject_id),
        )
        self._conn.execute(
            "UPDATE cp_identities SET display_name = '', reputation = 0"
            " WHERE tenant_id = ? AND site_id = ? AND subject_id = ?",
            (scope.tenant_id, scope.site_id, subject_id),
        )
        return cursor.rowcount

    # --- diagnostics ------------------------------------------------------

    def table_names(self) -> tuple[str, ...]:
        rows = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE 'cp_%'"
            " ORDER BY name"
        ).fetchall()
        return tuple(r["name"] for r in rows)

    def columns_of(self, table: str) -> tuple[str, ...]:
        rows = self._conn.execute(f"PRAGMA table_info({table})").fetchall()
        return tuple(r["name"] for r in rows)

    def raw_count(self, table: str, scope: TenantScope | None = None) -> int:
        """Unscoped count, for tests that must prove isolation from outside."""
        if scope is None:
            row = self._conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
        else:
            row = self._conn.execute(
                f"SELECT COUNT(*) AS n FROM {table} WHERE tenant_id = ? AND site_id = ?",
                (scope.tenant_id, scope.site_id),
            ).fetchone()
        return int(row["n"])

    def execute_raw(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        """Escape hatch for tests and the backup rehearsal. Not used by the service."""
        return [dict(r) for r in self._conn.execute(sql, params).fetchall()]
