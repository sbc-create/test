"""Изолированное SQLite-хранилище ratings. Production DB не трогаем."""

from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path
from typing import Any

from factory.paths import PATHS
from factory.ratings.models import (
    FreshnessState,
    HealthState,
    MappingState,
    QueueItemState,
    RatingCurrent,
    RatingObservation,
    SourceRecord,
    SourceState,
    TitleSourceMapping,
    ValidationState,
    utc_now_iso,
)


def _load_migration_0002():
    path = PATHS.root / "migrations" / "0002_ratings_ingestion.py"
    spec = importlib.util.spec_from_file_location("ratings_migration_0002", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"не удалось загрузить миграцию {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


class RatingsStore:
    """Единственный владелец записи рейтингов в изолированной SQLite."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.conn = _connect(self.path)
        self.ensure_schema()

    def ensure_schema(self) -> None:
        mig = _load_migration_0002()
        if not mig.applied(self.conn):
            mig.upgrade(self.conn)

    def close(self) -> None:
        self.conn.close()

    # ---- sources ---------------------------------------------------------
    def upsert_source(self, source: SourceRecord) -> None:
        self.conn.execute(
            """INSERT INTO rating_sources (
                source_key, display_name, canonical_origin, adapter_version,
                state, enabled, score_scale, supports_vote_count,
                supports_distribution, max_rps, max_requests_per_minute,
                freshness_policy_json, legal_access_evidence, attribution_gate,
                last_schema_check, last_successful_fetch, health_state)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(source_key) DO UPDATE SET
                display_name=excluded.display_name,
                canonical_origin=excluded.canonical_origin,
                adapter_version=excluded.adapter_version,
                state=excluded.state,
                enabled=excluded.enabled,
                score_scale=excluded.score_scale,
                supports_vote_count=excluded.supports_vote_count,
                supports_distribution=excluded.supports_distribution,
                max_rps=excluded.max_rps,
                max_requests_per_minute=excluded.max_requests_per_minute,
                freshness_policy_json=excluded.freshness_policy_json,
                legal_access_evidence=excluded.legal_access_evidence,
                attribution_gate=excluded.attribution_gate,
                last_schema_check=excluded.last_schema_check,
                last_successful_fetch=excluded.last_successful_fetch,
                health_state=excluded.health_state""",
            (
                source.source_key,
                source.display_name,
                source.canonical_origin,
                source.adapter_version,
                source.state.value,
                1 if source.enabled else 0,
                source.score_scale,
                1 if source.supports_vote_count else 0,
                1 if source.supports_distribution else 0,
                source.max_rps,
                source.max_requests_per_minute,
                json.dumps(source.freshness_policy, ensure_ascii=False),
                source.legal_access_evidence,
                source.attribution_gate,
                source.last_schema_check,
                source.last_successful_fetch,
                source.health_state.value,
            ),
        )

    def list_sources(self) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM rating_sources ORDER BY source_key").fetchall()
        return [dict(r) for r in rows]

    def get_source(self, source_key: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM rating_sources WHERE source_key = ?", (source_key,)
        ).fetchone()
        return dict(row) if row else None

    def touch_source_success(self, source_key: str, *, schema_check: str = "") -> None:
        now = utc_now_iso()
        if schema_check:
            self.conn.execute(
                """UPDATE rating_sources SET last_successful_fetch=?, last_schema_check=?,
                   health_state=? WHERE source_key=?""",
                (now, schema_check, HealthState.HEALTHY.value, source_key),
            )
        else:
            self.conn.execute(
                """UPDATE rating_sources SET last_successful_fetch=?, health_state=?
                   WHERE source_key=?""",
                (now, HealthState.HEALTHY.value, source_key),
            )

    def set_source_health(self, source_key: str, health: HealthState, state: SourceState | None = None) -> None:
        if state is not None:
            self.conn.execute(
                "UPDATE rating_sources SET health_state=?, state=? WHERE source_key=?",
                (health.value, state.value, source_key),
            )
        else:
            self.conn.execute(
                "UPDATE rating_sources SET health_state=? WHERE source_key=?",
                (health.value, source_key),
            )

    # ---- mappings --------------------------------------------------------
    def upsert_mapping(self, mapping: TitleSourceMapping) -> None:
        self.conn.execute(
            """INSERT INTO title_source_mappings (
                canonical_title_id, source_key, external_title_id, external_url,
                mapping_method, confidence, evidence, verified_at, state)
               VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT(canonical_title_id, source_key) DO UPDATE SET
                external_title_id=excluded.external_title_id,
                external_url=excluded.external_url,
                mapping_method=excluded.mapping_method,
                confidence=excluded.confidence,
                evidence=excluded.evidence,
                verified_at=excluded.verified_at,
                state=excluded.state""",
            (
                mapping.canonical_title_id,
                mapping.source_key,
                mapping.external_title_id,
                mapping.external_url,
                mapping.mapping_method.value,
                mapping.confidence,
                mapping.evidence,
                mapping.verified_at,
                mapping.state.value,
            ),
        )

    def get_mapping(self, canonical_title_id: str, source_key: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            """SELECT * FROM title_source_mappings
               WHERE canonical_title_id=? AND source_key=?""",
            (canonical_title_id, source_key),
        ).fetchone()
        return dict(row) if row else None

    def verified_mappings(self, source_key: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """SELECT * FROM title_source_mappings
               WHERE source_key=? AND state=?""",
            (source_key, MappingState.VERIFIED.value),
        ).fetchall()
        return [dict(r) for r in rows]

    # ---- observations (append-only) --------------------------------------
    def insert_observation(self, obs: RatingObservation) -> int | None:
        """Insert observation. Returns id, or None if idempotency_key exists."""
        try:
            cur = self.conn.execute(
                """INSERT INTO rating_observations (
                    canonical_title_id, source_key, external_id, raw_score,
                    source_scale, normalized_score, vote_count, score_distribution,
                    source_updated_at, observed_at, payload_sha256, adapter_version,
                    provenance_url, mapping_method, validation_state, run_id,
                    idempotency_key)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    obs.canonical_title_id,
                    obs.source_key,
                    obs.external_id,
                    obs.raw_score,
                    obs.source_scale,
                    obs.normalized_score,
                    obs.vote_count,
                    json.dumps(obs.score_distribution) if obs.score_distribution else None,
                    obs.source_updated_at,
                    obs.observed_at,
                    obs.payload_sha256,
                    obs.adapter_version,
                    obs.provenance_url,
                    obs.mapping_method.value,
                    obs.validation_state.value,
                    obs.run_id,
                    obs.idempotency_key,
                ),
            )
            return int(cur.lastrowid)
        except sqlite3.IntegrityError:
            return None

    def latest_valid_observation(
        self, canonical_title_id: str, source_key: str
    ) -> dict[str, Any] | None:
        row = self.conn.execute(
            """SELECT * FROM rating_observations
               WHERE canonical_title_id=? AND source_key=? AND validation_state=?
               ORDER BY observed_at DESC, id DESC LIMIT 1""",
            (canonical_title_id, source_key, ValidationState.VALID.value),
        ).fetchone()
        return dict(row) if row else None

    def observation_count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) AS c FROM rating_observations").fetchone()
        return int(row["c"])

    # ---- current projection ----------------------------------------------
    def upsert_current(self, current: RatingCurrent) -> None:
        self.conn.execute(
            """INSERT INTO rating_current (
                canonical_title_id, source_key, observation_id, raw_score,
                normalized_score, vote_count, freshness, observed_at,
                provenance_url, payload_sha256, adapter_version, external_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(canonical_title_id, source_key) DO UPDATE SET
                observation_id=excluded.observation_id,
                raw_score=excluded.raw_score,
                normalized_score=excluded.normalized_score,
                vote_count=excluded.vote_count,
                freshness=excluded.freshness,
                observed_at=excluded.observed_at,
                provenance_url=excluded.provenance_url,
                payload_sha256=excluded.payload_sha256,
                adapter_version=excluded.adapter_version,
                external_id=excluded.external_id""",
            (
                current.canonical_title_id,
                current.source_key,
                current.observation_id,
                current.raw_score,
                current.normalized_score,
                current.vote_count,
                current.freshness.value,
                current.observed_at,
                current.provenance_url,
                current.payload_sha256,
                current.adapter_version,
                current.external_id,
            ),
        )

    def get_current(self, canonical_title_id: str, source_key: str | None = None) -> list[dict[str, Any]]:
        if source_key:
            row = self.conn.execute(
                "SELECT * FROM rating_current WHERE canonical_title_id=? AND source_key=?",
                (canonical_title_id, source_key),
            ).fetchone()
            return [dict(row)] if row else []
        rows = self.conn.execute(
            "SELECT * FROM rating_current WHERE canonical_title_id=?",
            (canonical_title_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def all_current(self) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM rating_current").fetchall()
        return [dict(r) for r in rows]

    def coverage_stats(self, source_key: str | None = None) -> dict[str, Any]:
        if source_key:
            total = self.conn.execute(
                "SELECT COUNT(*) AS c FROM rating_current WHERE source_key=?",
                (source_key,),
            ).fetchone()["c"]
            with_score = self.conn.execute(
                """SELECT COUNT(*) AS c FROM rating_current
                   WHERE source_key=? AND normalized_score IS NOT NULL
                     AND freshness NOT IN (?, ?, ?)""",
                (
                    source_key,
                    FreshnessState.MISSING.value,
                    FreshnessState.EXPIRED.value,
                    FreshnessState.CONFLICT.value,
                ),
            ).fetchone()["c"]
        else:
            total = self.conn.execute("SELECT COUNT(*) AS c FROM rating_current").fetchone()["c"]
            with_score = self.conn.execute(
                """SELECT COUNT(*) AS c FROM rating_current
                   WHERE normalized_score IS NOT NULL
                     AND freshness NOT IN (?, ?, ?)""",
                (
                    FreshnessState.MISSING.value,
                    FreshnessState.EXPIRED.value,
                    FreshnessState.CONFLICT.value,
                ),
            ).fetchone()["c"]
        return {"total": int(total), "with_score": int(with_score)}

    # ---- queue -----------------------------------------------------------
    def enqueue(
        self,
        *,
        canonical_title_id: str,
        source_key: str,
        priority: int,
        priority_label: str,
        available_at: str = "",
    ) -> bool:
        """Enqueue or bump priority if higher. Returns True if inserted/updated."""
        now = utc_now_iso()
        existing = self.conn.execute(
            """SELECT priority, state FROM rating_backfill_queue
               WHERE canonical_title_id=? AND source_key=?""",
            (canonical_title_id, source_key),
        ).fetchone()
        if existing is None:
            self.conn.execute(
                """INSERT INTO rating_backfill_queue (
                    canonical_title_id, source_key, priority, priority_label,
                    state, enqueued_at, available_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    canonical_title_id,
                    source_key,
                    priority,
                    priority_label,
                    QueueItemState.PENDING.value,
                    now,
                    available_at or now,
                ),
            )
            return True
        if existing["state"] in (
            QueueItemState.DONE.value,
            QueueItemState.DEAD_LETTER.value,
        ):
            self.conn.execute(
                """UPDATE rating_backfill_queue SET priority=?, priority_label=?,
                   state=?, enqueued_at=?, available_at=?, attempts=0, last_error='',
                   claimed_by='', claim_lease_until=''
                   WHERE canonical_title_id=? AND source_key=?""",
                (
                    priority,
                    priority_label,
                    QueueItemState.PENDING.value,
                    now,
                    available_at or now,
                    canonical_title_id,
                    source_key,
                ),
            )
            return True
        if priority < int(existing["priority"]):
            self.conn.execute(
                """UPDATE rating_backfill_queue SET priority=?, priority_label=?
                   WHERE canonical_title_id=? AND source_key=?""",
                (priority, priority_label, canonical_title_id, source_key),
            )
            return True
        return False

    def claim_batch(
        self,
        *,
        source_key: str,
        worker_id: str,
        limit: int,
        lease_seconds: int,
        now_iso: str | None = None,
    ) -> list[dict[str, Any]]:
        """Atomic claim of pending items with lease."""
        now = now_iso or utc_now_iso()
        # Release expired leases first.
        self.conn.execute(
            """UPDATE rating_backfill_queue SET state=?, claimed_by='', claim_lease_until=''
               WHERE source_key=? AND state=? AND claim_lease_until <> '' AND claim_lease_until < ?""",
            (QueueItemState.PENDING.value, source_key, QueueItemState.CLAIMED.value, now),
        )
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            rows = self.conn.execute(
                """SELECT * FROM rating_backfill_queue
                   WHERE source_key=? AND state=? AND (available_at='' OR available_at<=?)
                   ORDER BY priority ASC, enqueued_at ASC
                   LIMIT ?""",
                (source_key, QueueItemState.PENDING.value, now, limit),
            ).fetchall()
            claimed: list[dict[str, Any]] = []
            from datetime import datetime, timedelta, timezone

            lease_until = (
                datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
            for row in rows:
                self.conn.execute(
                    """UPDATE rating_backfill_queue
                       SET state=?, claimed_by=?, claim_lease_until=?, attempts=attempts+1
                       WHERE id=? AND state=?""",
                    (
                        QueueItemState.CLAIMED.value,
                        worker_id,
                        lease_until,
                        row["id"],
                        QueueItemState.PENDING.value,
                    ),
                )
                if self.conn.execute(
                    "SELECT changes()"
                ).fetchone()[0]:
                    claimed.append(dict(row))
            self.conn.execute("COMMIT")
            return claimed
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def heartbeat(self, item_id: int, worker_id: str, lease_seconds: int) -> bool:
        from datetime import datetime, timedelta, timezone

        lease_until = (
            datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        cur = self.conn.execute(
            """UPDATE rating_backfill_queue SET claim_lease_until=?
               WHERE id=? AND claimed_by=? AND state=?""",
            (lease_until, item_id, worker_id, QueueItemState.CLAIMED.value),
        )
        return cur.rowcount > 0

    def complete_item(self, item_id: int, state: QueueItemState, error: str = "") -> None:
        self.conn.execute(
            """UPDATE rating_backfill_queue
               SET state=?, last_error=?, claimed_by='', claim_lease_until=''
               WHERE id=?""",
            (state.value, error, item_id),
        )

    def queue_size(self, source_key: str, state: str | None = None) -> int:
        if state:
            row = self.conn.execute(
                "SELECT COUNT(*) AS c FROM rating_backfill_queue WHERE source_key=? AND state=?",
                (source_key, state),
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT COUNT(*) AS c FROM rating_backfill_queue WHERE source_key=?",
                (source_key,),
            ).fetchone()
        return int(row["c"])

    def queue_priority_breakdown(self, source_key: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """SELECT priority, priority_label, COUNT(*) AS c
               FROM rating_backfill_queue
               WHERE source_key=? AND state IN (?, ?)
               GROUP BY priority, priority_label
               ORDER BY priority ASC""",
            (
                source_key,
                QueueItemState.PENDING.value,
                QueueItemState.CLAIMED.value,
            ),
        ).fetchall()
        return [dict(r) for r in rows]

    # ---- runs / idempotency ----------------------------------------------
    def create_run(
        self,
        *,
        run_id: str,
        source_key: str,
        idempotency_key: str,
        dry_run: bool,
        candidate_cap: int,
        success_target: int,
    ) -> bool:
        """Create run. Returns False if idempotency_key already exists."""
        try:
            self.conn.execute(
                """INSERT INTO rating_ingestion_runs (
                    run_id, source_key, started_at, status, dry_run,
                    idempotency_key, candidate_cap, success_target)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    run_id,
                    source_key,
                    utc_now_iso(),
                    "RUNNING",
                    1 if dry_run else 0,
                    idempotency_key,
                    candidate_cap,
                    success_target,
                ),
            )
            return True
        except sqlite3.IntegrityError:
            return False

    def get_run_by_idempotency(self, idempotency_key: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM rating_ingestion_runs WHERE idempotency_key=?",
            (idempotency_key,),
        ).fetchone()
        return dict(row) if row else None

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM rating_ingestion_runs WHERE run_id=?", (run_id,)
        ).fetchone()
        return dict(row) if row else None

    def save_checkpoint(self, run_id: str, checkpoint: dict[str, Any]) -> None:
        self.conn.execute(
            "UPDATE rating_ingestion_runs SET checkpoint_json=? WHERE run_id=?",
            (json.dumps(checkpoint, ensure_ascii=False), run_id),
        )

    def finish_run(self, run_id: str, status: str, metrics: dict[str, Any]) -> None:
        self.conn.execute(
            """UPDATE rating_ingestion_runs
               SET finished_at=?, status=?, metrics_json=? WHERE run_id=?""",
            (utc_now_iso(), status, json.dumps(metrics, ensure_ascii=False), run_id),
        )

    # ---- conflicts / review / DLQ ----------------------------------------
    def add_conflict(
        self,
        *,
        canonical_title_id: str,
        source_key: str,
        reason: str,
        evidence: dict[str, Any],
    ) -> None:
        self.conn.execute(
            """INSERT INTO rating_conflicts (
                canonical_title_id, source_key, reason, evidence_json, created_at)
               VALUES (?,?,?,?,?)""",
            (
                canonical_title_id,
                source_key,
                reason,
                json.dumps(evidence, ensure_ascii=False),
                utc_now_iso(),
            ),
        )

    def list_conflicts(self, state: str = "OPEN") -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM rating_conflicts WHERE state=? ORDER BY id DESC", (state,)
        ).fetchall()
        return [dict(r) for r in rows]

    def add_review(
        self,
        *,
        canonical_title_id: str,
        source_key: str,
        candidates: list[dict[str, Any]],
        reason: str,
    ) -> None:
        self.conn.execute(
            """INSERT INTO rating_review_queue (
                canonical_title_id, source_key, candidates_json, reason, created_at)
               VALUES (?,?,?,?,?)""",
            (
                canonical_title_id,
                source_key,
                json.dumps(candidates, ensure_ascii=False),
                reason,
                utc_now_iso(),
            ),
        )

    def add_dead_letter(
        self,
        *,
        canonical_title_id: str,
        source_key: str,
        run_id: str,
        error: str,
        payload: dict[str, Any],
    ) -> None:
        self.conn.execute(
            """INSERT INTO rating_dead_letter (
                canonical_title_id, source_key, run_id, error, payload_json, created_at)
               VALUES (?,?,?,?,?,?)""",
            (
                canonical_title_id,
                source_key,
                run_id,
                error,
                json.dumps(payload, ensure_ascii=False),
                utc_now_iso(),
            ),
        )

    def set_cursor(self, source_key: str, cursor: dict[str, Any]) -> None:
        self.conn.execute(
            """INSERT INTO rating_backfill_cursor (source_key, cursor_json, updated_at)
               VALUES (?,?,?)
               ON CONFLICT(source_key) DO UPDATE SET
                cursor_json=excluded.cursor_json, updated_at=excluded.updated_at""",
            (source_key, json.dumps(cursor, ensure_ascii=False), utc_now_iso()),
        )

    def get_cursor(self, source_key: str) -> dict[str, Any]:
        row = self.conn.execute(
            "SELECT cursor_json FROM rating_backfill_cursor WHERE source_key=?",
            (source_key,),
        ).fetchone()
        if not row:
            return {}
        return json.loads(row["cursor_json"] or "{}")
