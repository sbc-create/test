"""Comments admin queue — moderate only; never fake/impersonate/silent-rewrite."""

from __future__ import annotations

from typing import Any

from factory.community.comments import flags as comment_flags
from factory.community.comments.service import (
    CommentsNotFound,
    CommentsService,
    CommentsValidationError,
    _utc,
)

ALLOWED_ACTIONS = frozenset(
    {
        "approve",
        "quarantine",
        "reject",
        "remove",
        "restore",
        "mark_spoiler",
        "dismiss_report",
    }
)

# Permanently forbidden — even if someone flips a constant.
FORBIDDEN_ACTIONS = frozenset(
    {
        "ADMIN_FAKE_COMMENT_INSERT",
        "ADMIN_IMPERSONATE_USER",
        "ADMIN_SILENT_TEXT_REWRITE",
    }
)


def require_moderation_scope(scopes: set[str] | list[str] | tuple[str, ...]) -> None:
    if "moderation" not in set(scopes) and "write" not in set(scopes):
        raise PermissionError("RBAC: moderation scope required")


class CommentsAdmin:
    def __init__(self, service: CommentsService) -> None:
        self.service = service

    def queue(
        self,
        *,
        scopes: set[str] | list[str] | tuple[str, ...],
        status: str = "PENDING",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        require_moderation_scope(scopes)
        if not comment_flags.admin_preview_enabled():
            return []
        rows = self.service.store.conn.execute(
            """SELECT comment_id, site_space, title_id, status, risk_state, spoiler,
                      created_at, body, identity_id, moderation_reason, version
               FROM community_comments
               WHERE status=?
               ORDER BY created_at ASC LIMIT ?""",
            (status, max(1, min(limit, 200))),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            iid = d.pop("identity_id", "")
            d["identity_redacted"] = (iid[:4] + "…" + iid[-2:]) if iid else ""
            out.append(d)
        return out

    def apply(
        self,
        *,
        scopes: set[str] | list[str] | tuple[str, ...],
        comment_id: str,
        action: str,
        moderator_identity_id: str,
        reason_code: str = "",
        report_id: str = "",
    ) -> dict[str, Any]:
        require_moderation_scope(scopes)
        action = (action or "").strip().lower()
        if action.upper() in FORBIDDEN_ACTIONS or action in {
            "fake_insert",
            "impersonate",
            "silent_rewrite",
        }:
            cap = {
                "fake_insert": "ADMIN_FAKE_COMMENT_INSERT",
                "impersonate": "ADMIN_IMPERSONATE_USER",
                "silent_rewrite": "ADMIN_SILENT_TEXT_REWRITE",
            }.get(action, "ADMIN_FAKE_COMMENT_INSERT")
            comment_flags.forbid_admin_capability(cap)
        if action not in ALLOWED_ACTIONS:
            raise CommentsValidationError(f"unsupported action: {action}")

        return self._apply_action(
            comment_id=comment_id,
            action=action,
            moderator_identity_id=moderator_identity_id,
            reason_code=reason_code,
            report_id=report_id,
        )

    def _apply_action(
        self,
        *,
        comment_id: str,
        action: str,
        moderator_identity_id: str,
        reason_code: str,
        report_id: str,
    ) -> dict[str, Any]:
        store = self.service.store
        with self.service._lock:
            row = self.service._row(comment_id)
            if not row:
                raise CommentsNotFound("comment not found")
            prior = row["status"]
            now = _utc()
            new_status = prior
            if action == "approve":
                # Approve queues to PUBLISHED only when publication flag is on;
                # otherwise stays PENDING with moderation note (dark stage).
                if comment_flags.comments_dark_flags()["COMMENTS_PUBLICATION_ENABLED"]:
                    new_status = comment_flags.STATUS_PUBLISHED
                    store.conn.execute(
                        """UPDATE community_comments
                           SET status=?, published_at=?, updated_at=?, moderation_reason=?,
                               risk_state='CLEAR'
                           WHERE comment_id=?""",
                        (new_status, now, now, reason_code, comment_id),
                    )
                else:
                    new_status = comment_flags.STATUS_PENDING
                    store.conn.execute(
                        """UPDATE community_comments
                           SET status=?, updated_at=?, moderation_reason=?, risk_state='CLEAR'
                           WHERE comment_id=?""",
                        (
                            new_status,
                            now,
                            reason_code or "APPROVED_DARK_NO_PUBLICATION",
                            comment_id,
                        ),
                    )
            elif action == "quarantine":
                new_status = comment_flags.STATUS_QUARANTINED
                store.conn.execute(
                    """UPDATE community_comments
                       SET status=?, updated_at=?, moderation_reason=?, risk_state='QUARANTINED'
                       WHERE comment_id=?""",
                    (new_status, now, reason_code or "QUARANTINE", comment_id),
                )
            elif action == "reject":
                new_status = comment_flags.STATUS_REJECTED
                store.conn.execute(
                    """UPDATE community_comments
                       SET status=?, updated_at=?, moderation_reason=?, risk_state='REJECTED'
                       WHERE comment_id=?""",
                    (new_status, now, reason_code or "REJECT", comment_id),
                )
            elif action == "remove":
                new_status = comment_flags.STATUS_REMOVED_BY_MODERATOR
                store.conn.execute(
                    """UPDATE community_comments
                       SET status=?, deleted_at=?, updated_at=?, moderation_reason=?
                       WHERE comment_id=?""",
                    (new_status, now, now, reason_code or "REMOVE", comment_id),
                )
            elif action == "restore":
                new_status = comment_flags.STATUS_PENDING
                store.conn.execute(
                    """UPDATE community_comments
                       SET status=?, deleted_at='', published_at='', updated_at=?,
                           moderation_reason=?, risk_state='CLEAR'
                       WHERE comment_id=?""",
                    (new_status, now, reason_code or "RESTORE", comment_id),
                )
            elif action == "mark_spoiler":
                store.conn.execute(
                    """UPDATE community_comments SET spoiler=1, updated_at=? WHERE comment_id=?""",
                    (now, comment_id),
                )
                new_status = prior
            elif action == "dismiss_report":
                if not report_id:
                    raise CommentsValidationError("report_id required for dismiss_report")
                store.conn.execute(
                    """UPDATE community_content_reports
                       SET status='DISMISSED', resolved_at=? WHERE report_id=?""",
                    (now, report_id),
                )
                new_status = prior
            else:
                raise CommentsValidationError(f"unsupported action: {action}")

            self.service._record_moderation(
                comment_id=comment_id,
                action=action,
                actor_identity_id=moderator_identity_id,
                reason_code=reason_code or action.upper(),
                prior_status=prior,
                new_status=new_status,
                actor_role="moderator",
            )
            return {"comment": self.service._row(comment_id), "action": action, "status": 200}


def assert_forbidden_capabilities() -> None:
    """Runtime guard used by tests and admin boot."""
    for name in (
        "ADMIN_FAKE_COMMENT_INSERT",
        "ADMIN_IMPERSONATE_USER",
        "ADMIN_SILENT_TEXT_REWRITE",
    ):
        assert getattr(comment_flags, name) == 0
