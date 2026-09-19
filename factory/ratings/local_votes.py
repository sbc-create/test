"""Local user votes: one user — one current vote; append-only events; Decimal aggregates."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass
from typing import Any

from factory.ratings.formula import FORMULA_VERSION, combine_amd_local
from factory.ratings.models import utc_now_iso

SCOPE_NETWORK = "NETWORK"
SCOPE_SITE_ANONYMOUS = "SITE_ANONYMOUS"

STATE_ACCEPTED = "ACCEPTED"
STATE_QUARANTINED = "QUARANTINED"
STATE_REJECTED = "REJECTED"
STATE_REVOKED = "REVOKED"

ACTION_CREATE = "CREATE"
ACTION_UPDATE = "UPDATE"
ACTION_DELETE = "DELETE"
ACTION_REVOKE = "REVOKE"
ACTION_MODERATION = "MODERATION"


class VoteConflict(Exception):
    """HTTP 409 — same idempotency key, different payload."""

    status = 409


class VoteValidationError(ValueError):
    status = 400


@dataclass
class VoteResult:
    status: int
    body: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {"status": self.status, **self.body}


def _payload_digest(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def _aggregate_digest(count: int, total: int) -> str:
    return hashlib.sha256(f"{count}:{total}".encode()).hexdigest()


def validate_score(score: int | None) -> int | None:
    if score is None:
        return None
    if isinstance(score, bool) or not isinstance(score, int):
        raise VoteValidationError("score must be integer 1..10")
    if score < 1 or score > 10:
        raise VoteValidationError("score must be integer 1..10; 0 forbidden")
    return score


class LocalVotesService:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def apply(
        self,
        *,
        idempotency_key: str,
        canonical_title_id: str,
        voter_subject_id: str,
        scope: str,
        site_id: str = "",
        action: str,
        new_score: int | None = None,
        moderation_status: str = STATE_ACCEPTED,
        reason: str = "",
        request_id: str = "",
        quarantine: bool = False,
    ) -> VoteResult:
        if not idempotency_key:
            raise VoteValidationError("Idempotency-Key required")
        if action in (ACTION_CREATE, ACTION_UPDATE):
            new_score = validate_score(new_score)
        elif action in (ACTION_DELETE, ACTION_REVOKE):
            new_score = None
        else:
            if new_score is not None:
                new_score = validate_score(new_score)

        if quarantine:
            moderation_status = STATE_QUARANTINED

        payload = {
            "canonical_title_id": canonical_title_id,
            "voter_subject_id": voter_subject_id,
            "scope": scope,
            "site_id": site_id,
            "action": action,
            "new_score": new_score,
            "moderation_status": moderation_status,
        }
        digest = _payload_digest(payload)

        existing = self.conn.execute(
            "SELECT payload_digest, response_json FROM rating_idempotency WHERE idempotency_key=?",
            (idempotency_key,),
        ).fetchone()
        if existing:
            if existing["payload_digest"] != digest:
                raise VoteConflict("idempotency key reused with different payload")
            body = json.loads(existing["response_json"])
            return VoteResult(status=200, body=body)

        self.conn.execute("BEGIN IMMEDIATE")
        try:
            row = self.conn.execute(
                """SELECT * FROM rating_vote_current
                   WHERE canonical_title_id=? AND voter_subject_id=? AND scope=? AND site_id=?""",
                (canonical_title_id, voter_subject_id, scope, site_id),
            ).fetchone()
            old_score = int(row["score"]) if row and row["state"] == STATE_ACCEPTED else None
            old_state = row["state"] if row else None

            event_id = f"evt-{uuid.uuid4().hex[:16]}"
            now = utc_now_iso()

            if action in (ACTION_CREATE, ACTION_UPDATE):
                assert new_score is not None
                state = moderation_status if moderation_status in (
                    STATE_ACCEPTED, STATE_QUARANTINED, STATE_REJECTED
                ) else STATE_ACCEPTED
                if quarantine:
                    state = STATE_QUARANTINED
                if row is None:
                    actual_action = ACTION_CREATE
                    self.conn.execute(
                        """INSERT INTO rating_vote_current (
                            canonical_title_id, voter_subject_id, scope, site_id,
                            score, state, created_at, updated_at)
                           VALUES (?,?,?,?,?,?,?,?)""",
                        (
                            canonical_title_id, voter_subject_id, scope, site_id,
                            new_score, state, now, now,
                        ),
                    )
                else:
                    actual_action = ACTION_UPDATE
                    self.conn.execute(
                        """UPDATE rating_vote_current
                           SET score=?, state=?, updated_at=?
                           WHERE canonical_title_id=? AND voter_subject_id=? AND scope=? AND site_id=?""",
                        (
                            new_score, state, now,
                            canonical_title_id, voter_subject_id, scope, site_id,
                        ),
                    )
            elif action in (ACTION_DELETE, ACTION_REVOKE):
                actual_action = ACTION_REVOKE
                if row is None:
                    body = {"action": actual_action, "noop": True, "local_vote_count": self._count(canonical_title_id, scope, site_id)}
                    self._store_idem(idempotency_key, digest, body)
                    self.conn.execute("COMMIT")
                    return VoteResult(status=200, body=body)
                self.conn.execute(
                    """UPDATE rating_vote_current SET state=?, updated_at=?
                       WHERE canonical_title_id=? AND voter_subject_id=? AND scope=? AND site_id=?""",
                    (STATE_REVOKED, now, canonical_title_id, voter_subject_id, scope, site_id),
                )
            else:
                raise VoteValidationError(f"unknown action {action}")

            self.conn.execute(
                """INSERT INTO rating_vote_event (
                    event_id, request_id, idempotency_key, canonical_title_id,
                    voter_subject_id, scope, site_id, action, old_score, new_score,
                    moderation_status, reason, created_at, formula_version, payload_digest)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    event_id, request_id, idempotency_key, canonical_title_id,
                    voter_subject_id, scope, site_id, actual_action, old_score, new_score,
                    moderation_status if action not in (ACTION_DELETE, ACTION_REVOKE) else STATE_REVOKED,
                    reason, now, FORMULA_VERSION, digest,
                ),
            )

            agg = self.rebuild_aggregate(canonical_title_id, scope, site_id)
            body = {
                "event_id": event_id,
                "action": actual_action,
                "old_score": old_score,
                "new_score": new_score,
                "state": moderation_status if action not in (ACTION_DELETE, ACTION_REVOKE) else STATE_REVOKED,
                "aggregate": agg,
                "previous_state": old_state,
            }
            self._store_idem(idempotency_key, digest, body)
            self.conn.execute("COMMIT")
            return VoteResult(status=200, body=body)
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def _store_idem(self, key: str, digest: str, body: dict) -> None:
        self.conn.execute(
            """INSERT INTO rating_idempotency (idempotency_key, payload_digest, response_json, created_at)
               VALUES (?,?,?,?)""",
            (key, digest, json.dumps(body, ensure_ascii=False), utc_now_iso()),
        )

    def _count(self, canonical_title_id: str, scope: str, site_id: str) -> int:
        row = self.conn.execute(
            """SELECT accepted_vote_count FROM rating_local_aggregate
               WHERE canonical_title_id=? AND scope=? AND site_id=?""",
            (canonical_title_id, scope, site_id),
        ).fetchone()
        return int(row["accepted_vote_count"]) if row else 0

    def rebuild_aggregate(self, canonical_title_id: str, scope: str, site_id: str = "") -> dict[str, Any]:
        rows = self.conn.execute(
            """SELECT score FROM rating_vote_current
               WHERE canonical_title_id=? AND scope=? AND site_id=? AND state=?""",
            (canonical_title_id, scope, site_id, STATE_ACCEPTED),
        ).fetchall()
        count = len(rows)
        total = sum(int(r["score"]) for r in rows)
        avg = None if count == 0 else f"{(total / count):.10f}".rstrip("0").rstrip(".")
        digest = _aggregate_digest(count, total)
        now = utc_now_iso()
        self.conn.execute(
            """INSERT INTO rating_local_aggregate (
                canonical_title_id, scope, site_id, accepted_vote_count,
                accepted_vote_sum, average_score, updated_at, digest)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(canonical_title_id, scope, site_id) DO UPDATE SET
                accepted_vote_count=excluded.accepted_vote_count,
                accepted_vote_sum=excluded.accepted_vote_sum,
                average_score=excluded.average_score,
                updated_at=excluded.updated_at,
                digest=excluded.digest""",
            (canonical_title_id, scope, site_id, count, total, avg, now, digest),
        )
        # verify invariant
        rebuilt = _aggregate_digest(count, total)
        assert rebuilt == digest
        return {
            "accepted_vote_count": count,
            "accepted_vote_sum": total,
            "average_score": avg,
            "digest": digest,
        }

    def get_aggregate(self, canonical_title_id: str, scope: str = SCOPE_NETWORK, site_id: str = "") -> dict[str, Any] | None:
        row = self.conn.execute(
            """SELECT * FROM rating_local_aggregate
               WHERE canonical_title_id=? AND scope=? AND site_id=?""",
            (canonical_title_id, scope, site_id),
        ).fetchone()
        return dict(row) if row else None


