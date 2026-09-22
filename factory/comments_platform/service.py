"""Use cases.

Every operation runs the same gauntlet, in this order, and the order is the
design:

1. **Scope.** Resolved by the server before this layer is entered. Nothing here
   accepts a tenant or site from a caller.
2. **Flags.** Is this capability being served at all? A kill switch answers
   before any work is done.
3. **Authorisation.** Default deny, scope checked before permission.
4. **Idempotency.** A retried write replays its first answer rather than
   producing a second comment.
5. **Anti-abuse.** Bans, rate limits, duplicates — the refusing rules.
6. **Validation and sanitisation.** Length, depth, markup.
7. **Persist**, in one transaction with its audit row and outbox event.

Steps 2 and 3 are not interchangeable. Checking permission first would let an
unauthorised caller learn, from the difference between 403 and 503, whether a
site has comments switched on.

The public read path never receives a non-public comment. That is enforced in
one place — :meth:`_visible_states_for` — rather than by each caller filtering,
because "filter it out at the edge" is how pending comments end up in embedded
JSON while the rendered list looks correct.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from . import audit as audit_log
from . import states
from .antiabuse import RULE_VERSION, AntiAbuse, Policy, exact_digest, near_digest
from .errors import (
    Conflict,
    FeatureDisabled,
    Forbidden,
    NotFound,
    PolicyViolation,
    ValidationFailed,
)
from .flags import EffectiveFlags, FlagResolver
from .identity import Identity
from .rbac import (
    P_AUDIT_READ,
    P_BAN_USER,
    P_CREATE,
    P_DELETE_OWN,
    P_EDIT_OWN,
    P_MODERATION_HIDE,
    P_MODERATION_QUEUE,
    P_MODERATION_REMOVE,
    P_MODERATION_RESOLVE_REPORT,
    P_MODERATION_RESTORE,
    P_POLICY_WRITE,
    P_REACT,
    P_READ_PUBLISHED,
    P_REPORT,
    Principal,
    authorize,
)
from .sanitize import sanitize_body, to_plain_preview
from .store import CommentsStore
from .tenancy import ResourceRef, SiteBinding, SiteRegistry, TenantScope

REACTIONS = ("like", "dislike", "helpful")
REPORT_REASONS = ("spam", "abuse", "spoiler", "offtopic", "illegal", "other")


@dataclass(frozen=True, slots=True)
class ThreadView:
    """What the widget gets for one page of a discussion."""

    thread_id: str
    resource_type: str
    canonical_content_id: str
    total_count: int
    items: tuple[dict[str, Any], ...]
    next_cursor: str
    has_more: bool
    sort: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "thread_id": self.thread_id,
            "resource_type": self.resource_type,
            "canonical_content_id": self.canonical_content_id,
            "total_count": self.total_count,
            "items": list(self.items),
            "next_cursor": self.next_cursor,
            "has_more": self.has_more,
            "sort": self.sort,
        }


class CommentsService:
    def __init__(
        self,
        store: CommentsStore,
        registry: SiteRegistry,
        *,
        flags: FlagResolver | None = None,
        antiabuse: AntiAbuse | None = None,
        now: datetime | None = None,
        artifact_hash: str = "",
    ) -> None:
        self._store = store
        self._registry = registry
        self._flags = flags or FlagResolver()
        self._antiabuse = antiabuse or AntiAbuse(store, now=now)
        self._fixed_now = now
        self._artifact_hash = artifact_hash

    # --- helpers ---------------------------------------------------------

    def _now(self) -> datetime:
        return self._fixed_now or datetime.now(timezone.utc)

    def binding(self, scope: TenantScope) -> SiteBinding:
        return self._registry.get(scope.tenant_id, scope.site_id)

    def effective_flags(self, scope: TenantScope, cohort: str = "public") -> EffectiveFlags:
        """Flags for one audience.

        The default is `public`, deliberately: a call site that forgets to
        thread the cohort through receives the ordinary-visitor answer, which
        in this stage is "nothing". The permissive direction must be named.
        """
        return self._flags.resolve_for_cohort(self.binding(scope), cohort)

    def policy(self, scope: TenantScope) -> Policy:
        return Policy.from_row(self._store.get_policy(scope))

    def _require_reads(self, scope: TenantScope, cohort: str = "public") -> EffectiveFlags:
        flags = self.effective_flags(scope, cohort)
        if not flags.reads_allowed:
            # 503, so a page embedding the widget degrades rather than breaks.
            raise FeatureDisabled("comments reading is not enabled for this site")
        return flags

    def _require_writes(self, scope: TenantScope, cohort: str = "public") -> EffectiveFlags:
        flags = self.effective_flags(scope, cohort)
        if flags.any_kill_switch:
            raise FeatureDisabled("comments are stopped by a kill switch")
        if not flags.writes_allowed:
            raise FeatureDisabled("comments writing is not enabled for this site")
        return flags

    @staticmethod
    def _visible_states_for(viewer_subject_id: str, comment_owner: str = "") -> tuple[str, ...]:
        """The single definition of what a given viewer may see."""
        if viewer_subject_id and comment_owner and viewer_subject_id == comment_owner:
            return tuple(sorted(states.AUTHOR_VISIBLE))
        return tuple(sorted(states.PUBLIC_VISIBLE))

    def _fingerprint(self, operation: str, payload: Mapping[str, Any]) -> str:
        """Stable hash of what the caller asked for.

        Used to tell a genuine retry from a key reused with different content.
        Sorted keys so that a client reordering its JSON does not look like a
        different request.
        """
        material = json.dumps(
            {"op": operation, **dict(sorted(payload.items()))},
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def _public_dto(
        self, row: Mapping[str, Any], *, viewer_subject_id: str = ""
    ) -> dict[str, Any]:
        """What leaves the service for a browser.

        Note what is not here: `tenant_id`, `site_id`, the raw body, the risk
        score, the report count and the network identifier. A client that can
        see another site's name has learned something it had no way to ask for.
        """
        is_own = bool(viewer_subject_id) and row["subject_id"] == viewer_subject_id
        state = row["state"]
        dto = {
            "comment_id": row["comment_id"],
            "parent_id": row["parent_id"] or None,
            "depth": row["depth"],
            "author": {"subject_id": row["subject_id"]},
            "state": state,
            "is_own": is_own,
            "created_at": row["created_at"],
            "edited_at": row["edited_at"] or None,
            "revision": row["revision"],
            "reaction_count": row["reaction_count"],
            "reply_count": row["reply_count"],
            "anchor": f"comment-{row['comment_id']}",
        }
        if states.is_public_visible(state) or is_own:
            dto["body_html"] = row["body_html"]
        else:
            # The author of a hidden comment sees it; nobody else sees its text.
            dto["body_html"] = ""
        return dto

    # --- reading ---------------------------------------------------------

    def thread_view(
        self,
        scope: TenantScope,
        principal: Principal,
        ref: ResourceRef,
        *,
        sort: str = "new",
        limit: int = 20,
        cursor: str = "",
        viewer_subject_id: str = "",
        cohort: str = "public",
    ) -> ThreadView:
        self._require_reads(scope, cohort)
        authorize(principal, P_READ_PUBLISHED, scope)

        thread = self._store.find_thread(scope, ref)
        if thread is None:
            # An empty discussion, not an error. Creating the thread row on a
            # read would let a crawler populate the table by walking the site.
            return ThreadView(
                thread_id="", resource_type=ref.resource_type,
                canonical_content_id=ref.canonical_content_id,
                total_count=0, items=(), next_cursor="", has_more=False, sort=sort,
            )

        page = self._store.list_comments(
            scope,
            thread["thread_id"],
            visible_states=states.PUBLIC_VISIBLE,
            sort=sort,
            limit=limit,
            cursor=cursor,
            include_subject_id=viewer_subject_id,
        )
        return ThreadView(
            thread_id=thread["thread_id"],
            resource_type=thread["resource_type"],
            canonical_content_id=thread["canonical_content_id"],
            total_count=int(thread["comment_count"]),
            items=tuple(
                self._public_dto(row, viewer_subject_id=viewer_subject_id) for row in page.items
            ),
            next_cursor=page.next_cursor,
            has_more=page.has_more,
            sort=sort,
        )

    def comment_count(
        self, scope: TenantScope, principal: Principal, ref: ResourceRef,
        *, cohort: str = "public",
    ) -> int:
        self._require_reads(scope, cohort)
        authorize(principal, P_READ_PUBLISHED, scope)
        thread = self._store.find_thread(scope, ref)
        return int(thread["comment_count"]) if thread else 0

    # --- writing ---------------------------------------------------------

    def create_comment(
        self,
        scope: TenantScope,
        principal: Principal,
        identity: Identity,
        ref: ResourceRef,
        *,
        body: str,
        parent_id: str = "",
        idempotency_key: str = "",
        request_id: str = "",
        antispam_degraded: bool = False,
        cohort: str = "public",
    ) -> dict[str, Any]:
        flags = self._require_writes(scope, cohort)
        authorize(principal, P_CREATE, scope)

        if self._store.is_banned(scope, identity.subject_id):
            # Not a 404: the person knows they are banned, and pretending the
            # site vanished would just make them open a new tab.
            raise Forbidden("this account is banned on this site")

        binding = self.binding(scope)
        policy = self.policy(scope)

        fingerprint = self._fingerprint(
            "create",
            {
                "body": body, "parent_id": parent_id,
                "resource": f"{ref.resource_type}:{ref.canonical_content_id}",
            },
        )
        if idempotency_key:
            replay = self._store.idempotent_replay(
                scope, subject_id=identity.subject_id, key=idempotency_key,
                fingerprint=fingerprint,
            )
            if replay is not None:
                return replay

        thread = self._store.get_or_create_thread(scope, ref)
        thread_id = thread["thread_id"]

        depth = 0
        if parent_id:
            parent = self._store.get_comment(scope, parent_id)
            if parent["thread_id"] != thread_id:
                raise ValidationFailed("parent belongs to another thread", field="parent_id")
            if not states.is_public_visible(parent["state"]):
                # Replying to a hidden comment would leak that it exists.
                raise NotFound("parent not found", parent_id=parent_id)
            depth = int(parent["depth"]) + 1
            if depth >= binding.max_depth:
                raise PolicyViolation(
                    f"replies are limited to {binding.max_depth} levels", rule="MAX_DEPTH"
                )

        self._antiabuse.check_rate_limits(
            scope,
            subject_id=identity.subject_id,
            network_hmac=identity.network_hmac,
            thread_id=thread_id,
            endpoint="create",
            policy=policy,
        )

        sanitized = sanitize_body(
            body, max_length=binding.max_length, max_links=binding.max_links
        )
        self._antiabuse.check_duplicates(
            scope,
            subject_id=identity.subject_id,
            thread_id=thread_id,
            text=sanitized.stored_text,
            policy=policy,
        )

        author_history = len(
            self._store.execute_raw(
                "SELECT comment_id FROM cp_comments WHERE tenant_id = ? AND site_id = ?"
                " AND subject_id = ? LIMIT 1",
                (scope.tenant_id, scope.site_id, identity.subject_id),
            )
        )
        verdict = self._antiabuse.evaluate(
            scope,
            text=sanitized.stored_text,
            subject_id=identity.subject_id,
            policy=policy,
            author_comment_count=author_history,
            degraded=antispam_degraded,
        )

        state = states.initial_state(
            moderation_mode=flags.moderation_mode,
            risk_flagged=verdict.should_hold,
            antispam_degraded=verdict.degraded,
        )

        with self._store.transaction():
            self._store.upsert_identity(
                scope, identity.subject_id,
                display_name=identity.display_name, is_guest=identity.is_guest,
            )
            row = self._store.insert_comment(
                scope,
                thread_id=thread_id,
                subject_id=identity.subject_id,
                body=sanitized.stored_text,
                body_html=sanitized.rendered_html,
                state=state,
                parent_id=parent_id,
                depth=depth,
                risk_score=verdict.risk_score,
            )
            self._store.record_digest(
                scope,
                subject_id=identity.subject_id,
                thread_id=thread_id,
                digest=exact_digest(sanitized.stored_text),
                near_digest=near_digest(sanitized.stored_text),
                comment_id=row["comment_id"],
            )
            self._antiabuse.record_attempt(
                scope,
                subject_id=identity.subject_id,
                network_hmac=identity.network_hmac,
                thread_id=thread_id,
                endpoint="create",
            )
            self._store.refresh_thread_count(scope, thread_id)
            audit_log.record(
                self._store, scope,
                action="comment.create",
                actor=principal,
                object_type="comment",
                object_id=row["comment_id"],
                after={"state": state, "body": sanitized.stored_text, "risk": verdict.risk_score},
                request_id=request_id,
                rule_version=RULE_VERSION,
                artifact_hash=self._artifact_hash,
            )
            self._store.enqueue_event(
                scope,
                event_type="comment.created",
                payload={"comment_id": row["comment_id"], "state": state},
            )
            result = {
                "comment": self._public_dto(row, viewer_subject_id=identity.subject_id),
                "moderation": {
                    "state": state,
                    "held": state != states.PUBLISHED,
                    "degraded": verdict.degraded,
                },
            }
            if idempotency_key:
                self._store.remember_idempotent(
                    scope,
                    subject_id=identity.subject_id,
                    key=idempotency_key,
                    operation="create",
                    fingerprint=fingerprint,
                    response=result,
                )
        return result

    def edit_own_comment(
        self,
        scope: TenantScope,
        principal: Principal,
        identity: Identity,
        comment_id: str,
        *,
        body: str,
        request_id: str = "",
        cohort: str = "public",
    ) -> dict[str, Any]:
        flags = self._require_writes(scope, cohort)
        current = self._store.get_comment(scope, comment_id)
        authorize(
            principal, P_EDIT_OWN, scope, owner_subject_id=current["subject_id"]
        )
        if current["state"] == states.REMOVED:
            raise Conflict("a removed comment cannot be edited")

        binding = self.binding(scope)
        policy = self.policy(scope)
        sanitized = sanitize_body(
            body, max_length=binding.max_length, max_links=binding.max_links
        )
        verdict = self._antiabuse.evaluate(
            scope, text=sanitized.stored_text, subject_id=identity.subject_id, policy=policy
        )
        # An edit re-enters moderation: otherwise "post something bland, get
        # approved, rewrite it" is an open door.
        new_state = states.state_after_edit(
            current["state"], moderation_mode=flags.moderation_mode
        )
        if verdict.should_hold:
            new_state = states.PENDING

        with self._store.transaction():
            row = self._store.update_comment_body(
                scope, comment_id,
                body=sanitized.stored_text,
                body_html=sanitized.rendered_html,
                state=new_state,
                editor_subject_id=identity.subject_id,
            )
            self._store.refresh_thread_count(scope, row["thread_id"])
            audit_log.record(
                self._store, scope,
                action="comment.edit",
                actor=principal,
                object_type="comment",
                object_id=comment_id,
                before={"state": current["state"], "body": current["body"]},
                after={"state": new_state, "body": sanitized.stored_text},
                request_id=request_id,
                rule_version=RULE_VERSION,
                artifact_hash=self._artifact_hash,
            )
        return {
            "comment": self._public_dto(row, viewer_subject_id=identity.subject_id),
            "moderation": {"state": new_state, "held": new_state != states.PUBLISHED},
        }

    def delete_own_comment(
        self,
        scope: TenantScope,
        principal: Principal,
        comment_id: str,
        *,
        request_id: str = "",
        cohort: str = "public",
    ) -> dict[str, Any]:
        """Soft delete. The row and its text stay; the comment stops being public.

        Hard deletion is not offered: a thread with holes punched in it is
        unreadable, and an irreversible operation triggered by a misclick is
        not something this service is willing to perform.
        """
        self._require_writes(scope, cohort)
        current = self._store.get_comment(scope, comment_id)
        authorize(principal, P_DELETE_OWN, scope, owner_subject_id=current["subject_id"])

        target = states.validate_transition(
            current["state"], states.REMOVED, actor="human", reason="deleted by author"
        )
        with self._store.transaction():
            self._store.set_state(scope, comment_id, target)
            self._store.refresh_thread_count(scope, current["thread_id"])
            audit_log.record(
                self._store, scope,
                action="comment.delete_own",
                actor=principal,
                object_type="comment",
                object_id=comment_id,
                before={"state": current["state"]},
                after={"state": target},
                reason="deleted by author",
                request_id=request_id,
                artifact_hash=self._artifact_hash,
            )
        return {"comment_id": comment_id, "state": target}

    # --- reactions -------------------------------------------------------

    def set_reaction(
        self,
        scope: TenantScope,
        principal: Principal,
        identity: Identity,
        comment_id: str,
        reaction: str,
        *,
        request_id: str = "",
        cohort: str = "public",
    ) -> dict[str, Any]:
        self._require_writes(scope, cohort)
        authorize(principal, P_REACT, scope)
        if reaction not in REACTIONS:
            raise ValidationFailed(f"unknown reaction {reaction!r}", field="reaction")

        comment = self._store.get_comment(scope, comment_id)
        if not states.is_public_visible(comment["state"]):
            raise NotFound("comment not found", comment_id=comment_id)

        policy = self.policy(scope)
        self._antiabuse.check_rate_limits(
            scope,
            subject_id=identity.subject_id,
            network_hmac=identity.network_hmac,
            thread_id=comment["thread_id"],
            endpoint="react",
            policy=policy,
        )
        with self._store.transaction():
            self._store.set_reaction(scope, comment_id, identity.subject_id, reaction)
            self._antiabuse.record_attempt(
                scope, subject_id=identity.subject_id, network_hmac=identity.network_hmac,
                thread_id=comment["thread_id"], endpoint="react",
            )
            count = self._store.refresh_reaction_count(scope, comment_id)
        return {"comment_id": comment_id, "reaction": reaction, "reaction_count": count}

    def clear_reaction(
        self, scope: TenantScope, principal: Principal, identity: Identity, comment_id: str,
        *, cohort: str = "public",
    ) -> dict[str, Any]:
        self._require_writes(scope, cohort)
        authorize(principal, P_REACT, scope)
        self._store.get_comment(scope, comment_id)
        with self._store.transaction():
            self._store.clear_reaction(scope, comment_id, identity.subject_id)
            count = self._store.refresh_reaction_count(scope, comment_id)
        return {"comment_id": comment_id, "reaction": "", "reaction_count": count}

    # --- reports ---------------------------------------------------------

    def report_comment(
        self,
        scope: TenantScope,
        principal: Principal,
        identity: Identity,
        comment_id: str,
        *,
        reason: str,
        note: str = "",
        request_id: str = "",
        cohort: str = "public",
    ) -> dict[str, Any]:
        self._require_writes(scope, cohort)
        authorize(principal, P_REPORT, scope)
        if reason not in REPORT_REASONS:
            raise ValidationFailed(f"unknown report reason {reason!r}", field="reason")

        comment = self._store.get_comment(scope, comment_id)
        policy = self.policy(scope)

        with self._store.transaction():
            created = self._store.add_report(
                scope, comment_id, identity.subject_id,
                reason=reason, note=to_plain_preview(note, limit=200),
                network_hmac=identity.network_hmac,
            )
            brigade = self._antiabuse.detect_report_brigade(scope, comment_id, policy=policy)
            if created:
                audit_log.record(
                    self._store, scope,
                    action="report.create",
                    actor=principal,
                    object_type="comment",
                    object_id=comment_id,
                    after={"reason": reason, "brigade_suspected": brigade},
                    request_id=request_id,
                    artifact_hash=self._artifact_hash,
                )
            # Reaching the queue is a moderation decision, so it is a state
            # change, and a brigade does not get to make it: a coordinated
            # report campaign must not be able to hide a comment by volume.
            reporters = self._store.distinct_reporters(scope, comment_id)
            queue_it = (
                created
                and not brigade
                and reporters >= policy.report_brigade_threshold
                and states.transition_allowed(comment["state"], states.QUARANTINED)
            )
            if queue_it:
                self._store.set_state(scope, comment_id, states.QUARANTINED)
                self._store.record_moderation_action(
                    scope,
                    action="quarantine",
                    actor_subject_id="system",
                    actor_role="automation",
                    comment_id=comment_id,
                    from_state=comment["state"],
                    to_state=states.QUARANTINED,
                    reason="report threshold reached",
                    automatic=True,
                    rule_version=RULE_VERSION,
                    request_id=request_id,
                )
                self._store.refresh_thread_count(scope, comment["thread_id"])

        # The response is identical whether this was a new report or a repeat,
        # so a reporter cannot probe who else has reported a comment.
        return {"comment_id": comment_id, "accepted": True}

    # --- moderation ------------------------------------------------------

    def moderation_queue(
        self, scope: TenantScope, principal: Principal, *, limit: int = 50, cursor: str = ""
    ) -> dict[str, Any]:
        authorize(principal, P_MODERATION_QUEUE, scope)
        page = self._store.moderation_queue(scope, limit=limit, cursor=cursor)
        return {
            "items": [
                {
                    "comment_id": row["comment_id"],
                    "thread_id": row["thread_id"],
                    "state": row["state"],
                    "risk_score": row["risk_score"],
                    "report_count": row["report_count"],
                    "created_at": row["created_at"],
                    # A preview, not the body: the queue is a list, and a
                    # moderator opens what they intend to act on.
                    "preview": to_plain_preview(row["body"]),
                }
                for row in page.items
            ],
            "next_cursor": page.next_cursor,
            "has_more": page.has_more,
        }

    def moderate(
        self,
        scope: TenantScope,
        principal: Principal,
        comment_id: str,
        *,
        action: str,
        reason: str,
        request_id: str = "",
    ) -> dict[str, Any]:
        """hide / restore / remove / publish, each with a mandatory reason."""
        permission, target = {
            "hide": (P_MODERATION_HIDE, states.HIDDEN),
            "restore": (P_MODERATION_RESTORE, states.RESTORED),
            "remove": (P_MODERATION_REMOVE, states.REMOVED),
            "publish": (P_MODERATION_HIDE, states.PUBLISHED),
        }.get(action, (None, None))
        if permission is None:
            raise ValidationFailed(f"unknown moderation action {action!r}", field="action")

        authorize(principal, permission, scope)
        current = self._store.get_comment(scope, comment_id)

        new_state = states.validate_transition(
            current["state"], target, actor="human", reason=reason
        )
        with self._store.transaction():
            self._store.set_state(scope, comment_id, new_state)
            self._store.record_moderation_action(
                scope,
                action=action,
                actor_subject_id=principal.subject_id,
                actor_role=principal.role,
                comment_id=comment_id,
                from_state=current["state"],
                to_state=new_state,
                reason=reason,
                automatic=False,
                request_id=request_id,
            )
            self._store.refresh_thread_count(scope, current["thread_id"])
            audit_log.record(
                self._store, scope,
                action=f"moderation.{action}",
                actor=principal,
                object_type="comment",
                object_id=comment_id,
                before={"state": current["state"]},
                after={"state": new_state},
                reason=reason,
                request_id=request_id,
                artifact_hash=self._artifact_hash,
            )
        return {"comment_id": comment_id, "state": new_state}

    def resolve_reports(
        self,
        scope: TenantScope,
        principal: Principal,
        comment_id: str,
        *,
        reason: str,
        request_id: str = "",
    ) -> dict[str, Any]:
        authorize(principal, P_MODERATION_RESOLVE_REPORT, scope)
        self._store.get_comment(scope, comment_id)
        with self._store.transaction():
            resolved = self._store.resolve_reports(
                scope, comment_id, resolved_by=principal.subject_id
            )
            audit_log.record(
                self._store, scope,
                action="moderation.resolve_report",
                actor=principal,
                object_type="comment",
                object_id=comment_id,
                after={"resolved": resolved},
                reason=reason,
                request_id=request_id,
                artifact_hash=self._artifact_hash,
            )
        return {"comment_id": comment_id, "resolved": resolved}

    def ban_subject(
        self,
        scope: TenantScope,
        principal: Principal,
        subject_id: str,
        *,
        banned: bool,
        reason: str,
        request_id: str = "",
    ) -> dict[str, Any]:
        """Tenant-local. A ban here has no effect on any other site."""
        authorize(principal, P_BAN_USER, scope)
        if not reason.strip():
            raise ValidationFailed("a ban needs a reason", field="reason")
        before = self._store.get_identity(scope, subject_id)
        if before is None:
            raise NotFound("no such subject on this site", subject_id=subject_id)
        with self._store.transaction():
            self._store.set_ban(scope, subject_id, banned=banned, reason=reason)
            audit_log.record(
                self._store, scope,
                action="ban.apply" if banned else "ban.lift",
                actor=principal,
                object_type="identity",
                object_id=subject_id,
                before={"banned": bool(before["banned"])},
                after={"banned": banned},
                reason=reason,
                request_id=request_id,
                artifact_hash=self._artifact_hash,
            )
        return {"subject_id": subject_id, "banned": banned}

    # --- policy and audit ------------------------------------------------

    def update_policy(
        self,
        scope: TenantScope,
        principal: Principal,
        *,
        reason: str,
        request_id: str = "",
        **values: Any,
    ) -> dict[str, Any]:
        authorize(principal, P_POLICY_WRITE, scope)
        before = self._store.get_policy(scope) or {}
        with self._store.transaction():
            self._store.upsert_policy(scope, updated_by=principal.subject_id, **values)
            after = self._store.get_policy(scope) or {}
            audit_log.record(
                self._store, scope,
                action="policy.update",
                actor=principal,
                object_type="policy",
                object_id=scope.key,
                before=before,
                after=after,
                reason=reason,
                request_id=request_id,
                artifact_hash=self._artifact_hash,
            )
        return after

    def read_audit(
        self, scope: TenantScope, principal: Principal, *, limit: int = 100
    ) -> tuple[dict[str, Any], ...]:
        """Tenant-local audit. An auditor of one site sees only that site."""
        authorize(principal, P_AUDIT_READ, scope)
        return self._store.list_audit(scope, limit=limit)
