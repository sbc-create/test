"""HTTP-facing community ratings API (library + public write facade)."""

from __future__ import annotations

import json
import secrets
import time
from typing import Any

from factory.community import metrics
from factory.community.antifraud import (
    AntifraudGuard,
    KillSwitchActive,
    OriginRejected,
    RateLimited,
    ReadOnlyMode,
)
from factory.community.cohort import CohortDenied, decide_cohort
from factory.community.identity_v1 import (
    BOUND_RATING_SPACE,
    IDENTITY_MODE,
    IdentityError,
    IdentityForgery,
    reject_client_supplied_user_id,
    resolve_or_mint,
)
from factory.community.rollout import as_public_dict, load_flags, writes_allowed
from factory.community.service import CommunityConflict, CommunityValidationError, CommunityVotesService
from factory.community.spaces import merge_guest_into_account, rating_space_for_domain

MAX_BODY_BYTES = 4096
CSRF_COOKIE = "yummy_cr_csrf"


class CommunityRatingsAPI:
    """Thin adapter: GET rating/preview/my vote, PUT/DELETE vote, history."""

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


class PublicRatingsFacade:
    """Production public surface for Yummy 1% canary writes."""

    def __init__(self, service: CommunityVotesService, guard: AntifraudGuard | None = None) -> None:
        self.api = CommunityRatingsAPI(service, guard)
        self.guard = self.api.guard
        self.service = service

    def session_bootstrap(self, *, cookie_header: str | None) -> dict[str, Any]:
        flags = load_flags()
        identity, set_cookie = resolve_or_mint(cookie_header, mint_if_missing=True)
        if identity.minted:
            metrics.incr("identities_created")
        cohort = decide_cohort(
            identity.identity_id,
            rollout_percent=int(flags.PUBLIC_WRITE_ROLLOUT_PERCENT) if writes_allowed(flags) else 0,
        )
        csrf = secrets.token_urlsafe(24)
        metrics.incr("widget_impressions")
        metrics.incr("session_bootstraps")
        if cohort.eligible:
            metrics.incr("eligible_widget_impressions")
            metrics.incr("eligible_cohort_impressions")
            # Distinct exposure, counted without storing the identity itself.
            metrics.mark_unique("exposed_visitor", identity.identity_id)
        return {
            "status": 200,
            "identity_mode": IDENTITY_MODE,
            "cohort": cohort.as_dict(),
            "flags": as_public_dict(flags),
            "csrf_token": csrf,
            "cache_control": "no-store",
            "_set_identity_cookie": set_cookie,
            "_set_csrf": csrf,
            "_identity_id": identity.identity_id,  # internal only — stripped by gateway
        }

    def get_public(
        self,
        *,
        subject_id: str,
        cookie_header: str | None,
        rating_space_id: str = BOUND_RATING_SPACE,
    ) -> dict[str, Any]:
        if rating_space_id != BOUND_RATING_SPACE:
            metrics.incr("cross_space_denied")
            return {"status": 403, "error": "cross-space denied", "code": "CrossSpaceDenied"}
        identity, set_cookie = resolve_or_mint(cookie_header, mint_if_missing=True)
        flags = load_flags()
        cohort = decide_cohort(
            identity.identity_id,
            rollout_percent=int(flags.PUBLIC_WRITE_ROLLOUT_PERCENT) if writes_allowed(flags) else 0,
        )
        # Native-only public score — never pass prior inputs.
        body = self.service.get_rating(
            rating_space_id=rating_space_id,
            subject_id=subject_id,
            actor_id=identity.identity_id,
            yummy_prior_inputs={},
        )
        # Force native display fields for Stage06 policy.
        body["public_brand_score"] = body.get("native_user_average")
        body["public_score_mode"] = "NATIVE_ONLY"
        body["native_absent_label"] = (
            "Пока нет пользовательских оценок" if body.get("native_absent") else None
        )
        body["cohort"] = cohort.as_dict()
        body["writes_ui_enabled"] = bool(cohort.eligible and writes_allowed(flags))
        body["identity"] = identity.as_public()
        body["status"] = 200
        body["cache_control"] = "no-store"
        body["_set_identity_cookie"] = set_cookie
        body["_identity_id"] = identity.identity_id
        return body

    def widget_event(
        self,
        *,
        event: str,
        cookie_header: str | None,
    ) -> dict[str, Any]:
        """Beacon from the mounted widget: it is on screen for this visitor.

        Server-side exposure counting is the only honest kind. The injector can
        only report that it *offered* the widget; whether the browser actually
        rendered it is something only the browser knows. The payload carries no
        user text, no page content and no identifier — the identity comes from
        the signed cookie, exactly as on every other endpoint.
        """
        if event != "rendered":
            return {"status": 400, "error": "unsupported event", "code": "CommunityValidationError"}
        identity, set_cookie = resolve_or_mint(cookie_header, mint_if_missing=True)
        flags = load_flags()
        cohort = decide_cohort(
            identity.identity_id,
            rollout_percent=int(flags.PUBLIC_WRITE_ROLLOUT_PERCENT) if writes_allowed(flags) else 0,
        )
        # Only a genuinely eligible visitor can mark the widget as rendered;
        # otherwise a crafted beacon could inflate the exposure figure.
        if not cohort.eligible:
            return {
                "status": 403,
                "error": "not in public-write cohort",
                "code": "CohortDenied",
                "cache_control": "no-store",
                "_set_identity_cookie": set_cookie,
            }
        metrics.incr("widget_rendered")
        metrics.mark_unique("exposed_visitor", identity.identity_id)
        # 200, not 204: the gateway always writes a JSON body with a
        # Content-Length, and a 204 carrying a body is a malformed response.
        return {
            "status": 200,
            "ok": True,
            "cache_control": "no-store",
            "_set_identity_cookie": set_cookie,
        }

    def preview(
        self,
        *,
        subject_id: str,
        score: Any,
        cookie_header: str | None,
        rating_space_id: str = BOUND_RATING_SPACE,
    ) -> dict[str, Any]:
        try:
            if rating_space_id != BOUND_RATING_SPACE:
                raise CohortDenied("cross-space")
            identity, set_cookie = resolve_or_mint(cookie_header, mint_if_missing=True)
            score_i = _coerce_score(score)
            metrics.incr("preview_requests")
            prev = self.service.preview_one(
                rating_space_id=rating_space_id,
                subject_id=subject_id,
                actor_id=identity.identity_id,
                score=score_i,
                yummy_prior_inputs={},  # native-only
            )
            prev["status"] = 200
            prev["cache_control"] = "no-store"
            prev["_set_identity_cookie"] = set_cookie
            return prev
        except (IdentityError, CommunityValidationError, CohortDenied) as exc:
            return {"status": getattr(exc, "status", 400), "error": str(exc), "code": type(exc).__name__}

    def mutate(
        self,
        *,
        method: str,
        subject_id: str,
        body: dict[str, Any] | None,
        cookie_header: str | None,
        origin: str | None,
        csrf_header: str | None,
        csrf_cookie: str | None,
        idempotency_key: str,
        content_type: str | None,
        peer_ip: str = "",
        body_len: int = 0,
        rating_space_id: str = BOUND_RATING_SPACE,
    ) -> dict[str, Any]:
        t0 = time.monotonic()
        metrics.incr("write_attempts")
        set_cookie = None
        try:
            self.guard.sync_from_rollout()
            flags = load_flags()
            if not writes_allowed(flags):
                self.guard.assert_writable()
                if not flags.PUBLIC_WRITE_ENABLED:
                    raise KillSwitchActive("public writes disabled")
            if body_len > MAX_BODY_BYTES:
                raise CommunityValidationError("request body too large")
            if content_type and "application/json" not in content_type.lower():
                raise CommunityValidationError("Content-Type must be application/json")
            reject_client_supplied_user_id(body)
            if rating_space_id != BOUND_RATING_SPACE:
                metrics.incr("cross_space_denied")
                raise CohortDenied("cross-space write denied")
            # Never trust body.rating_space_id
            if body and body.get("rating_space_id") not in (None, "", BOUND_RATING_SPACE):
                metrics.incr("cross_space_denied")
                raise CohortDenied("body rating_space_id rejected")
            if body and "title_id" in body and "subject_id" not in body:
                # allow alias but still server-bound
                pass

            identity, set_cookie = resolve_or_mint(cookie_header, mint_if_missing=True)
            cohort = decide_cohort(
                identity.identity_id,
                rollout_percent=int(flags.PUBLIC_WRITE_ROLLOUT_PERCENT),
            )
            if not cohort.eligible:
                metrics.incr("cohort_denied")
                raise CohortDenied("not in public-write cohort")

            try:
                self.guard.check_origin(origin, csrf_token=csrf_header, session_csrf=csrf_cookie)
            except OriginRejected as exc:
                if "CSRF" in str(exc):
                    metrics.incr("csrf_denied")
                else:
                    metrics.incr("origin_denied")
                self.guard.note_invalid(f"id:{identity.identity_id}")
                raise

            ip_hmac = self.guard.ip_prefix_hmac(peer_ip) if peer_ip else ""

            if method.upper() in ("PUT", "POST") and method.upper() != "DELETE":
                metrics.incr("cast_attempts")
                score = _coerce_score((body or {}).get("score", (body or {}).get("rating")))
                # Rate-limit only after schema validation so junk probes do not burn title budget.
                self.guard.check_rate(
                    account_id="",
                    token_id=identity.identity_id,
                    ip_hmac_prefix=ip_hmac,
                    subject_id=subject_id,
                )
                # quarantine heuristic
                q, reason = self.guard.should_quarantine(
                    identity_id=identity.identity_id, subject_id=subject_id
                )
                result = self.service.put_vote(
                    idempotency_key=idempotency_key,
                    rating_space_id=BOUND_RATING_SPACE,
                    subject_id=subject_id,
                    actor_id=identity.identity_id,
                    score=score,
                    yummy_prior_inputs={},
                )
                if q:
                    admin_quarantine_vote(
                        self.service,
                        rating_space_id=BOUND_RATING_SPACE,
                        subject_id=subject_id,
                        actor_id=identity.identity_id,
                        reason_code=reason,
                    )
                    metrics.incr("quarantined_votes")
                    result["quarantined"] = True
                    result["quarantine_reason"] = reason
                action = result.get("action")
                if action == "CREATE":
                    metrics.incr("cast_accepted")
                elif action == "UPDATE":
                    metrics.incr("update_accepted")
                result["cache_control"] = "no-store"
                result["_set_identity_cookie"] = set_cookie
                result["cohort"] = cohort.as_dict()
                result["identity"] = identity.as_public()
                return result

            if method.upper() in ("DELETE",) or (method.upper() == "POST" and (body or {}).get("action") == "retract"):
                self.guard.check_rate(
                    account_id="",
                    token_id=identity.identity_id,
                    ip_hmac_prefix=ip_hmac,
                    subject_id=subject_id,
                )
                result = self.service.delete_vote(
                    idempotency_key=idempotency_key,
                    rating_space_id=BOUND_RATING_SPACE,
                    subject_id=subject_id,
                    actor_id=identity.identity_id,
                    yummy_prior_inputs={},
                )
                metrics.incr("retract_accepted")
                result["cache_control"] = "no-store"
                result["_set_identity_cookie"] = set_cookie
                result["cohort"] = cohort.as_dict()
                result["identity"] = identity.as_public()
                return result

            raise CommunityValidationError(f"unsupported method {method}")
        except CohortDenied as exc:
            metrics.incr("write_4xx")
            return {"status": 403, "error": str(exc), "code": "CohortDenied"}
        except IdentityForgery as exc:
            metrics.incr("write_4xx")
            return {"status": 401, "error": str(exc), "code": "IdentityForgery"}
        except IdentityError as exc:
            metrics.incr("write_4xx")
            return {"status": 401, "error": str(exc), "code": type(exc).__name__}
        except RateLimited as exc:
            metrics.incr("rate_limited")
            metrics.incr("write_4xx")
            return {"status": 429, "error": str(exc), "code": "RateLimited"}
        except OriginRejected as exc:
            metrics.incr("write_4xx")
            return {"status": 403, "error": str(exc), "code": "OriginRejected"}
        except (KillSwitchActive, ReadOnlyMode) as exc:
            return {"status": 503, "error": str(exc), "code": type(exc).__name__}
        except CommunityValidationError as exc:
            metrics.incr("invalid_rating_denied")
            metrics.incr("write_4xx")
            return {"status": 400, "error": str(exc), "code": "CommunityValidationError"}
        except CommunityConflict as exc:
            metrics.incr("write_4xx")
            return {"status": 409, "error": str(exc), "code": "CommunityConflict"}
        except Exception as exc:
            metrics.incr("write_5xx")
            return {"status": 500, "error": "internal error", "code": type(exc).__name__}
        finally:
            metrics.observe_latency_ms((time.monotonic() - t0) * 1000.0)


