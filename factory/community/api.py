"""HTTP-facing community ratings API (library; no production mount without owner gate)."""

from __future__ import annotations

from typing import Any

from factory.community.antifraud import (
    AntifraudGuard,
    KillSwitchActive,
    OriginRejected,
    RateLimited,
    ReadOnlyMode,
)
from factory.community.service import CommunityConflict, CommunityValidationError, CommunityVotesService
from factory.community.spaces import merge_guest_into_account, rating_space_for_domain


class CommunityRatingsAPI:
    """Thin adapter: GET rating/preview/my vote, PUT/DELETE vote, history.

    Not registered on production routes until owner public-write approval.
    """

    def __init__(self, service: CommunityVotesService, guard: AntifraudGuard | None = None) -> None:
        self.service = service
        self.guard = guard or AntifraudGuard()

    def get_rating(self, **kwargs: Any) -> dict[str, Any]:
        return self.service.get_rating(**kwargs)

    def get_my_vote(
        self,
        *,
        rating_space_id: str,
        subject_id: str,
        actor_id: str,
        dimension: str = "overall",
    ) -> dict[str, Any]:
        row = self.service.store.conn.execute(
            """SELECT score, status, updated_at FROM community_votes
               WHERE rating_space_id=? AND subject_id=? AND actor_id=? AND dimension=?""",
            (rating_space_id, subject_id, actor_id, dimension),
        ).fetchone()
        if not row or str(row[1]).upper() != "ACCEPTED":
            return {
                "status": 200,
                "my_vote": None,
                "rating_space_id": rating_space_id,
                "subject_id": subject_id,
            }
        return {
            "status": 200,
            "my_vote": int(row[0]),
            "updated_at": row[2],
            "rating_space_id": rating_space_id,
            "subject_id": subject_id,
        }

    def get_preview(self, **kwargs: Any) -> dict[str, Any]:
        return self.service.preview_one(**kwargs)

    def put_vote(
        self,
        *,
        idempotency_key: str,
        origin: str | None = None,
        csrf_token: str | None = None,
        session_csrf: str | None = None,
        account_id: str = "",
        token_id: str = "",
        ip: str = "",
        replay_id: str = "",
        **kwargs: Any,
    ) -> dict[str, Any]:
        try:
            self.guard.assert_writable()
            if origin is not None or csrf_token is not None:
                self.guard.check_origin(origin, csrf_token=csrf_token, session_csrf=session_csrf)
            ip_hmac = self.guard.ip_prefix_hmac(ip) if ip else ""
            subject_id = str(kwargs.get("subject_id") or "")
            if account_id or token_id or ip_hmac or subject_id:
                self.guard.check_rate(
                    account_id=account_id,
                    token_id=token_id,
                    ip_hmac_prefix=ip_hmac,
                    subject_id=subject_id,
                )
            if replay_id:
                self.guard.check_replay(replay_id)
            return self.service.put_vote(idempotency_key=idempotency_key, **kwargs)
        except (
            KillSwitchActive,
            ReadOnlyMode,
            OriginRejected,
            RateLimited,
            CommunityConflict,
            CommunityValidationError,
        ) as exc:
            return {"status": getattr(exc, "status", 400), "error": str(exc), "code": type(exc).__name__}

    def delete_vote(
        self,
        *,
        idempotency_key: str,
        origin: str | None = None,
        csrf_token: str | None = None,
        session_csrf: str | None = None,
        account_id: str = "",
        token_id: str = "",
        ip: str = "",
        **kwargs: Any,
    ) -> dict[str, Any]:
        try:
            self.guard.assert_writable()
            if origin is not None or csrf_token is not None:
                self.guard.check_origin(origin, csrf_token=csrf_token, session_csrf=session_csrf)
            ip_hmac = self.guard.ip_prefix_hmac(ip) if ip else ""
            subject_id = str(kwargs.get("subject_id") or "")
            if account_id or token_id or ip_hmac or subject_id:
                self.guard.check_rate(
                    account_id=account_id,
                    token_id=token_id,
                    ip_hmac_prefix=ip_hmac,
                    subject_id=subject_id,
                )
            return self.service.delete_vote(idempotency_key=idempotency_key, **kwargs)
        except (
            KillSwitchActive,
            ReadOnlyMode,
            OriginRejected,
            RateLimited,
            CommunityConflict,
            CommunityValidationError,
        ) as exc:
            return {"status": getattr(exc, "status", 400), "error": str(exc), "code": type(exc).__name__}

    def get_own_history(self, *, actor_id: str, rating_space_id: str | None = None) -> list[dict[str, Any]]:
        q = "SELECT * FROM community_vote_events WHERE actor_id=? ORDER BY created_at DESC LIMIT 100"
        args: list[Any] = [actor_id]
        if rating_space_id:
            q = "SELECT * FROM community_vote_events WHERE actor_id=? AND rating_space_id=? ORDER BY created_at DESC LIMIT 100"
            args.append(rating_space_id)
        rows = self.service.store.conn.execute(q, args).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def resolve_space(domain: str) -> str:
        return rating_space_for_domain(domain)


