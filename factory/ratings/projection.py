"""Current projection: last-good preservation. NULL ≠ 0."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from factory.ratings.models import (
    FreshnessState,
    RatingCurrent,
    RatingObservation,
    ValidationState,
)
from factory.ratings.store import RatingsStore


def _parse(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def freshness_for(
    observed_at: str,
    *,
    policy_hours: float = 24.0,
    stale_hours: float = 24.0 * 14,
    expired_hours: float = 24.0 * 90,
    now: datetime | None = None,
) -> FreshnessState:
    moment = _parse(observed_at)
    if moment is None:
        return FreshnessState.MISSING
    now = now or datetime.now(timezone.utc)
    age_h = (now - moment).total_seconds() / 3600.0
    if age_h <= policy_hours:
        return FreshnessState.FRESH
    if age_h <= stale_hours:
        return FreshnessState.STALE
    if age_h <= expired_hours:
        return FreshnessState.EXPIRED
    return FreshnessState.EXPIRED


def apply_observation(
    store: RatingsStore,
    obs: RatingObservation,
    *,
    dry_run: bool = True,
    accepted_target: int | None = None,
) -> dict[str, Any]:
    """Применить наблюдение к current. Невалидное/пустое не затирает last-good.

    When ``accepted_target`` is set, insertion is gated by an atomic per-run
    accepted count so writers cannot overshoot the daily/pilot cap.
    """
    existing = store.get_current(obs.canonical_title_id, obs.source_key)
    last_good = existing[0] if existing else None

    if obs.validation_state != ValidationState.VALID or obs.normalized_score is None:
        # Preserve last-good
        return {
            "action": "preserved_last_good",
            "inserted": False,
            "reason": obs.validation_state.value,
            "last_good_present": last_good is not None,
            "last_good_score": None if last_good is None else last_good.get("normalized_score"),
        }

    if dry_run:
        if accepted_target is not None and accepted_target <= 0:
            return {"action": "accepted_cap_reached", "inserted": False}
        return {
            "action": "dry_run_would_insert",
            "inserted": False,
            "score": obs.normalized_score,
            "vote_count": obs.vote_count,
        }

    if accepted_target is not None:
        obs_id, status = store.insert_observation_capped(obs, accepted_target=accepted_target)
        if status == "accepted_cap_reached":
            return {
                "action": "accepted_cap_reached",
                "inserted": False,
                "accepted_target": accepted_target,
            }
        if status == "idempotent_skip" or obs_id is None:
            return {
                "action": "idempotent_skip",
                "inserted": False,
                "reason": "duplicate_idempotency_key",
            }
    else:
        obs_id = store.insert_observation(obs)
        if obs_id is None:
            return {
                "action": "idempotent_skip",
                "inserted": False,
                "reason": "duplicate_idempotency_key",
            }

    current = RatingCurrent(
        canonical_title_id=obs.canonical_title_id,
        source_key=obs.source_key,
        observation_id=obs_id,
        raw_score=obs.raw_score,
        normalized_score=obs.normalized_score,
        vote_count=obs.vote_count,
        freshness=freshness_for(obs.observed_at),
        observed_at=obs.observed_at,
        provenance_url=obs.provenance_url,
        payload_sha256=obs.payload_sha256,
        adapter_version=obs.adapter_version,
        external_id=obs.external_id,
    )
    store.upsert_current(current)
    return {
        "action": "inserted",
        "inserted": True,
        "observation_id": obs_id,
        "score": obs.normalized_score,
        "vote_count": obs.vote_count,
    }


def score_never_zero_from_null(value: float | None) -> float | None:
    """Контракт: NULL никогда не становится 0."""
    if value is None:
        return None
    return value
