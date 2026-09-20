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
from factory.community.comments import outbox, states
from factory.community.comments.degraded import DegradedController
from factory.community.comments.guest_display import public_author_dto
from factory.community.comments.kill_switch import load_capabilities
from factory.community.comments.labels import label_comment
from factory.community.comments.metrics_postmod import metrics as postmod_metrics
from factory.community.comments.preflight import PreflightError, run_preflight
from factory.community.comments.sanitize import sanitize_body
from factory.community.store import CommunityStore

MAX_REPLY_DEPTH = 1  # root=0, reply=1; no nested replies
# Goal §7 defaults for anonymous devices
RATE_LIMIT_WINDOW_SEC = 600  # 10 minutes
RATE_LIMIT_MAX = 3
RATE_LIMIT_DAY_SEC = 86400
RATE_LIMIT_DAY_MAX = 20
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
        now_iso = _utc()
        cutoff_10m = datetime.fromtimestamp(
            time.time() - RATE_LIMIT_WINDOW_SEC, timezone.utc
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        cutoff_day = datetime.fromtimestamp(
            time.time() - RATE_LIMIT_DAY_SEC, timezone.utc
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        rows = self.store.conn.execute(
            """SELECT created_at FROM community_comment_rate_limit_events
               WHERE identity_id=? AND created_at>=? ORDER BY created_at DESC""",
            (identity_id, cutoff_day),
        ).fetchall()
        recent_10m = sum(1 for r in rows if str(r["created_at"]) >= cutoff_10m)
        if recent_10m >= RATE_LIMIT_MAX or len(rows) >= RATE_LIMIT_DAY_MAX:
            postmod_metrics().rate_limit_blocks += 1
            raise CommentsRateLimited("comment rate limit exceeded")
        self.store.conn.execute(
            """INSERT INTO community_comment_rate_limit_events
               (event_id, identity_id, site_space, title_id, action, created_at)
               VALUES (?,?,?,?,?,?)""",
            (_new_id("crl"), identity_id, site_space, title_id, action, now_iso),
        )

    def _queue_stats(self) -> tuple[int, float]:
        row = self.store.conn.execute(
            """SELECT COUNT(*) AS n,
                      MIN(created_at) AS oldest
               FROM community_comment_moderation_jobs
               WHERE status IN ('PENDING','LEASED')"""
        ).fetchone()
        depth = int(row["n"] or 0) if row else 0
        oldest_age = 0.0
        if row and row["oldest"]:
            try:
                oldest = datetime.strptime(str(row["oldest"]), "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=timezone.utc
                )
                oldest_age = max(0.0, (datetime.now(timezone.utc) - oldest).total_seconds())
            except ValueError:
                oldest_age = 0.0
        return depth, oldest_age

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
        decision_json: dict[str, Any] | None = None,
        policy_version: str = "",
        model: str = "",
        prompt_digest: str = "",
    ) -> None:
        import json

        self.store.conn.execute(
            """INSERT INTO community_comment_moderation_events
               (event_id, comment_id, action, actor_role, actor_identity_id,
                reason_code, detail, prior_status, new_status, created_at,
                policy_version, model, prompt_digest, decision_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
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
                policy_version,
                model,
                prompt_digest,
                json.dumps(decision_json or {}, ensure_ascii=False),
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
        try:
            parent_status = states.normalize_status(parent["status"])
        except Exception:
            parent_status = parent["status"]
        if parent_status in (
            states.DELETED_BY_AUTHOR,
            states.DELETED_BY_ADMIN,
            states.PREFLIGHT_REJECTED,
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
        content_type: str = "",
        bypass_write_flag_for_tests: bool = False,
        degraded: DegradedController | None = None,
    ) -> dict[str, Any]:
        """Technical preflight → immediate PUBLISHED_UNREVIEWED + Qwen outbox job.

        Production publication/read flags remain OFF; status is ledger-side only
        until a supervised canary enables public read.
        """
        caps = load_capabilities()
        if caps.block_writes and not bypass_write_flag_for_tests:
            raise CommentsWriteDisabled("kill switch block_writes")
        if not bypass_write_flag_for_tests:
            self._require_write()
        else:
            comment_flags.assert_comments_dark()
        if not site_space or not title_id or not identity_id:
            raise CommentsValidationError("site_space, title_id, identity_id required")

        # Opaque device ban (admin sanction) — no PII; identity_id is HMAC opaque.
        banned = self.store.conn.execute(
            """SELECT 1 FROM community_sanctions
               WHERE actor_id=? AND kind='DEVICE_BAN'
                 AND (expires_at='' OR expires_at > ?)
               LIMIT 1""",
            (identity_id, _utc()),
        ).fetchone()
        if banned:
            raise CommentsForbidden("device sanctioned")

        def _dup_check(digest: str) -> bool:
            row = self.store.conn.execute(
                """SELECT COUNT(*) AS n FROM community_comments
                   WHERE body_digest=? AND deleted_at='' AND status NOT IN (?,?)""",
                (digest, states.DELETED_BY_AUTHOR, states.DELETED_BY_ADMIN),
            ).fetchone()
            return int(row["n"] or 0) >= 2

        try:
            cleaned = run_preflight(body, duplicate_check=_dup_check)
        except PreflightError as exc:
            postmod_metrics().preflight_rejected += 1
            if "XSS" in exc.reject_code or "SANITIZE" in exc.reject_code:
                postmod_metrics().xss_blocks += 1
            raise CommentsValidationError(f"preflight:{exc.reject_code}") from exc

        labels = label_comment(cleaned["body"], body_normalized=cleaned["body_normalized"])
        with self._lock:
            self._check_rate(
                identity_id=identity_id, site_space=site_space, title_id=title_id, action="create"
            )
            self._validate_parent(
                parent_comment_id=parent_comment_id or "", site_space=site_space, title_id=title_id
            )
            dup = self.store.conn.execute(
                """SELECT comment_id FROM community_comments
                   WHERE identity_id=? AND site_space=? AND title_id=?
                     AND body_normalized=? AND deleted_at=''
                   ORDER BY created_at DESC LIMIT 1""",
                (identity_id, site_space, title_id, cleaned["body_normalized"]),
            ).fetchone()
            if dup:
                raise CommentsConflict("duplicate comment")

            ctl = degraded or DegradedController()
            depth, oldest = self._queue_stats()
            if caps.force_pending_hidden or caps.hide_new_public:
                status = states.PENDING_MODERATION_DEGRADED
            else:
                status = ctl.initial_status_for_new_comment(queue_depth=depth, oldest_age=oldest)

            now = _utc()
            comment_id = _new_id("cmt")
            suggested_spoiler = bool(spoiler or labels.get("spoiler_suggested"))
            assert labels.get("auto_publish") is False
            published_at = now if status == states.PUBLISHED_UNREVIEWED else ""
            self.store.conn.execute(
                """INSERT INTO community_comments (
                    comment_id, site_space, title_id, identity_id, parent_comment_id,
                    body, body_normalized, spoiler, status, created_at, edited_at,
                    deleted_at, published_at, moderation_reason, risk_state, version,
                    discussion_space_id, subject_id, actor_id, updated_at,
                    moderation_status, body_digest, spoiler_collapsed, content_type
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
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
                    published_at,
                    "",
                    "CLEAR",
                    1,
                    site_space,
                    title_id,
                    identity_id,
                    now,
                    status,
                    cleaned["digest"],
                    0,
                    content_type or "",
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
            job = outbox.enqueue_job(self.store, comment_id=comment_id, revision=1)
            postmod_metrics().comments_created += 1
            if status == states.PUBLISHED_UNREVIEWED:
                postmod_metrics().published_unreviewed += 1
            row = self._row(comment_id)
            assert row is not None
            return {
                "comment": row,
                "labels": labels,
                "job": job,
                "author": public_author_dto(
                    identity_id=identity_id, site_space=site_space, title_id=title_id
                ),
                "status": 201,
            }

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
        with self._lock:
            row = self._row(comment_id)
            if not row:
                raise CommentsNotFound("comment not found")
            if row["identity_id"] != identity_id:
                raise CommentsForbidden("only author may edit")
            if row["status"] in (
                comment_flags.STATUS_REMOVED_BY_MODERATOR,
                comment_flags.STATUS_REJECTED,
                states.DELETED_BY_ADMIN,
                states.HIDDEN_BY_ADMIN,
            ):
                raise CommentsForbidden("cannot edit moderated comment")
            if row["deleted_at"]:
                raise CommentsForbidden("cannot edit deleted comment")
            try:
                cleaned = run_preflight(body)
            except PreflightError as exc:
                raise CommentsValidationError(f"preflight:{exc.reject_code}") from exc
            labels = label_comment(cleaned["body"], body_normalized=cleaned["body_normalized"])
            new_version = int(row["version"]) + 1
            now = _utc()
            self.store.conn.execute(
                """UPDATE community_comments
                   SET body=?, body_normalized=?, body_digest=?, edited_at=?, updated_at=?, version=?,
                       spoiler=CASE WHEN ? THEN 1 ELSE spoiler END,
                       status=?, moderation_status=?, published_at=?,
                       qwen_decision_json='', last_moderation_at=''
                   WHERE comment_id=?""",
                (
                    cleaned["body"],
                    cleaned["body_normalized"],
                    cleaned["digest"],
                    now,
                    now,
                    new_version,
                    1 if labels.get("spoiler_suggested") else 0,
                    states.PUBLISHED_UNREVIEWED,
                    states.PUBLISHED_UNREVIEWED,
                    now,
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
            outbox.enqueue_job(self.store, comment_id=comment_id, revision=new_version)
            postmod_metrics().edits += 1
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
            if row["status"] in (states.DELETED_BY_AUTHOR, comment_flags.STATUS_DELETED_BY_USER):
                return {"comment": row, "status": 200}
            now = _utc()
            prior = row["status"]
            self.store.conn.execute(
                """UPDATE community_comments
                   SET status=?, moderation_status=?, deleted_at=?, updated_at=?
                   WHERE comment_id=?""",
                (states.DELETED_BY_AUTHOR, states.DELETED_BY_AUTHOR, now, now, comment_id),
            )
            outbox.cancel_jobs_for_comment(self.store, comment_id)
            self._record_moderation(
                comment_id=comment_id,
                action="delete_by_user",
                actor_identity_id=identity_id,
                reason_code="USER_DELETE",
                prior_status=prior,
                new_status=states.DELETED_BY_AUTHOR,
                actor_role="author",
            )
            postmod_metrics().deletes += 1
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
        peer_ids = [dict(r)["identity_id"] for r in rows]
        out: list[dict[str, Any]] = []
        for raw in rows:
            row = dict(raw)
            status = row["status"]
            try:
                canon = states.normalize_status(status)
            except Exception:
                canon = status
            is_author = bool(viewer_identity_id and row["identity_id"] == viewer_identity_id)
            if admin_on:
                out.append(
                    self._public_view(
                        row,
                        include_body=True,
                        viewer_identity_id=viewer_identity_id,
                        thread_identity_ids=peer_ids,
                    )
                )
                continue
            if public_on and states.is_public_visible(canon):
                out.append(
                    self._public_view(
                        row,
                        include_body=True,
                        viewer_identity_id=viewer_identity_id,
                        thread_identity_ids=peer_ids,
                    )
                )
            elif is_author and (
                canon in states.AUTHOR_VISIBLE_EXTRA
                or status in comment_flags.AUTHOR_VISIBLE_EXTRA
            ):
                out.append(
                    self._public_view(
                        row,
                        include_body=True,
                        viewer_identity_id=viewer_identity_id,
                        thread_identity_ids=peer_ids,
                    )
                )
            # others hidden
        return {"comments": out, "status": 200, "dark": not public_on, "count": len(out)}

    def _public_view(
        self,
        row: dict[str, Any],
        *,
        include_body: bool,
        viewer_identity_id: str = "",
        thread_identity_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        author = public_author_dto(
            identity_id=row.get("identity_id") or "",
            site_space=row.get("site_space") or "",
            title_id=row.get("title_id") or "",
            thread_identity_ids=thread_identity_ids,
        )
        return {
            "comment_id": row["comment_id"],
            "site_space": row["site_space"],
            "title_id": row["title_id"],
            "parent_comment_id": row["parent_comment_id"],
            "body": row["body"] if include_body else "",
            "spoiler": bool(row["spoiler"]),
            "spoiler_collapsed": bool(row.get("spoiler_collapsed") or 0)
            or (row.get("status") == states.VISIBLE_SPOILER_COLLAPSED),
            "status": row["status"],
            "created_at": row["created_at"],
            "edited_at": row["edited_at"],
            "version": row["version"],
            "author": author,
            "display_name": author["display_name"],
            "is_own": bool(
                viewer_identity_id and row.get("identity_id") == viewer_identity_id
            ),
            # Never expose identity_id / qwen_decision / device fields.
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