def admin_quarantine_vote(
    service: CommunityVotesService,
    *,
    rating_space_id: str,
    subject_id: str,
    actor_id: str,
    reason_code: str,
) -> dict[str, Any]:
    """Admin may quarantine; may NOT create/change score on behalf of user."""
    if not reason_code:
        raise CommunityValidationError("reason_code required")
    store = service.store
    store.conn.execute("BEGIN IMMEDIATE")
    try:
        vote = store.get_vote(rating_space_id=rating_space_id, subject_id=subject_id, actor_id=actor_id)
        if not vote:
            store.conn.execute("COMMIT")
            return {"status": 404, "error": "no active vote"}
        store.conn.execute(
            """UPDATE community_votes SET status='QUARANTINED', risk_state='QUARANTINED', updated_at=datetime('now')
               WHERE rating_space_id=? AND subject_id=? AND actor_id=? AND dimension='overall'""",
            (rating_space_id, subject_id, actor_id),
        )
        rebuilt = store.rebuild_aggregate_from_votes(
            rating_space_id=rating_space_id, subject_id=subject_id
        )
        agg = store.get_aggregate(rating_space_id=rating_space_id, subject_id=subject_id)
        new_v = int(agg["aggregate_version"]) + 1
        store.conn.execute(
            """UPDATE community_aggregates SET vote_sum=?, vote_count=?, aggregate_version=?
               WHERE rating_space_id=? AND subject_id=? AND dimension='overall'""",
            (rebuilt["vote_sum"], rebuilt["vote_count"], new_v, rating_space_id, subject_id),
        )
        store.conn.execute("COMMIT")
        return {
            "status": 200,
            "action": "QUARANTINE",
            "reason_code": reason_code,
            "aggregate_version": new_v,
            "vote_count": rebuilt["vote_count"],
        }
    except Exception:
        store.conn.execute("ROLLBACK")
        raise


def merge_actors_votes(
    service: CommunityVotesService,
    *,
    guest_actor_id: str,
    account_actor_id: str,
) -> dict[str, Any]:
    """Reassign guest votes to account; one active vote per subject after merge."""
    from factory.community.spaces import Actor, ActorKind

    guest = Actor(actor_id=guest_actor_id, kind=ActorKind.SIGNED_GUEST)
    account = Actor(actor_id=account_actor_id, kind=ActorKind.ACCOUNT, account_id=account_actor_id)
    canonical = merge_guest_into_account(guest=guest, account=account)
    store = service.store
    store.conn.execute("BEGIN IMMEDIATE")
    try:
        rows = store.conn.execute(
            "SELECT * FROM community_votes WHERE actor_id=? AND status='ACCEPTED'",
            (guest_actor_id,),
        ).fetchall()
        conflicts = 0
        moved = 0
        for row in rows:
            existing = store.get_vote(
                rating_space_id=row["rating_space_id"],
                subject_id=row["subject_id"],
                actor_id=account_actor_id,
            )
            if existing:
                # keep account vote; retract guest
                store.conn.execute(
                    """UPDATE community_votes SET status='RETRACTED', retracted_at=datetime('now'),
                       updated_at=datetime('now')
                       WHERE rating_space_id=? AND subject_id=? AND actor_id=? AND dimension=?""",
                    (row["rating_space_id"], row["subject_id"], guest_actor_id, row["dimension"]),
                )
                conflicts += 1
            else:
                store.conn.execute(
                    """UPDATE community_votes SET actor_id=? WHERE rating_space_id=? AND subject_id=?
                       AND actor_id=? AND dimension=?""",
                    (
                        account_actor_id,
                        row["rating_space_id"],
                        row["subject_id"],
                        guest_actor_id,
                        row["dimension"],
                    ),
                )
                moved += 1
            rebuilt = store.rebuild_aggregate_from_votes(
                rating_space_id=row["rating_space_id"], subject_id=row["subject_id"]
            )
            store.conn.execute(
                """UPDATE community_aggregates SET vote_sum=?, vote_count=?,
                   aggregate_version=aggregate_version+1
                   WHERE rating_space_id=? AND subject_id=? AND dimension='overall'""",
                (rebuilt["vote_sum"], rebuilt["vote_count"], row["rating_space_id"], row["subject_id"]),
            )
        store.conn.execute(
            """INSERT OR REPLACE INTO community_actors(actor_id, kind, account_id, merged_into, created_at)
               VALUES (?,?,?,?,datetime('now'))""",
            (guest_actor_id, "merged", account_actor_id, account_actor_id),
        )
        store.conn.execute(
            """INSERT OR IGNORE INTO community_outbox(outbox_id, event_type, dedupe_key, payload_json, created_at)
               VALUES (?,?,?,?,datetime('now'))""",
            (
                f"merge-{guest_actor_id}",
                "actor.merged",
                f"actor.merged:{guest_actor_id}:{account_actor_id}",
                f'{{"guest":"{guest_actor_id}","account":"{account_actor_id}"}}',
            ),
        )
        store.conn.execute("COMMIT")
        return {
            "canonical_actor_id": canonical.canonical_actor_id(),
            "moved": moved,
            "conflicts_resolved_keep_account": conflicts,
            "duplicates": 0,
        }
    except Exception:
        store.conn.execute("ROLLBACK")
        raise