def upsert_combined(
    conn: sqlite3.Connection,
    *,
    canonical_title_id: str,
    amd_score,
    amd_vote_count: int | None,
    scope: str = SCOPE_NETWORK,
    site_id: str = "",
    rotation_algorithm: str = "animedia_rotation_v1",
) -> dict[str, Any]:
    from decimal import Decimal

    agg = conn.execute(
        """SELECT * FROM rating_local_aggregate
           WHERE canonical_title_id=? AND scope=? AND site_id=?""",
        (canonical_title_id, scope, site_id),
    ).fetchone()
    local_count = int(agg["accepted_vote_count"]) if agg else 0
    local_sum = int(agg["accepted_vote_sum"]) if agg else 0
    result = combine_amd_local(
        amd_score=None if amd_score is None else Decimal(str(amd_score)),
        amd_vote_count=amd_vote_count,
        accepted_local_vote_sum=local_sum,
        accepted_local_vote_count=local_count,
    )
    now = utc_now_iso()
    conn.execute(
        """INSERT INTO rating_combined_projection (
            canonical_title_id, scope, site_id, amd_score, amd_vote_count,
            baseline_weight, local_vote_count, local_vote_sum, combined_raw,
            combined_ui, state, formula_version, quality_flags, rotation_score,
            rotation_algorithm, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(canonical_title_id, scope, site_id) DO UPDATE SET
            amd_score=excluded.amd_score,
            amd_vote_count=excluded.amd_vote_count,
            baseline_weight=excluded.baseline_weight,
            local_vote_count=excluded.local_vote_count,
            local_vote_sum=excluded.local_vote_sum,
            combined_raw=excluded.combined_raw,
            combined_ui=excluded.combined_ui,
            state=excluded.state,
            formula_version=excluded.formula_version,
            quality_flags=excluded.quality_flags,
            rotation_score=excluded.rotation_score,
            rotation_algorithm=excluded.rotation_algorithm,
            updated_at=excluded.updated_at""",
        (
            canonical_title_id, scope, site_id,
            result.as_dict()["amd_score"], amd_vote_count,
            result.baseline_weight, result.local_vote_count, result.local_vote_sum,
            result.as_dict()["combined_raw"], result.combined_ui, result.state,
            result.formula_version, json.dumps(list(result.quality_flags)),
            result.as_dict()["combined_raw"], rotation_algorithm, now,
        ),
    )
    return result.as_dict()
