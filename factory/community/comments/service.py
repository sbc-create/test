"""Comments service — create/edit/delete/reply/list/report/moderate.

All writes are gated by COMMENTS_API_WRITE_ENABLED (default 0).
Publication to the public web is additionally gated by
COMMENTS_PUBLICATION_ENABLED (hard-locked 0). Soft-delete only.
"""

from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from factory.community.comments import flags as comment_flags
from factory.community.comments.labels import label_comment
from factory.community.comments.sanitize import sanitize_body
from factory.community.store import CommunityStore

MAX_REPLY_DEPTH = 1  # root=0, reply=1; no nested replies
RATE_LIMIT_WINDOW_SEC = 60
RATE_LIMIT_MAX = 5
DUPLICATE_WINDOW_SEC = 300


class CommentsError(Exception):
    status = 400
    code = "CommentsError"


class CommentsWriteDisabled(CommentsError):
    status = 403
    code = "CommentsWriteDisabled"


class CommentsNotFound(CommentsError):
    status = 404
    code = "CommentsNotFound"


class CommentsForbidden(CommentsError):
    status = 403
    code = "CommentsForbidden"


class CommentsConflict(CommentsError):
    status = 409
    code = "CommentsConflict"


class CommentsRateLimited(CommentsError):
    status = 429
    code = "CommentsRateLimited"


