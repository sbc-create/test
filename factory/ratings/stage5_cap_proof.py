"""Offline proof that Stage5 accepted hard-cap cannot overshoot (no network)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from factory.ratings.adapters.base import FetchResult
from factory.ratings.config import RatingsConfig
from factory.ratings.ingestion import IngestionEngine
from factory.ratings.models import MappingMethod, MappingState, TitleSourceMapping
from factory.ratings.rate_limit import RateLimiter
from factory.ratings.source_registry import seed_registry
from factory.ratings.stage5_constants import ACCEPTED_HARD_CAP, CANDIDATE_ATTEMPT_CAP, EVIDENCE_DIR
from factory.ratings.store import RatingsStore


class _CapProofAdapter:
    source_key = "shikimori"
    adapter_version = "stage5-cap-proof/1.0"
    rate_limiter = RateLimiter(max_rps=1000, max_per_minute=10000, sleeper=lambda _s: None)
    fetch_calls = 0

    def fetch_by_ids(self, ids: list[str]) -> dict[str, FetchResult]:
        self.fetch_calls += 1
        out: dict[str, FetchResult] = {}
        for eid in ids:
            score = 7.0 + (int(eid) % 20) / 10.0
            out[eid] = FetchResult(
                external_id=eid,
                found=True,
                raw_score=score,
                vote_count=10 + int(eid),
                payload={"id": eid, "score": score, "score_source": "shikimori"},
                provenance_url=f"https://shikimori.io/animes/{eid}",
            )
        return out


def run_cap_proof(*, db_path: Path, n_candidates: int = CANDIDATE_ATTEMPT_CAP) -> dict[str, Any]:
    """Enqueue n_candidates and ingest with accepted_target=100; assert no overshoot."""
    if db_path.exists():
        db_path.unlink()
    store = RatingsStore(db_path)
    seed_registry(store)
    for i in range(n_candidates):
        cid = f"nova:cap-{i:04d}"
        ext = str(20000 + i)
        store.upsert_mapping(
            TitleSourceMapping(
                canonical_title_id=cid,
                source_key="shikimori",
                external_title_id=ext,
                mapping_method=MappingMethod.MAL_ID_CROSSWALK,
                confidence=1.0,
                state=MappingState.VERIFIED,
                verified_at="2026-09-20T00:00:00Z",
                evidence="cap-proof",
            )
        )
        store.enqueue(
            canonical_title_id=cid,
            source_key="shikimori",
            priority=10,
            priority_label="cap_proof",
        )

    cfg = RatingsConfig(
        daily_success_target=ACCEPTED_HARD_CAP,
        daily_candidate_cap=CANDIDATE_ATTEMPT_CAP,
        batch_size=50,
        max_rps=1000,
        db_path=db_path,
        lock_name="ratings-cap-proof",
    )
    adapter = _CapProofAdapter()
    engine = IngestionEngine(store, adapter, cfg)
    metrics = engine.ingest(
        source_key="shikimori",
        limit=n_candidates,
        dry_run=False,
        apply=True,
        run_id="stage5-cap-proof-offline",
        idempotency_key="stage5:cap-proof-offline",
        use_lock=False,
        accepted_target=ACCEPTED_HARD_CAP,
        quota_window="2099-12-31",
    )
    accepted = store.count_accepted_for_run("stage5-cap-proof-offline")
    total_obs = store.observation_count()
    store.close()
    ok = (
        metrics.inserted <= ACCEPTED_HARD_CAP
        and accepted <= ACCEPTED_HARD_CAP
        and accepted == metrics.inserted
        and metrics.deferred_capacity > 0
    )
    return {
        "ok": ok,
        "LIVE_NETWORK": 0,
        "candidates_enqueued": n_candidates,
        "accepted_target": ACCEPTED_HARD_CAP,
        "CANDIDATE_ATTEMPT_CAP": CANDIDATE_ATTEMPT_CAP,
        "ACCEPTED_HARD_CAP": ACCEPTED_HARD_CAP,
        "inserted": metrics.inserted,
        "accepted_db_count": accepted,
        "accepted_cap_skipped": metrics.accepted_cap_skipped,
        "deferred_capacity": metrics.deferred_capacity,
        "fetch_calls": adapter.fetch_calls,
        "total_observations": total_obs,
        "DAILY_ACCEPTED_ABOVE_100": 0 if accepted <= ACCEPTED_HARD_CAP else 1,
        "SECOND_LIVE_CYCLE_ATTEMPT": 0,
        "metrics": metrics.as_dict(),
    }


def main() -> int:
    from factory.paths import PATHS

    ev = PATHS.root / EVIDENCE_DIR
    ev.mkdir(parents=True, exist_ok=True)
    raw = ev / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    result = run_cap_proof(db_path=raw / "accepted_cap_proof.sqlite")
    (ev / "ACCEPTED_CAP_PROOF.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    plan = {
        "title": "Safe supervised retry plan (no live cycle now)",
        "LIVE_CYCLES_ATTEMPTED_THIS_REPAIR": 0,
        "SECOND_LIVE_CYCLE_ATTEMPT": 0,
        "AMD_NETWORK_CALLS": 0,
        "preconditions_for_future_authorized_cycle": [
            "atomic accepted_target hard cap merged and ACCEPTED_CAP_PROOF.ok=true",
            "ACCEPTED_CAP_RECONCILIATION.json reviewed (overshoot retained, not deleted)",
            "owner authorizes a new Stage5/6 live cycle explicitly",
            "Qwen config still required before enabling daily timer",
            "claim limit and accepted_target both = 100; candidate_cap = 150",
        ],
        "command_when_authorized": (
            "python -m factory.ratings.stage5_supervised --apply-live"
        ),
        "command_offline_proof": (
            "python -m factory.ratings.stage5_cap_proof"
        ),
        "do_not": [
            "run a second live cycle as part of this repair",
            "delete the 25 overshoot observations blindly",
            "enable scheduler without Qwen ACK",
            "call AMD network",
        ],
    }
    (ev / "SUPERVISED_RETRY_PLAN.md").write_text(
        "# Supervised retry plan (safe, no live cycle)\n\n"
        "```json\n"
        + json.dumps(plan, ensure_ascii=False, indent=2)
        + "\n```\n",
        encoding="utf-8",
    )
    (ev / "SUPERVISED_RETRY_PLAN.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