def _coerce_score(value: Any) -> int:
    if isinstance(value, bool) or value is None:
        raise CommunityValidationError("score must be integer 1..10")
    if isinstance(value, float):
        if value != int(value):
            raise CommunityValidationError("score must be integer 1..10")
        value = int(value)
    if isinstance(value, str):
        raise CommunityValidationError("score must be integer 1..10")
    if isinstance(value, (list, dict)):
        raise CommunityValidationError("score must be integer 1..10")
    if not isinstance(value, int) or value < 1 or value > 10:
        raise CommunityValidationError("score must be integer 1..10")
    return value


def admin_quarantine_vote(
    service: CommunityVotesService,
    *,
    rating_space_id: str,
    subject_id: str,
    actor_id: str,
    reason_code: str,
    moderator_id: str = "",
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
        # immutable audit
        store.conn.execute(
            """INSERT INTO community_vote_events (
                event_id, rating_space_id, subject_id, actor_id, dimension, action,
                old_score, new_score, status, policy_version, risk_state,
                idempotency_key, created_at, payload_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'),?)""",
            (
                f"mod-q-{secrets.token_hex(8)}",
                rating_space_id,
                subject_id,
                actor_id,
                "overall",
                "MODERATOR_QUARANTINE",
                int(vote["score"]),
                int(vote["score"]),
                "QUARANTINED",
                "rating_policy_v1",
                "QUARANTINED",
                f"mod-q-{secrets.token_hex(8)}",
                json.dumps(
                    {
                        "moderator_id": moderator_id,
                        "reason_code": reason_code,
                        "before": "ACCEPTED",
                        "after": "QUARANTINED",
                    },
                    ensure_ascii=False,
                ),
            ),
        )
        store.conn.execute("COMMIT")
        return {
            "status": 200,
            "action": "QUARANTINE",
            "reason_code": reason_code,
            "aggregate_version": new_v,
            "vote_count": rebuilt["vote_count"],
            "moderator_id": moderator_id,
        }
    except Exception:
        store.conn.execute("ROLLBACK")
        raise


def admin_resolve_quarantine(
    service: CommunityVotesService,
    *,
    rating_space_id: str,
    subject_id: str,
    actor_id: str,
    decision: str,
    reason_code: str,
    moderator_id: str,
) -> dict[str, Any]:
    """decision: approve|reject — approve restores ACCEPTED; reject keeps out of aggregate."""
    if decision not in ("approve", "reject"):
        raise CommunityValidationError("decision must be approve|reject")
    if not reason_code or not moderator_id:
        raise CommunityValidationError("reason_code and moderator_id required")
    store = service.store
    store.conn.execute("BEGIN IMMEDIATE")
    try:
        row = store.get_vote_row_any_status(
            rating_space_id=rating_space_id, subject_id=subject_id, actor_id=actor_id
        )
        if not row:
            store.conn.execute("COMMIT")
            return {"status": 404, "error": "vote not found"}
        before = row["status"]
        if decision == "approve":
            store.conn.execute(
                """UPDATE community_votes SET status='ACCEPTED', risk_state='CLEAR', updated_at=datetime('now')
                   WHERE rating_space_id=? AND subject_id=? AND actor_id=? AND dimension='overall'""",
                (rating_space_id, subject_id, actor_id),
            )
            after = "ACCEPTED"
        else:
            store.conn.execute(
                """UPDATE community_votes SET status='RETRACTED', risk_state='REJECTED',
                   retracted_at=datetime('now'), updated_at=datetime('now')
                   WHERE rating_space_id=? AND subject_id=? AND actor_id=? AND dimension='overall'""",
                (rating_space_id, subject_id, actor_id),
            )
            after = "RETRACTED"
        rebuilt = store.rebuild_aggregate_from_votes(
            rating_space_id=rating_space_id, subject_id=subject_id
        )
        store.conn.execute(
            """UPDATE community_aggregates SET vote_sum=?, vote_count=?,
               aggregate_version=aggregate_version+1, updated_at=datetime('now')
               WHERE rating_space_id=? AND subject_id=? AND dimension='overall'""",
            (rebuilt["vote_sum"], rebuilt["vote_count"], rating_space_id, subject_id),
        )
        store.conn.execute(
            """INSERT INTO community_vote_events (
                event_id, rating_space_id, subject_id, actor_id, dimension, action,
                old_score, new_score, status, policy_version, risk_state,
                idempotency_key, created_at, payload_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'),?)""",
            (
                f"mod-r-{secrets.token_hex(8)}",
                rating_space_id,
                subject_id,
                actor_id,
                "overall",
                f"MODERATOR_{decision.upper()}",
                int(row["score"]),
                int(row["score"]),
                after,
                "rating_policy_v1",
                after,
                f"mod-r-{secrets.token_hex(8)}",
                json.dumps(
                    {
                        "moderator_id": moderator_id,
                        "reason_code": reason_code,
                        "before": before,
                        "after": after,
                    },
                    ensure_ascii=False,
                ),
            ),
        )
        store.conn.execute("COMMIT")
        return {"status": 200, "decision": decision, "before": before, "after": after}
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