class CommentsValidationError(CommentsError):
    status = 400
    code = "CommentsValidationError"


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class CommentsService:
    """Ledger operations for community comments (isolated from vote aggregates)."""

    def __init__(self, store: CommunityStore) -> None:
        self.store = store
        self._lock = threading.RLock()

    def _require_write(self) -> None:
        comment_flags.assert_comments_dark()
        if not comment_flags.writes_enabled():
            raise CommentsWriteDisabled("COMMENTS_API_WRITE_ENABLED=0")
        if comment_flags.ADMIN_FAKE_COMMENT_INSERT:
            raise CommentsForbidden("ADMIN_FAKE_COMMENT_INSERT forbidden")

    def _check_rate(self, *, identity_id: str, site_space: str, title_id: str, action: str) -> None:
        cutoff = time.time() - RATE_LIMIT_WINDOW_SEC
        # Store uses ISO timestamps; compare via recent count in-process + ledger.
        rows = self.store.conn.execute(
            """SELECT created_at FROM community_comment_rate_limit_events
               WHERE identity_id=? ORDER BY created_at DESC LIMIT ?""",
            (identity_id, RATE_LIMIT_MAX + 2),
        ).fetchall()
        recent = 0
        for row in rows:
            try:
                # Accept both epoch-ish and ISO; ISO compare lexicographically for Zulu.
                ts = str(row["created_at"])
                if ts >= datetime.fromtimestamp(cutoff, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"):
                    recent += 1
            except Exception:
                recent += 1
        if recent >= RATE_LIMIT_MAX:
            raise CommentsRateLimited("comment rate limit exceeded")
        self.store.conn.execute(
            """INSERT INTO community_comment_rate_limit_events
               (event_id, identity_id, site_space, title_id, action, created_at)
               VALUES (?,?,?,?,?,?)""",
            (_new_id("crl"), identity_id, site_space, title_id, action, _utc()),
        )

    def _row(self, comment_id: str) -> dict[str, Any] | None:
        row = self.store.conn.execute(
            "SELECT * FROM community_comments WHERE comment_id=?", (comment_id,)
        ).fetchone()
        return dict(row) if row else None

    def _record_revision(
        self,
        *,
        comment_id: str,
        version: int,
        body: str,
        body_normalized: str,
        editor_identity_id: str,
        edit_reason: str = "",
    ) -> None:
        self.store.conn.execute(
            """INSERT INTO community_comment_revisions
               (revision_id, comment_id, version, body, body_normalized,
                editor_identity_id, edit_reason, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                _new_id("crev"),
                comment_id,
                version,
                body,
                body_normalized,
                editor_identity_id,
                edit_reason,
                _utc(),
            ),
        )

    def _record_moderation(
        self,
        *,
        comment_id: str,
        action: str,
        actor_identity_id: str,
        reason_code: str,
        prior_status: str,
        new_status: str,
        detail: str = "",
        actor_role: str = "moderator",
    ) -> None:
        self.store.conn.execute(
            """INSERT INTO community_comment_moderation_events
               (event_id, comment_id, action, actor_role, actor_identity_id,
                reason_code, detail, prior_status, new_status, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                _new_id("cmod"),
                comment_id,
                action,
                actor_role,
                actor_identity_id,
                reason_code,
                detail,
                prior_status,
                new_status,
                _utc(),
            ),
        )

    def _record_risk(self, *, comment_id: str, identity_id: str, labels: dict[str, Any]) -> None:
        import json

        self.store.conn.execute(
            """INSERT INTO community_comment_risk_signals
               (signal_id, comment_id, identity_id, signal_type, score, detail_json, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (
                _new_id("crisk"),
                comment_id,
                identity_id,
                "LABELS_V1",
                float(labels.get("risk_score") or 0),
                json.dumps(
                    {
                        "toxicity": labels.get("toxicity_score"),
                        "spam": labels.get("spam_score"),
                        "spoiler": labels.get("spoiler_score"),
                        "pii": labels.get("pii", {}).get("has_pii"),
                        "auto_publish": False,
                    },
                    ensure_ascii=False,
                ),
                _utc(),
            ),
        )

    def _validate_parent(
        self, *, parent_comment_id: str, site_space: str, title_id: str
    ) -> dict[str, Any] | None:
        if not parent_comment_id:
            return None
        parent = self._row(parent_comment_id)
        if not parent:
            raise CommentsValidationError("parent comment not found")
        if parent["site_space"] != site_space or parent["title_id"] != title_id:
            raise CommentsValidationError("parent must share site_space and title_id")
        if parent.get("parent_comment_id"):
            raise CommentsValidationError("one-level replies only")
        if parent["status"] in (
            comment_flags.STATUS_DELETED_BY_USER,
            comment_flags.STATUS_REMOVED_BY_MODERATOR,
            comment_flags.STATUS_REJECTED,
        ):
            raise CommentsValidationError("cannot reply to removed parent")
        return parent

    def create(
        self,
        *,
        site_space: str,
        title_id: str,
        identity_id: str,
        body: str,
        parent_comment_id: str = "",
        spoiler: bool = False,
        bypass_write_flag_for_tests: bool = False,
    ) -> dict[str, Any]:
        if not bypass_write_flag_for_tests:
            self._require_write()
        else:
            comment_flags.assert_comments_dark()
        if not site_space or not title_id or not identity_id:
            raise CommentsValidationError("site_space, title_id, identity_id required")
        cleaned = sanitize_body(body)
        labels = label_comment(cleaned["body"], body_normalized=cleaned["body_normalized"])
        with self._lock:
            self._check_rate(
                identity_id=identity_id, site_space=site_space, title_id=title_id, action="create"
            )
            self._validate_parent(
                parent_comment_id=parent_comment_id or "", site_space=site_space, title_id=title_id
            )
            # Duplicate detection (same identity + normalized body in window)
            dup = self.store.conn.execute(
                """SELECT comment_id FROM community_comments
                   WHERE identity_id=? AND site_space=? AND title_id=?
                     AND body_normalized=? AND deleted_at=''
                   ORDER BY created_at DESC LIMIT 1""",
                (identity_id, site_space, title_id, cleaned["body_normalized"]),
            ).fetchone()
            if dup:
                raise CommentsConflict("duplicate comment")

            now = _utc()
            comment_id = _new_id("cmt")
            status = comment_flags.STATUS_PENDING
            risk_state = "CLEAR"
            if labels["pii"]["has_pii"] or labels["toxicity_score"] >= 0.8 or labels["spam_score"] >= 0.8:
                status = comment_flags.STATUS_QUARANTINED
                risk_state = "QUARANTINED"
            suggested_spoiler = bool(spoiler or labels.get("spoiler_suggested"))
            # Never auto-publish even if labels look clean.
            assert labels.get("auto_publish") is False
            self.store.conn.execute(
                """INSERT INTO community_comments (
                    comment_id, site_space, title_id, identity_id, parent_comment_id,
                    body, body_normalized, spoiler, status, created_at, edited_at,
                    deleted_at, published_at, moderation_reason, risk_state, version,
                    discussion_space_id, subject_id, actor_id, updated_at
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    comment_id,
                    site_space,
                    title_id,
                    identity_id,
                    parent_comment_id or "",
                    cleaned["body"],
                    cleaned["body_normalized"],
                    1 if suggested_spoiler else 0,
                    status,
                    now,
                    "",
                    "",
                    "",  # published_at stays empty while publication flag is off
                    "",
                    risk_state,
                    1,
                    site_space,
                    title_id,
                    identity_id,
                    now,
                ),
            )
            self._record_revision(
                comment_id=comment_id,
                version=1,
                body=cleaned["body"],
                body_normalized=cleaned["body_normalized"],
                editor_identity_id=identity_id,
                edit_reason="create",
            )
            self._record_risk(comment_id=comment_id, identity_id=identity_id, labels=labels)
            row = self._row(comment_id)
            assert row is not None
            return {"comment": row, "labels": labels, "status": 201}

    def edit(
        self,
        *,
        comment_id: str,
        identity_id: str,
        body: str,
        bypass_write_flag_for_tests: bool = False,
    ) -> dict[str, Any]:
        if not bypass_write_flag_for_tests:
            self._require_write()
        cleaned = sanitize_body(body)
        labels = label_comment(cleaned["body"], body_normalized=cleaned["body_normalized"])
        with self._lock:
            row = self._row(comment_id)
            if not row:
                raise CommentsNotFound("comment not found")
            if row["identity_id"] != identity_id:
                raise CommentsForbidden("only author may edit")
            if row["status"] in (
                comment_flags.STATUS_REMOVED_BY_MODERATOR,
                comment_flags.STATUS_REJECTED,
            ):
                raise CommentsForbidden("cannot edit moderated comment")
            if row["deleted_at"]:
                raise CommentsForbidden("cannot edit deleted comment")
            new_version = int(row["version"]) + 1
            now = _utc()
            # Immutable history: prior body already in revisions; update head only.
            self.store.conn.execute(
                """UPDATE community_comments
                   SET body=?, body_normalized=?, edited_at=?, updated_at=?, version=?,
                       spoiler=CASE WHEN ? THEN 1 ELSE spoiler END,
                       risk_state=CASE WHEN ? THEN 'QUARANTINED' ELSE risk_state END,
                       status=CASE WHEN ? AND status='PUBLISHED' THEN 'PENDING' ELSE status END
                   WHERE comment_id=?""",
                (
                    cleaned["body"],
                    cleaned["body_normalized"],
                    now,
                    now,
                    new_version,
                    1 if labels.get("spoiler_suggested") else 0,
                    1
                    if (labels["pii"]["has_pii"] or labels["toxicity_score"] >= 0.8)
                    else 0,
                    1
                    if (labels["pii"]["has_pii"] or labels["toxicity_score"] >= 0.8)
                    else 0,
                    comment_id,
                ),
            )
            self._record_revision(
                comment_id=comment_id,
                version=new_version,
                body=cleaned["body"],
                body_normalized=cleaned["body_normalized"],
                editor_identity_id=identity_id,
                edit_reason="edit",
            )
            self._record_risk(comment_id=comment_id, identity_id=identity_id, labels=labels)
            return {"comment": self._row(comment_id), "labels": labels, "status": 200}

    def delete_by_user(
        self,
        *,
        comment_id: str,
        identity_id: str,
        bypass_write_flag_for_tests: bool = False,
    ) -> dict[str, Any]:
        if not bypass_write_flag_for_tests:
            self._require_write()
        with self._lock:
            row = self._row(comment_id)
            if not row:
                raise CommentsNotFound("comment not found")
            if row["identity_id"] != identity_id:
                raise CommentsForbidden("only author may delete")
            if row["status"] == comment_flags.STATUS_DELETED_BY_USER:
                return {"comment": row, "status": 200}
            now = _utc()
            prior = row["status"]
            self.store.conn.execute(
                """UPDATE community_comments
                   SET status=?, deleted_at=?, updated_at=?
                   WHERE comment_id=?""",
                (comment_flags.STATUS_DELETED_BY_USER, now, now, comment_id),
            )
            self._record_moderation(
                comment_id=comment_id,
                action="delete_by_user",
                actor_identity_id=identity_id,
                reason_code="USER_DELETE",
                prior_status=prior,
                new_status=comment_flags.STATUS_DELETED_BY_USER,
                actor_role="author",
            )
            return {"comment": self._row(comment_id), "status": 200}

    def list_for_title(
        self,
        *,
        site_space: str,
        title_id: str,
        viewer_identity_id: str = "",
        admin_preview: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        comment_flags.assert_comments_dark()
        limit = max(1, min(int(limit), 100))
        offset = max(0, int(offset))
        public_on = comment_flags.public_read_enabled()
        admin_on = comment_flags.admin_preview_enabled() and admin_preview

        if not public_on and not admin_on:
            return {
                "comments": [],
                "status": 200,
                "dark": True,
                "reason": "COMMENTS_PUBLIC_READ_ENABLED=0",
            }

        rows = self.store.conn.execute(
            """SELECT * FROM community_comments
               WHERE site_space=? AND title_id=?
               ORDER BY created_at ASC
               LIMIT ? OFFSET ?""",
            (site_space, title_id, limit, offset),
        ).fetchall()
        out: list[dict[str, Any]] = []
        for raw in rows:
            row = dict(raw)
            status = row["status"]
            is_author = viewer_identity_id and row["identity_id"] == viewer_identity_id
            if admin_on:
                out.append(self._public_view(row, include_body=True))
                continue
            if status == comment_flags.STATUS_PUBLISHED and public_on:
                out.append(self._public_view(row, include_body=True))
            elif is_author and status in comment_flags.AUTHOR_VISIBLE_EXTRA:
                out.append(self._public_view(row, include_body=True))
            # others hidden
        return {"comments": out, "status": 200, "dark": not public_on, "count": len(out)}

    def _public_view(self, row: dict[str, Any], *, include_body: bool) -> dict[str, Any]:
        return {
            "comment_id": row["comment_id"],
            "site_space": row["site_space"],
            "title_id": row["title_id"],
            "parent_comment_id": row["parent_comment_id"],
            "body": row["body"] if include_body else "",
            "spoiler": bool(row["spoiler"]),
            "status": row["status"],
            "created_at": row["created_at"],
            "edited_at": row["edited_at"],
            "version": row["version"],
            "identity_redacted": (row["identity_id"][:4] + "…" + row["identity_id"][-2:])
            if row.get("identity_id")
            else "",
        }

    def report(
        self,
        *,
        comment_id: str,
        identity_id: str,
        reason_code: str,
        detail: str = "",
        bypass_write_flag_for_tests: bool = False,
    ) -> dict[str, Any]:
        if not bypass_write_flag_for_tests:
            self._require_write()
        if not reason_code:
            raise CommentsValidationError("reason_code required")
        with self._lock:
            row = self._row(comment_id)
            if not row:
                raise CommentsNotFound("comment not found")
            report_id = _new_id("crpt")
            now = _utc()
            self.store.conn.execute(
                """INSERT INTO community_content_reports
                   (report_id, target_type, target_id, comment_id, identity_id, actor_id,
                    reason_code, detail, status, created_at, resolved_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    report_id,
                    "comment",
                    comment_id,
                    comment_id,
                    identity_id,
                    identity_id,
                    reason_code[:64],
                    (detail or "")[:500],
                    "OPEN",
                    now,
                    "",
                ),
            )
            return {"report_id": report_id, "status": 201}

    def revisions(self, comment_id: str) -> list[dict[str, Any]]:
        rows = self.store.conn.execute(
            """SELECT revision_id, comment_id, version, body, created_at, edit_reason
               FROM community_comment_revisions
               WHERE comment_id=? ORDER BY version ASC""",
            (comment_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def vote_aggregate_unchanged_probe(
        self, *, rating_space_id: str, subject_id: str
    ) -> dict[str, Any]:
        """Prove comments paths do not mutate rating aggregates."""
        before = self.store.get_aggregate(rating_space_id=rating_space_id, subject_id=subject_id)
        return {
            "vote_sum": before["vote_sum"],
            "vote_count": before["vote_count"],
            "aggregate_version": before["aggregate_version"],
        }
