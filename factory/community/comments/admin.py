"""Comments admin queue — V2 postmod overrides with RBAC + audit.

Never fake/impersonate/silent-rewrite. Soft-delete only; physical body
deletion is not an admin path on this stage.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from factory.community.comments import flags as comment_flags
from factory.community.comments import states
from factory.community.comments.service import (
    CommentsNotFound,
    CommentsService,
    CommentsValidationError,
    _utc,
)

# Canonical Stage02 actions (goal §17)
V2_ACTIONS = frozenset(
    {
        "approve",
        "hide",
        "unhide",
        "delete",
        "restore",
        "mark_spoiler",
        "clear_spoiler",
        "mark_spam",
        "ban_device",
        "unban_device",
        "add_note",
        "confirm_qwen",
        "override_qwen",
        "dismiss_report",
    }
)

# Stage01 aliases kept for dual-read / existing tests
STAGE01_ACTION_ALIASES = {
    "quarantine": "hide",
    "reject": "hide",
    "remove": "delete",
}

ALLOWED_ACTIONS = V2_ACTIONS | frozenset(STAGE01_ACTION_ALIASES)

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
        status: str = states.HELD_FOR_REVIEW,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        require_moderation_scope(scopes)
        if not comment_flags.admin_preview_enabled():
            return []
        # Accept Stage01 alias or V2; also surface unreviewed / degraded.
        wanted = {status, states.normalize_status(status) if status else status}
        if status in ("PENDING", states.HELD_FOR_REVIEW):
            wanted |= {
                states.HELD_FOR_REVIEW,
                states.PUBLISHED_UNREVIEWED,
                states.PENDING_MODERATION_DEGRADED,
                states.HIDDEN_QWEN_HIGH_CONFIDENCE,
                "PENDING",
                "QUARANTINED",
            }
        placeholders = ",".join("?" * len(wanted))
        rows = self.service.store.conn.execute(
            f"""SELECT c.comment_id, c.site_space, c.title_id, c.status,
                      c.moderation_status, c.risk_state, c.spoiler, c.spoiler_collapsed,
                      c.created_at, c.body, c.identity_id, c.moderation_reason,
                      c.version, c.qwen_decision_json, c.last_moderation_at,
                      (SELECT COUNT(*) FROM community_content_reports r
                         WHERE r.comment_id=c.comment_id AND r.status='OPEN') AS report_count
               FROM community_comments c
               WHERE c.status IN ({placeholders})
                  OR c.moderation_status IN ({placeholders})
               ORDER BY c.created_at ASC LIMIT ?""",
            (*wanted, *wanted, max(1, min(limit, 200))),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            iid = d.pop("identity_id", "")
            d["identity_redacted"] = (iid[:4] + "…" + iid[-2:]) if iid else ""
            decision = {}
            raw = d.get("qwen_decision_json") or ""
            if raw:
                try:
                    decision = json.loads(raw)
                except json.JSONDecodeError:
                    decision = {}
            d["qwen_action"] = decision.get("action", "")
            d["qwen_labels"] = decision.get("labels", [])
            d["qwen_confidence"] = decision.get("confidence")
            d["qwen_reason_codes"] = decision.get("reason_codes", [])
            d["qwen_decision"] = decision  # admin-only; never public API
            d["override_history"] = self._override_history(d["comment_id"])
            # Never leak raw identity_id
            out.append(d)
        return out

    def _override_history(self, comment_id: str) -> list[dict[str, Any]]:
        rows = self.service.store.conn.execute(
            """SELECT event_id, action, actor_role, reason_code, prior_status, new_status,
                      policy_version, model, prompt_digest, created_at
               FROM community_comment_moderation_events
               WHERE comment_id=?
               ORDER BY created_at ASC""",
            (comment_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def apply(
        self,
        *,
        scopes: set[str] | list[str] | tuple[str, ...],
        comment_id: str,
        action: str,
        moderator_identity_id: str,
        reason_code: str = "",
        report_id: str = "",
        note: str = "",
        target_identity_id: str = "",
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
        canonical = STAGE01_ACTION_ALIASES.get(action, action)

        return self._apply_action(
            comment_id=comment_id,
            action=canonical,
            requested_action=action,
            moderator_identity_id=moderator_identity_id,
            reason_code=reason_code,
            report_id=report_id,
            note=note,
            target_identity_id=target_identity_id,
        )

    def _apply_action(
        self,
        *,
        comment_id: str,
        action: str,
        requested_action: str,
        moderator_identity_id: str,
        reason_code: str,
        report_id: str,
        note: str,
        target_identity_id: str,
    ) -> dict[str, Any]:
        store = self.service.store
        with self.service._lock:
            row = self.service._row(comment_id)
            if not row and action not in {"ban_device", "unban_device"}:
                raise CommentsNotFound("comment not found")
            prior = row["status"] if row else ""
            now = _utc()
            new_status = prior

            if action == "approve" or action == "confirm_qwen":
                # Admin confirmation → visible approved; publication flag still gates public.
                new_status = states.VISIBLE_QWEN_APPROVED
                if not comment_flags.comments_dark_flags()["COMMENTS_PUBLICATION_ENABLED"]:
                    # Dark stage: keep visible-approved ledger status for canary/admin preview.
                    pass
                store.conn.execute(
                    """UPDATE community_comments
                       SET status=?, moderation_status=?, published_at=COALESCE(NULLIF(published_at,''), ?),
                           updated_at=?, moderation_reason=?, risk_state='CLEAR',
                           spoiler_collapsed=0, last_moderation_at=?
                       WHERE comment_id=?""",
                    (
                        new_status,
                        new_status,
                        now,
                        now,
                        reason_code or "ADMIN_APPROVE",
                        now,
                        comment_id,
                    ),
                )
            elif action == "hide" or action == "mark_spam":
                new_status = states.HIDDEN_BY_ADMIN
                risk = "SPAM" if action == "mark_spam" else "HIDDEN"
                store.conn.execute(
                    """UPDATE community_comments
                       SET status=?, moderation_status=?, updated_at=?, moderation_reason=?,
                           risk_state=?, last_moderation_at=?
                       WHERE comment_id=?""",
                    (
                        new_status,
                        new_status,
                        now,
                        reason_code or action.upper(),
                        risk,
                        now,
                        comment_id,
                    ),
                )
            elif action == "unhide" or action == "override_qwen":
                new_status = states.VISIBLE_QWEN_APPROVED
                store.conn.execute(
                    """UPDATE community_comments
                       SET status=?, moderation_status=?, updated_at=?, moderation_reason=?,
                           risk_state='CLEAR', last_moderation_at=?
                       WHERE comment_id=?""",
                    (
                        new_status,
                        new_status,
                        now,
                        reason_code or "ADMIN_UNHIDE",
                        now,
                        comment_id,
                    ),
                )
            elif action == "delete":
                new_status = states.DELETED_BY_ADMIN
                store.conn.execute(
                    """UPDATE community_comments
                       SET status=?, moderation_status=?, deleted_at=?, updated_at=?,
                           moderation_reason=?, last_moderation_at=?
                       WHERE comment_id=?""",
                    (
                        new_status,
                        new_status,
                        now,
                        now,
                        reason_code or "ADMIN_DELETE",
                        now,
                        comment_id,
                    ),
                )
            elif action == "restore":
                # Soft-restore into held-for-review (requires re-check) unless already visible path.
                new_status = states.HELD_FOR_REVIEW
                store.conn.execute(
                    """UPDATE community_comments
                       SET status=?, moderation_status=?, deleted_at='', updated_at=?,
                           moderation_reason=?, risk_state='CLEAR', last_moderation_at=?
                       WHERE comment_id=?""",
                    (
                        new_status,
                        new_status,
                        now,
                        reason_code or "ADMIN_RESTORE",
                        now,
                        comment_id,
                    ),
                )
            elif action == "mark_spoiler":
                store.conn.execute(
                    """UPDATE community_comments
                       SET spoiler=1, spoiler_collapsed=1, status=?, moderation_status=?,
                           updated_at=?, last_moderation_at=?
                       WHERE comment_id=?""",
                    (
                        states.VISIBLE_SPOILER_COLLAPSED
                        if states.is_public_visible(prior)
                        or prior
                        in (
                            states.PUBLISHED_UNREVIEWED,
                            states.VISIBLE_QWEN_APPROVED,
                            "PUBLISHED",
                        )
                        else prior,
                        states.VISIBLE_SPOILER_COLLAPSED
                        if states.is_public_visible(prior)
                        or prior
                        in (
                            states.PUBLISHED_UNREVIEWED,
                            states.VISIBLE_QWEN_APPROVED,
                            "PUBLISHED",
                        )
                        else prior,
                        now,
                        now,
                        comment_id,
                    ),
                )
                row2 = self.service._row(comment_id)
                new_status = row2["status"] if row2 else prior
            elif action == "clear_spoiler":
                store.conn.execute(
                    """UPDATE community_comments
                       SET spoiler=0, spoiler_collapsed=0, updated_at=?, last_moderation_at=?
                       WHERE comment_id=?""",
                    (now, now, comment_id),
                )
                if prior == states.VISIBLE_SPOILER_COLLAPSED:
                    new_status = states.VISIBLE_QWEN_APPROVED
                    store.conn.execute(
                        """UPDATE community_comments
                           SET status=?, moderation_status=? WHERE comment_id=?""",
                        (new_status, new_status, comment_id),
                    )
                else:
                    new_status = prior
            elif action == "add_note":
                if not note.strip():
                    raise CommentsValidationError("note required for add_note")
                self.service._record_moderation(
                    comment_id=comment_id,
                    action="INTERNAL_NOTE",
                    actor_identity_id=moderator_identity_id,
                    reason_code=reason_code or "NOTE",
                    prior_status=prior,
                    new_status=prior,
                    actor_role="moderator",
                    decision_json={"note": note.strip()[:2000]},
                )
                return {"comment": self.service._row(comment_id), "action": action, "status": 200}
            elif action == "ban_device":
                target = target_identity_id or (row["identity_id"] if row else "")
                if not target:
                    raise CommentsValidationError("target_identity_id required for ban_device")
                store.conn.execute(
                    """INSERT INTO community_sanctions
                       (sanction_id, actor_id, kind, created_at, expires_at)
                       VALUES (?, ?, 'DEVICE_BAN', ?, '')""",
                    (str(uuid.uuid4()), target, now),
                )
                self.service._record_moderation(
                    comment_id=comment_id or "n/a",
                    action="BAN_DEVICE",
                    actor_identity_id=moderator_identity_id,
                    reason_code=reason_code or "DEVICE_BAN",
                    prior_status=prior or "",
                    new_status=prior or "",
                    actor_role="moderator",
                    decision_json={"target_redacted": target[:4] + "…" + target[-2:]},
                )
                return {
                    "comment": self.service._row(comment_id) if comment_id else None,
                    "action": action,
                    "status": 200,
                }
            elif action == "unban_device":
                target = target_identity_id or (row["identity_id"] if row else "")
                if not target:
                    raise CommentsValidationError("target_identity_id required for unban_device")
                store.conn.execute(
                    """UPDATE community_sanctions
                       SET expires_at=?
                       WHERE actor_id=? AND kind='DEVICE_BAN'
                         AND (expires_at='' OR expires_at > ?)""",
                    (now, target, now),
                )
                self.service._record_moderation(
                    comment_id=comment_id or "n/a",
                    action="UNBAN_DEVICE",
                    actor_identity_id=moderator_identity_id,
                    reason_code=reason_code or "DEVICE_UNBAN",
                    prior_status=prior or "",
                    new_status=prior or "",
                    actor_role="moderator",
                    decision_json={"target_redacted": target[:4] + "…" + target[-2:]},
                )
                return {
                    "comment": self.service._row(comment_id) if comment_id else None,
                    "action": action,
                    "status": 200,
                }
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
                action=requested_action,
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
