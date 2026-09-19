"""Ingestion pipeline: claim → fetch → observe → project. Default dry-run."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from factory.ratings.adapters.base import AdapterError, FetchResult, SourceAdapter
from factory.ratings.circuit_breaker import CircuitBreaker
from factory.ratings.config import RatingsConfig
from factory.ratings.locks import RatingsLockBusy, ratings_lock
from factory.ratings.models import (
    MappingMethod,
    QueueItemState,
    RatingObservation,
    ValidationState,
    payload_sha256,
    utc_now_iso,
)
from factory.ratings.projection import apply_observation
from factory.ratings.store import RatingsStore


def _idempotency_key(run_id: str, canonical_title_id: str, source_key: str, payload_hash: str) -> str:
    raw = f"{run_id}|{canonical_title_id}|{source_key}|{payload_hash}"
    return hashlib.sha256(raw.encode()).hexdigest()


@dataclass
class RunMetrics:
    source: str = ""
    run_id: str = ""
    started_at: str = ""
    finished_at: str = ""
    duration_sec: float = 0.0
    dry_run: bool = True
    queue_size: int = 0
    planned_candidates: int = 0
    attempted: int = 0
    fetched: int = 0
    matched: int = 0
    inserted: int = 0
    unchanged: int = 0
    refreshed: int = 0
    not_found: int = 0
    conflicts: int = 0
    review_queued: int = 0
    retried: int = 0
    rate_limited: int = 0
    failed: int = 0
    dead_letter: int = 0
    request_count: int = 0
    daily_limit_usage: dict[str, Any] = field(default_factory=dict)
    wrong_automatic_mappings: int = 0
    ambiguous_auto_published: int = 0
    last_good_preserved: int = 0
    checkpoint: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


class IngestionEngine:
    def __init__(
        self,
        store: RatingsStore,
        adapter: SourceAdapter,
        config: RatingsConfig,
        *,
        breaker: CircuitBreaker | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.store = store
        self.adapter = adapter
        self.config = config
        self.breaker = breaker or CircuitBreaker(
            threshold=config.circuit_breaker_threshold,
            cooldown_sec=config.circuit_breaker_cooldown_sec,
        )
        self.clock = clock or (lambda: datetime.now(timezone.utc).timestamp())

    def ingest(
        self,
        *,
        source_key: str,
        limit: int,
        dry_run: bool = True,
        apply: bool = False,
        run_id: str | None = None,
        idempotency_key: str | None = None,
        resume: bool = False,
        use_lock: bool = True,
    ) -> RunMetrics:
        """Ingest up to ``limit`` claimed items. Mutations require apply=True."""
        if apply and dry_run:
            dry_run = False
        if not apply:
            dry_run = True

        run_id = run_id or f"run-{uuid.uuid4().hex[:12]}"
        idem = idempotency_key or f"{source_key}:{run_id}"
        metrics = RunMetrics(
            source=source_key,
            run_id=run_id,
            started_at=utc_now_iso(),
            dry_run=dry_run,
            planned_candidates=limit,
        )

        def _body() -> RunMetrics:
            return self._run_body(
                metrics=metrics,
                source_key=source_key,
                limit=limit,
                dry_run=dry_run,
                run_id=run_id,
                idem=idem,
                resume=resume,
            )

        if use_lock:
            try:
                with ratings_lock(self.config.lock_name, timeout=0.0):
                    return _body()
            except RatingsLockBusy as exc:
                metrics.failed += 1
                metrics.finished_at = utc_now_iso()
                metrics.checkpoint = {"error": "lock_busy", "holder": exc.holder}
                return metrics
        return _body()

    def _run_body(
        self,
        *,
        metrics: RunMetrics,
        source_key: str,
        limit: int,
        dry_run: bool,
        run_id: str,
        idem: str,
        resume: bool,
    ) -> RunMetrics:
        existing = self.store.get_run_by_idempotency(idem)
        if existing and not resume:
            # Idempotent rerun: return prior metrics, no duplicate observations.
            prior = json.loads(existing.get("metrics_json") or "{}")
            metrics.finished_at = existing.get("finished_at") or utc_now_iso()
            for k, v in prior.items():
                if hasattr(metrics, k):
                    setattr(metrics, k, v)
            metrics.checkpoint = {"idempotent_replay": True, "prior_run": existing["run_id"]}
            return metrics

        if existing and resume:
            run_id = existing["run_id"]
            metrics.run_id = run_id
            checkpoint = json.loads(existing.get("checkpoint_json") or "{}")
            metrics.checkpoint = checkpoint
        else:
            created = self.store.create_run(
                run_id=run_id,
                source_key=source_key,
                idempotency_key=idem,
                dry_run=dry_run,
                candidate_cap=self.config.daily_candidate_cap,
                success_target=self.config.daily_success_target,
            )
            if not created and not resume:
                prior = self.store.get_run_by_idempotency(idem)
                metrics.checkpoint = {"idempotent_replay": True, "prior_run": (prior or {}).get("run_id")}
                return metrics

        if self.breaker.is_open():
            metrics.failed += 1
            metrics.finished_at = utc_now_iso()
            self.store.finish_run(run_id, "CIRCUIT_OPEN", metrics.as_dict())
            return metrics

        metrics.queue_size = self.store.queue_size(source_key)
        worker_id = f"worker-{run_id}"
        claimed = self.store.claim_batch(
            source_key=source_key,
            worker_id=worker_id,
            limit=limit,
            lease_seconds=self.config.lease_seconds,
        )

        # Group by external id via mapping
        to_fetch: list[tuple[dict, str]] = []  # (item, external_id)
        for item in claimed:
            mapping = self.store.get_mapping(item["canonical_title_id"], source_key)
            if not mapping or mapping.get("state") != "VERIFIED":
                metrics.not_found += 1
                metrics.attempted += 1
                self.store.complete_item(
                    item["id"],
                    QueueItemState.SKIPPED if dry_run else QueueItemState.FAILED,
                    error="NO_VERIFIED_MAPPING",
                )
                continue
            to_fetch.append((item, str(mapping["external_title_id"])))

        # Batch fetch
        by_ext: dict[str, list[tuple[dict, str]]] = {}
        for item, ext in to_fetch:
            by_ext.setdefault(ext, []).append((item, ext))

        ext_ids = list(by_ext.keys())
        results: dict[str, FetchResult] = {}
        for start in range(0, len(ext_ids), self.config.batch_size):
            chunk = ext_ids[start : start + self.config.batch_size]
            try:
                part = self.adapter.fetch_by_ids(chunk)
                results.update(part)
                self.breaker.record_success()
                metrics.fetched += len(part)
            except AdapterError as exc:
                if exc.code == "RATE_LIMITED":
                    metrics.rate_limited += 1
                    metrics.retried += 1
                if exc.hard_circuit or exc.code in ("AUTH_REJECTED", "SCHEMA_DRIFT"):
                    self.breaker.record_failure(exc.code, hard=True)
                    for item, _ in ((i, e) for i, e in to_fetch if e in chunk):
                        metrics.failed += 1
                        metrics.attempted += 1
                        self.store.complete_item(item["id"], QueueItemState.FAILED, error=str(exc))
                    break
                self.breaker.record_failure(exc.code)
                for eid in chunk:
                    for item, _ in by_ext.get(eid, []):
                        metrics.failed += 1
                        metrics.attempted += 1
                        if item.get("attempts", 0) >= self.config.max_retries:
                            self.store.add_dead_letter(
                                canonical_title_id=item["canonical_title_id"],
                                source_key=source_key,
                                run_id=run_id,
                                error=str(exc),
                                payload={"external_id": eid},
                            )
                            metrics.dead_letter += 1
                            self.store.complete_item(item["id"], QueueItemState.DEAD_LETTER, error=str(exc))
                        else:
                            self.store.complete_item(item["id"], QueueItemState.PENDING, error=str(exc))
                continue

            # Process chunk results
            for eid in chunk:
                result = results.get(eid) or FetchResult(external_id=eid, found=False, error="NOT_FOUND")
                for item, _ in by_ext.get(eid, []):
                    metrics.attempted += 1
                    self._process_one(
                        metrics=metrics,
                        item=item,
                        source_key=source_key,
                        run_id=run_id,
                        dry_run=dry_run,
                        result=result,
                        worker_id=worker_id,
                    )

            # Crash-safe checkpoint
            metrics.checkpoint = {
                "last_external_ids": chunk,
                "attempted": metrics.attempted,
                "inserted": metrics.inserted,
            }
            self.store.save_checkpoint(run_id, metrics.checkpoint)

        usage = {}
        if hasattr(self.adapter, "rate_limiter"):
            usage = self.adapter.rate_limiter.usage()  # type: ignore[attr-defined]
            metrics.request_count = int(usage.get("request_count") or 0)
        metrics.daily_limit_usage = usage
        metrics.finished_at = utc_now_iso()
        try:
            t0 = datetime.fromisoformat(metrics.started_at.replace("Z", "+00:00"))
            t1 = datetime.fromisoformat(metrics.finished_at.replace("Z", "+00:00"))
            metrics.duration_sec = (t1 - t0).total_seconds()
        except ValueError:
            pass
        self.store.finish_run(run_id, "COMPLETED", metrics.as_dict())
        return metrics

    def _process_one(
        self,
        *,
        metrics: RunMetrics,
        item: dict,
        source_key: str,
        run_id: str,
        dry_run: bool,
        result: FetchResult,
        worker_id: str,
    ) -> None:
        self.store.heartbeat(item["id"], worker_id, self.config.lease_seconds)
        mapping = self.store.get_mapping(item["canonical_title_id"], source_key) or {}
        method = MappingMethod(mapping.get("mapping_method") or MappingMethod.NONE.value)

        if not result.found or result.raw_score is None:
            metrics.not_found += 1
            # Invalid/empty must not wipe last-good
            obs = RatingObservation(
                canonical_title_id=item["canonical_title_id"],
                source_key=source_key,
                external_id=result.external_id,
                raw_score=None,
                source_scale=10.0,
                normalized_score=None,
                vote_count=None,
                score_distribution=None,
                source_updated_at=result.source_updated_at,
                observed_at=utc_now_iso(),
                payload_sha256=payload_sha256(result.payload or {"not_found": True}),
                adapter_version=getattr(self.adapter, "adapter_version", ""),
                provenance_url=result.provenance_url,
                mapping_method=method,
                validation_state=ValidationState.NOT_FOUND,
                run_id=run_id,
                idempotency_key=_idempotency_key(
                    run_id, item["canonical_title_id"], source_key, "not_found"
                ),
            )
            outcome = apply_observation(self.store, obs, dry_run=dry_run)
            if outcome.get("action") == "preserved_last_good":
                metrics.last_good_preserved += 1
            self.store.complete_item(
                item["id"],
                QueueItemState.DONE if not dry_run else QueueItemState.SKIPPED,
                error="NOT_FOUND",
            )
            return

        # Score is Shikimori's — never relabel as MAL
        ph = payload_sha256(result.payload)
        existing = self.store.get_current(item["canonical_title_id"], source_key)
        if existing and existing[0].get("payload_sha256") == ph:
            metrics.unchanged += 1
            self.store.complete_item(
                item["id"],
                QueueItemState.DONE if not dry_run else QueueItemState.SKIPPED,
            )
            return

        obs = RatingObservation(
            canonical_title_id=item["canonical_title_id"],
            source_key=source_key,
            external_id=result.external_id,
            raw_score=result.raw_score,
            source_scale=10.0,
            normalized_score=result.raw_score,  # already 10-point
            vote_count=result.vote_count,
            score_distribution=result.score_distribution,
            source_updated_at=result.source_updated_at,
            observed_at=utc_now_iso(),
            payload_sha256=ph,
            adapter_version=getattr(self.adapter, "adapter_version", ""),
            provenance_url=result.provenance_url,
            mapping_method=method,
            validation_state=ValidationState.VALID,
            run_id=run_id,
            idempotency_key=_idempotency_key(
                run_id, item["canonical_title_id"], source_key, ph
            ),
        )
        metrics.matched += 1
        outcome = apply_observation(self.store, obs, dry_run=dry_run)
        if outcome.get("inserted"):
            metrics.inserted += 1
            if existing:
                metrics.refreshed += 1
        elif outcome.get("action") == "dry_run_would_insert":
            # Count as matched planning success, inserted stays 0
            pass
        elif outcome.get("action") == "idempotent_skip":
            metrics.unchanged += 1
        self.store.complete_item(
            item["id"],
            QueueItemState.DONE if not dry_run else QueueItemState.SKIPPED,
        )
