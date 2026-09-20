"""Transactional community vote service with preview and idempotency."""

from __future__ import annotations

import hashlib
import json
import uuid
from decimal import Decimal
from typing import Any

from factory.community.formulas import (
    DEFAULT_PRIOR_STRENGTH_M,
    NativeAggregate,
    YummyPublic,
    build_yummy_prior,
    format_delta,
    round_display,
)
from factory.community.policy import POLICY_VERSION
from factory.community.store import CommunityStore
from factory.ratings.models import utc_now_iso

DIMENSION_OVERALL = "overall"
STATUS_ACCEPTED = "ACCEPTED"
STATUS_RETRACTED = "RETRACTED"
STATUS_QUARANTINED = "QUARANTINED"


class CommunityConflict(Exception):
    status = 409


class CommunityValidationError(ValueError):
    status = 400


def _digest(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def validate_score(score: int) -> int:
    if isinstance(score, bool) or not isinstance(score, int) or score < 1 or score > 10:
        raise CommunityValidationError("score must be integer 1..10")
    return score


class CommunityVotesService:
    def __init__(self, store: CommunityStore) -> None:
        self.store = store

    def get_rating(
        self,
        *,
        rating_space_id: str,
        subject_id: str,
        actor_id: str | None = None,
        external: dict[str, Any] | None = None,
        yummy_prior_inputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        agg = self.store.get_aggregate(rating_space_id=rating_space_id, subject_id=subject_id)
        native = NativeAggregate(int(agg["vote_sum"]), int(agg["vote_count"]))
        native.assert_invariants()
        my = None
        if actor_id:
            my = self.store.get_vote(
                rating_space_id=rating_space_id, subject_id=subject_id, actor_id=actor_id
            )

        body: dict[str, Any] = {
            "rating_space_id": rating_space_id,
            "subject_id": subject_id,
            "policy_version": POLICY_VERSION,
            "aggregate_version": int(agg["aggregate_version"]),
            "external_observations": external or {},
            "native_user_average": None
            if native.average is None
            else str(round_display(native.average, "0.1")),
            "native_vote_count": native.vote_count,
            "native_absent": native.vote_count == 0,
            "native_absent_label": (
                "Пока нет пользовательских оценок" if native.vote_count == 0 else None
            ),
            "my_vote": None if not my else int(my["score"]),
            "component_provenance": {"layer": "native_user_average", "space": rating_space_id},
        }

        if rating_space_id == "yummy":
            inp = yummy_prior_inputs or {}
            use_native_only = not inp or (
                inp.get("animedia_native") is None
                and inp.get("shikimori") is None
                and not inp.get("force_bayes")
            )
            if use_native_only:
                body["public_brand_score"] = body["native_user_average"]
                body["raw_yummy_average"] = body["native_user_average"]
                body["displayed_vote_count"] = native.vote_count
                body["component_provenance"] = {
                    "layer": "native_user_average",
                    "space": "yummy",
                    "public_score_mode": "NATIVE_ONLY",
                    "double_counted_source_count": 0,
                }
                body["ui_label"] = "Оценка Yummy"
                body["prior_tooltip"] = None
            else:
                prior, prov = build_yummy_prior(
                    animedia_native=_dec(inp.get("animedia_native")),
                    shikimori=_dec(inp.get("shikimori")),
                    animedia_embeds_shikimori=bool(inp.get("animedia_embeds_shikimori")),
                )
                pub = YummyPublic(
                    native.vote_sum,
                    native.vote_count,
                    prior,
                    m=int(inp.get("m") or DEFAULT_PRIOR_STRENGTH_M),
                )
                body["public_brand_score"] = (
                    None if pub.public_score is None else str(round_display(pub.public_score))
                )
                body["raw_yummy_average"] = (
                    None if pub.raw_average is None else str(round_display(pub.raw_average))
                )
                body["displayed_vote_count"] = pub.displayed_vote_count()
                body["component_provenance"] = prov
                body["ui_label"] = "Оценка Yummy"
                body["prior_tooltip"] = (
                    "Расчётная оценка: голоса пользователей Yummy и версионируемая база Animedia/Shikimori"
                )
        else:
            body["public_brand_score"] = body["native_user_average"]
            body["ui_label"] = "Оценка Animedia"
            body["displayed_vote_count"] = native.vote_count

        body["preview_by_score"] = self.preview_map(
            rating_space_id=rating_space_id,
            subject_id=subject_id,
            actor_id=actor_id,
            yummy_prior_inputs=yummy_prior_inputs,
        )
        return body

    def preview_map(
        self,
        *,
        rating_space_id: str,
        subject_id: str,
        actor_id: str | None,
        yummy_prior_inputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for score in range(1, 11):
            out[str(score)] = self.preview_one(
                rating_space_id=rating_space_id,
                subject_id=subject_id,
                actor_id=actor_id,
                score=score,
                yummy_prior_inputs=yummy_prior_inputs,
            )
        return out

    def preview_one(
        self,
        *,
        rating_space_id: str,
        subject_id: str,
        actor_id: str | None,
        score: int,
        yummy_prior_inputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        score = validate_score(score)
        agg = self.store.get_aggregate(rating_space_id=rating_space_id, subject_id=subject_id)
        native = NativeAggregate(int(agg["vote_sum"]), int(agg["vote_count"]))
        existing = None
        if actor_id:
            existing = self.store.get_vote(
                rating_space_id=rating_space_id, subject_id=subject_id, actor_id=actor_id
            )
        before = native.average
        if existing:
            after_nat = native.after_update(int(existing["score"]), score)
            action = "replace"
        else:
            after_nat = native.after_create(score)
            action = "create"
        after = after_nat.average

        if rating_space_id == "yummy":
            inp = yummy_prior_inputs or {}
            use_native_only = not inp or (
                inp.get("animedia_native") is None
                and inp.get("shikimori") is None
                and not inp.get("force_bayes")
            )
            if use_native_only:
                before, after = before, after_nat.average
            else:
                prior, _ = build_yummy_prior(
                    animedia_native=_dec(inp.get("animedia_native")),
                    shikimori=_dec(inp.get("shikimori")),
                    animedia_embeds_shikimori=bool(inp.get("animedia_embeds_shikimori")),
                )
                m = int(inp.get("m") or DEFAULT_PRIOR_STRENGTH_M)
                before_pub = YummyPublic(native.vote_sum, native.vote_count, prior, m=m).public_score
                after_pub = YummyPublic(after_nat.vote_sum, after_nat.vote_count, prior, m=m).public_score
                before, after = before_pub, after_pub

        delta = None if before is None or after is None else (after - before)
        if before is None and after is not None:
            delta = after  # from absent
        before_disp = None if before is None else str(round_display(before, "0.1"))
        after_disp = None if after is None else str(round_display(after, "0.1"))
        # If displayed one-decimal does not change, say so explicitly for UI.
        display_unchanged = (
            before_disp is not None and after_disp is not None and before_disp == after_disp
        )
        return {
            "action": action,
            "score": score,
            "before": before_disp,
            "after": after_disp,
            "before_precise": None if before is None else str(before),
            "after_precise": None if after is None else str(after),
            "delta": None if delta is None else format_delta(delta),
            "delta_raw": None if delta is None else str(delta),
            "display_unchanged": display_unchanged,
            "vote_count_after": after_nat.vote_count,
        }

    def put_vote(
        self,
        *,
        idempotency_key: str,
        rating_space_id: str,
        subject_id: str,
        actor_id: str,
        score: int,
        yummy_prior_inputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not idempotency_key:
            raise CommunityValidationError("Idempotency-Key required")
        score = validate_score(score)
        payload = {
            "rating_space_id": rating_space_id,
            "subject_id": subject_id,
            "actor_id": actor_id,
            "score": score,
            "action": "PUT",
        }
        dig = _digest(payload)

        with self.store._lock:
            existing_idem = self.store.conn.execute(
                "SELECT payload_json, event_id FROM community_vote_events WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
            if existing_idem:
                prev = json.loads(existing_idem["payload_json"])
                if prev.get("digest") != dig:
                    raise CommunityConflict("idempotency key reused with different payload")
                return prev.get("response") or {"status": 200, "replay": True}

            self.store.conn.execute("BEGIN IMMEDIATE")
            try:
                agg_row = self.store.get_aggregate(
                    rating_space_id=rating_space_id, subject_id=subject_id
                )
                native = NativeAggregate(int(agg_row["vote_sum"]), int(agg_row["vote_count"]))
                existing = self.store.get_vote(
                    rating_space_id=rating_space_id, subject_id=subject_id, actor_id=actor_id
                )
                before = self._public_value(rating_space_id, native, yummy_prior_inputs)
                now = utc_now_iso()
                noop = False
                if existing and int(existing["score"]) == score:
                    noop = True
                    after_nat = native
                    action = "NOOP"
                elif existing:
                    after_nat = native.after_update(int(existing["score"]), score)
                    action = "UPDATE"
                    self.store.conn.execute(
                        """UPDATE community_votes SET score=?, updated_at=?, policy_version=?,
                           status=?, risk_state='CLEAR', retracted_at=''
                           WHERE rating_space_id=? AND subject_id=? AND actor_id=? AND dimension=?""",
                        (
                            score,
                            now,
                            POLICY_VERSION,
                            STATUS_ACCEPTED,
                            rating_space_id,
                            subject_id,
                            actor_id,
                            DIMENSION_OVERALL,
                        ),
                    )
                else:
                    after_nat = native.after_create(score)
                    action = "CREATE"
                    any_row = self.store.get_vote_row_any_status(
                        rating_space_id=rating_space_id,
                        subject_id=subject_id,
                        actor_id=actor_id,
                    )
                    if any_row:
                        self.store.conn.execute(
                            """UPDATE community_votes SET score=?, status=?, updated_at=?,
                               retracted_at='', policy_version=?, risk_state='CLEAR'
                               WHERE rating_space_id=? AND subject_id=? AND actor_id=? AND dimension=?""",
                            (
                                score,
                                STATUS_ACCEPTED,
                                now,
                                POLICY_VERSION,
                                rating_space_id,
                                subject_id,
                                actor_id,
                                DIMENSION_OVERALL,
                            ),
                        )
                    else:
                        self.store.conn.execute(
                            """INSERT INTO community_votes (
                                rating_space_id, subject_id, actor_id, dimension, score, status,
                                created_at, updated_at, policy_version, risk_state)
                               VALUES (?,?,?,?,?,?,?,?,?,?)""",
                            (
                                rating_space_id,
                                subject_id,
                                actor_id,
                                DIMENSION_OVERALL,
                                score,
                                STATUS_ACCEPTED,
                                now,
                                now,
                                POLICY_VERSION,
                                "CLEAR",
                            ),
                        )
                after_nat.assert_invariants()
                new_version = int(agg_row["aggregate_version"]) + (0 if noop else 1)
                self.store.conn.execute(
                    """INSERT INTO community_aggregates (
                        rating_space_id, subject_id, dimension, vote_sum, vote_count,
                        aggregate_version, policy_version, updated_at)
                       VALUES (?,?,?,?,?,?,?,?)
                       ON CONFLICT(rating_space_id, subject_id, dimension) DO UPDATE SET
                        vote_sum=excluded.vote_sum,
                        vote_count=excluded.vote_count,
                        aggregate_version=excluded.aggregate_version,
                        policy_version=excluded.policy_version,
                        updated_at=excluded.updated_at""",
                    (
                        rating_space_id,
                        subject_id,
                        DIMENSION_OVERALL,
                        after_nat.vote_sum,
                        after_nat.vote_count,
                        new_version,
                        POLICY_VERSION,
                        now,
                    ),
                )
                after = self._public_value(rating_space_id, after_nat, yummy_prior_inputs)
                event_id = f"evt-{uuid.uuid4().hex[:16]}"
                response = {
                    "status": 200,
                    "action": action,
                    "before": None if before is None else str(round_display(before, "0.1")),
                    "after": None if after is None else str(round_display(after, "0.1")),
                    "delta": format_delta(after - before)
                    if before is not None and after is not None
                    else None,
                    "my_vote": score,
                    "native_vote_count": after_nat.vote_count,
                    "aggregate_version": new_version,
                    "policy_version": POLICY_VERSION,
                    "noop": noop,
                }
                self.store.conn.execute(
                    """INSERT INTO community_vote_events (
                        event_id, rating_space_id, subject_id, actor_id, dimension, action,
                        old_score, new_score, status, policy_version, risk_state,
                        idempotency_key, created_at, payload_json)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        event_id,
                        rating_space_id,
                        subject_id,
                        actor_id,
                        DIMENSION_OVERALL,
                        action,
                        None if not existing else int(existing["score"]),
                        score,
                        STATUS_ACCEPTED,
                        POLICY_VERSION,
                        "CLEAR",
                        idempotency_key,
                        now,
                        json.dumps({"digest": dig, "response": response}, ensure_ascii=False),
                    ),
                )
                if not noop:
                    self._outbox(
                        "rating.vote.updated" if action == "UPDATE" else "rating.vote.created",
                        dedupe=f"{event_id}",
                        payload={
                            "event_id": event_id,
                            "subject_id": subject_id,
                            "space": rating_space_id,
                        },
                    )
                    self._outbox(
                        "rating.aggregate.changed",
                        dedupe=f"agg-{rating_space_id}-{subject_id}-{new_version}",
                        payload={
                            "subject_id": subject_id,
                            "space": rating_space_id,
                            "aggregate_version": new_version,
                        },
                    )
                self.store.conn.execute("COMMIT")
                return response
            except Exception:
                self.store.conn.execute("ROLLBACK")
                raise

    def delete_vote(
        self,
        *,
        idempotency_key: str,
        rating_space_id: str,
        subject_id: str,
        actor_id: str,
        yummy_prior_inputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not idempotency_key:
            raise CommunityValidationError("Idempotency-Key required")
        payload = {
            "rating_space_id": rating_space_id,
            "subject_id": subject_id,
            "actor_id": actor_id,
            "action": "DELETE",
        }
        dig = _digest(payload)

        with self.store._lock:
            existing_idem = self.store.conn.execute(
                "SELECT payload_json FROM community_vote_events WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
            if existing_idem:
                prev = json.loads(existing_idem["payload_json"])
                if prev.get("digest") != dig:
                    raise CommunityConflict("idempotency key reused with different payload")
                return prev.get("response") or {"status": 200, "replay": True}

            self.store.conn.execute("BEGIN IMMEDIATE")
            try:
                existing = self.store.get_vote(
                    rating_space_id=rating_space_id, subject_id=subject_id, actor_id=actor_id
                )
                if not existing:
                    self.store.conn.execute("COMMIT")
                    return {"status": 200, "action": "NOOP", "my_vote": None}
                agg_row = self.store.get_aggregate(
                    rating_space_id=rating_space_id, subject_id=subject_id
                )
                native = NativeAggregate(int(agg_row["vote_sum"]), int(agg_row["vote_count"]))
                before = self._public_value(rating_space_id, native, yummy_prior_inputs)
                after_nat = native.after_delete(int(existing["score"]))
                after_nat.assert_invariants()
                now = utc_now_iso()
                self.store.conn.execute(
                    """UPDATE community_votes SET status=?, retracted_at=?, updated_at=?
                       WHERE rating_space_id=? AND subject_id=? AND actor_id=? AND dimension=?""",
                    (
                        STATUS_RETRACTED,
                        now,
                        now,
                        rating_space_id,
                        subject_id,
                        actor_id,
                        DIMENSION_OVERALL,
                    ),
                )
                new_version = int(agg_row["aggregate_version"]) + 1
                self.store.conn.execute(
                    """UPDATE community_aggregates
                       SET vote_sum=?, vote_count=?, aggregate_version=?, updated_at=?
                       WHERE rating_space_id=? AND subject_id=? AND dimension=?""",
                    (
                        after_nat.vote_sum,
                        after_nat.vote_count,
                        new_version,
                        now,
                        rating_space_id,
                        subject_id,
                        DIMENSION_OVERALL,
                    ),
                )
                after = self._public_value(rating_space_id, after_nat, yummy_prior_inputs)
                event_id = f"evt-{uuid.uuid4().hex[:16]}"
                response = {
                    "status": 200,
                    "action": "DELETE",
                    "before": None if before is None else str(round_display(before, "0.1")),
                    "after": None if after is None else str(round_display(after, "0.1")),
                    "my_vote": None,
                    "native_vote_count": after_nat.vote_count,
                    "native_absent": after_nat.vote_count == 0,
                    "aggregate_version": new_version,
                }
                self.store.conn.execute(
                    """INSERT INTO community_vote_events (
                        event_id, rating_space_id, subject_id, actor_id, dimension, action,
                        old_score, new_score, status, policy_version, risk_state,
                        idempotency_key, created_at, payload_json)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        event_id,
                        rating_space_id,
                        subject_id,
                        actor_id,
                        DIMENSION_OVERALL,
                        "DELETE",
                        int(existing["score"]),
                        None,
                        STATUS_RETRACTED,
                        POLICY_VERSION,
                        "CLEAR",
                        idempotency_key,
                        now,
                        json.dumps({"digest": dig, "response": response}, ensure_ascii=False),
                    ),
                )
                self._outbox(
                    "rating.vote.retracted",
                    dedupe=event_id,
                    payload={"event_id": event_id, "subject_id": subject_id},
                )
                self.store.conn.execute("COMMIT")
                return response
            except Exception:
                self.store.conn.execute("ROLLBACK")
                raise

    def _public_value(
        self,
        rating_space_id: str,
        native: NativeAggregate,
        yummy_prior_inputs: dict[str, Any] | None,
    ) -> Decimal | None:
        if rating_space_id != "yummy":
            return native.average
        inp = yummy_prior_inputs or {}
        # Stage06 PUBLIC_SCORE_MODE=NATIVE_ONLY: empty/absent prior inputs → native mean.
        # Shadow Bayesian prior remains available only when explicit components are passed.
        if not inp or (
            inp.get("animedia_native") is None
            and inp.get("shikimori") is None
            and not inp.get("force_bayes")
        ):
            return native.average
        prior, _ = build_yummy_prior(
            animedia_native=_dec(inp.get("animedia_native")),
            shikimori=_dec(inp.get("shikimori")),
            animedia_embeds_shikimori=bool(inp.get("animedia_embeds_shikimori")),
        )
        return YummyPublic(
            native.vote_sum,
            native.vote_count,
            prior,
            m=int(inp.get("m") or DEFAULT_PRIOR_STRENGTH_M),
        ).public_score

    def _outbox(self, event_type: str, *, dedupe: str, payload: dict[str, Any]) -> None:
        self.store.conn.execute(
            """INSERT OR IGNORE INTO community_outbox (
                outbox_id, event_type, dedupe_key, payload_json, created_at)
               VALUES (?,?,?,?,?)""",
            (
                f"obx-{uuid.uuid4().hex[:12]}",
                event_type,
                dedupe,
                json.dumps(payload, ensure_ascii=False),
                utc_now_iso(),
            ),
        )


def _dec(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    return Decimal(str(value))
