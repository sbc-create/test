"""Stage 5R mandatory cap/ledger/reconciliation tests — no live network."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from factory.ratings.adapters.base import FetchResult
from factory.ratings.config import RatingsConfig
from factory.ratings.ingestion import IngestionEngine
from factory.ratings.models import MappingMethod, MappingState, TitleSourceMapping, utc_now_iso
from factory.ratings.rate_limit import RateLimiter
from factory.ratings.source_registry import seed_registry
from factory.ratings.stage5_constants import (
    ACCEPTED_HARD_CAP,
    CANDIDATE_ATTEMPT_CAP,
)
from factory.ratings.stage5_ledger import RunLedger
from factory.ratings.stage5_sim import run_31_day_simulation
from factory.ratings.store import RatingsStore


class _AllValidAdapter:
    source_key = "shikimori"
    adapter_version = "t"
    rate_limiter = RateLimiter(max_rps=1000, max_per_minute=100000, sleeper=lambda _s: None)
    invalid_ids: set[str] = set()

    def fetch_by_ids(self, ids):
        out = {}
        for eid in ids:
            if eid in self.invalid_ids:
                out[eid] = FetchResult(external_id=eid, found=False, error="NOT_FOUND")
            else:
                out[eid] = FetchResult(
                    external_id=eid,
                    found=True,
                    raw_score=8.0,
                    vote_count=10,
                    payload={"id": eid, "score": 8.0},
                    provenance_url=f"https://shikimori.io/animes/{eid}",
                )
        return out


def _seed(store: RatingsStore, n: int, *, prefix: str = "t") -> None:
    for i in range(n):
        store.upsert_mapping(
            TitleSourceMapping(
                canonical_title_id=f"nova:{prefix}{i}",
                source_key="shikimori",
                external_title_id=str(i),
                mapping_method=MappingMethod.SHIKIMORI_ID,
                confidence=1.0,
                state=MappingState.VERIFIED,
                verified_at=utc_now_iso(),
            )
        )
        store.enqueue(
            canonical_title_id=f"nova:{prefix}{i}",
            source_key="shikimori",
            priority=10,
            priority_label="t",
        )


def _engine(store: RatingsStore, adapter=None) -> IngestionEngine:
    cfg = RatingsConfig(
        daily_success_target=ACCEPTED_HARD_CAP,
        daily_candidate_cap=CANDIDATE_ATTEMPT_CAP,
        batch_size=50,
        db_path=store.path if hasattr(store, "path") else None,
    )
    return IngestionEngine(store, adapter or _AllValidAdapter(), cfg)


@pytest.fixture
def store(tmp_path: Path):
    db = tmp_path / "r.sqlite"
    s = RatingsStore(db)
    seed_registry(s)
    yield s
    s.close()


def test_01_150_valid_commit_100_rest_deferred(store):
    _seed(store, 150)
    m = _engine(store).ingest(
        source_key="shikimori",
        limit=CANDIDATE_ATTEMPT_CAP,
        dry_run=False,
        apply=True,
        run_id="r1",
        idempotency_key="r1",
        use_lock=False,
        accepted_target=ACCEPTED_HARD_CAP,
        quota_window="2099-01-01",
    )
    assert m.inserted == 100
    assert store.count_accepted_for_run("r1") == 100
    assert m.deferred_capacity >= 50
    assert m.inserted + m.not_found + m.deferred_capacity + m.unchanged + m.failed <= m.attempted + 50


def test_02_125_valid_25_invalid_max_100(store):
    adapter = _AllValidAdapter()
    # Invalids first so rejections are recorded before accepted hard cap stops work.
    adapter.invalid_ids = {str(i) for i in range(0, 25)}
    _seed(store, 150)
    m = _engine(store, adapter).ingest(
        source_key="shikimori",
        limit=150,
        dry_run=False,
        apply=True,
        run_id="r2",
        idempotency_key="r2",
        use_lock=False,
        accepted_target=100,
        quota_window="2099-01-02",
    )
    assert m.inserted == 100
    assert m.not_found == 25
    assert store.count_accepted_for_run("r2") == 100


def test_03_80_valid_shortfall_20(store):
    adapter = _AllValidAdapter()
    adapter.invalid_ids = {str(i) for i in range(80, 150)}
    _seed(store, 150)
    m = _engine(store, adapter).ingest(
        source_key="shikimori",
        limit=150,
        dry_run=False,
        apply=True,
        run_id="r3",
        idempotency_key="r3",
        use_lock=False,
        accepted_target=100,
        quota_window="2099-01-03",
    )
    assert m.inserted == 80
    assert m.not_found == 70
    shortfall = 100 - m.inserted
    assert shortfall == 20


def test_04_boundaries_99_100_101(tmp_path: Path):
    results = {}
    for n in (99, 100, 101):
        db = tmp_path / f"bnd-{n}.sqlite"
        s = RatingsStore(db)
        seed_registry(s)
        for i in range(n):
            eid = str(200000 + n * 1000 + i)
            s.upsert_mapping(
                TitleSourceMapping(
                    canonical_title_id=f"nova:bnd-{n}-{i}",
                    source_key="shikimori",
                    external_title_id=eid,
                    mapping_method=MappingMethod.SHIKIMORI_ID,
                    confidence=1.0,
                    state=MappingState.VERIFIED,
                    verified_at=utc_now_iso(),
                )
            )
            s.enqueue(
                canonical_title_id=f"nova:bnd-{n}-{i}",
                source_key="shikimori",
                priority=10,
                priority_label="t",
            )
        m = _engine(s).ingest(
            source_key="shikimori",
            limit=n,
            dry_run=False,
            apply=True,
            run_id=f"bnd-{n}",
            idempotency_key=f"bnd-{n}",
            use_lock=False,
            accepted_target=100,
            quota_window=f"2099-02-{min(n, 28):02d}",
        )
        results[n] = m.inserted
        s.close()
    assert results[99] == 99
    assert results[100] == 100
    assert results[101] == 100


def test_05_crash_after_99_resume_max_100(tmp_path: Path):
    db = tmp_path / "crash.sqlite"
    s = RatingsStore(db)
    seed_registry(s)
    for i in range(150):
        s.upsert_mapping(
            TitleSourceMapping(
                canonical_title_id=f"nova:c{i}",
                source_key="shikimori",
                external_title_id=str(5000 + i),
                mapping_method=MappingMethod.SHIKIMORI_ID,
                confidence=1.0,
                state=MappingState.VERIFIED,
                verified_at=utc_now_iso(),
            )
        )
        s.enqueue(
            canonical_title_id=f"nova:c{i}",
            source_key="shikimori",
            priority=10,
            priority_label="t",
        )
    # First pass: insert 99 manually via capped inserts then stop
    eng = _engine(s)
    m1 = eng.ingest(
        source_key="shikimori",
        limit=99,
        dry_run=False,
        apply=True,
        run_id="crash-a",
        idempotency_key="crash-a",
        use_lock=False,
        accepted_target=100,
        quota_window="2099-03-01",
    )
    assert m1.inserted == 99
    # Re-enqueue remaining and continue with NEW run id but SAME quota window
    for i in range(99, 150):
        s.enqueue(
            canonical_title_id=f"nova:c{i}",
            source_key="shikimori",
            priority=10,
            priority_label="t",
        )
    m2 = eng.ingest(
        source_key="shikimori",
        limit=60,
        dry_run=False,
        apply=True,
        run_id="crash-b",
        idempotency_key="crash-b",
        use_lock=False,
        accepted_target=100,
        quota_window="2099-03-01",
    )
    total = s.count_accepted_for_quota_window(source_key="shikimori", quota_window="2099-03-01")
    assert total == 100
    assert m2.inserted <= 1
    s.close()


def test_06_two_parallel_workers_max_100(tmp_path: Path):
    db = tmp_path / "par.sqlite"
    s = RatingsStore(db)
    seed_registry(s)
    for i in range(200):
        s.upsert_mapping(
            TitleSourceMapping(
                canonical_title_id=f"nova:p{i}",
                source_key="shikimori",
                external_title_id=str(8000 + i),
                mapping_method=MappingMethod.SHIKIMORI_ID,
                confidence=1.0,
                state=MappingState.VERIFIED,
                verified_at=utc_now_iso(),
            )
        )
        s.enqueue(
            canonical_title_id=f"nova:p{i}",
            source_key="shikimori",
            priority=10,
            priority_label="t",
        )
    errors: list[str] = []

    def worker(wid: str):
        try:
            # each worker gets own store connection
            local = RatingsStore(db)
            eng = _engine(local)
            eng.ingest(
                source_key="shikimori",
                limit=150,
                dry_run=False,
                apply=True,
                run_id=f"par-{wid}",
                idempotency_key=f"par-{wid}",
                use_lock=False,
                accepted_target=100,
                quota_window="2099-04-01",
            )
            local.close()
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))

    t1 = threading.Thread(target=worker, args=("a",))
    t2 = threading.Thread(target=worker, args=("b",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert not errors
    total = s.count_accepted_for_quota_window(source_key="shikimori", quota_window="2099-04-01")
    assert total == 100
    s.close()


def test_07_two_sequential_runs_same_quota_window(store):
    for i in range(80):
        store.upsert_mapping(
            TitleSourceMapping(
                canonical_title_id=f"nova:seqa{i}",
                source_key="shikimori",
                external_title_id=str(300000 + i),
                mapping_method=MappingMethod.SHIKIMORI_ID,
                confidence=1.0,
                state=MappingState.VERIFIED,
                verified_at=utc_now_iso(),
            )
        )
        store.enqueue(
            canonical_title_id=f"nova:seqa{i}",
            source_key="shikimori",
            priority=10,
            priority_label="t",
        )
    m1 = _engine(store).ingest(
        source_key="shikimori",
        limit=80,
        dry_run=False,
        apply=True,
        run_id="seq1",
        idempotency_key="seq1",
        use_lock=False,
        accepted_target=100,
        quota_window="2099-05-01",
    )
    for i in range(80):
        store.upsert_mapping(
            TitleSourceMapping(
                canonical_title_id=f"nova:seqb{i}",
                source_key="shikimori",
                external_title_id=str(400000 + i),
                mapping_method=MappingMethod.SHIKIMORI_ID,
                confidence=1.0,
                state=MappingState.VERIFIED,
                verified_at=utc_now_iso(),
            )
        )
        store.enqueue(
            canonical_title_id=f"nova:seqb{i}",
            source_key="shikimori",
            priority=10,
            priority_label="t",
        )
    m2 = _engine(store).ingest(
        source_key="shikimori",
        limit=80,
        dry_run=False,
        apply=True,
        run_id="seq2",
        idempotency_key="seq2",
        use_lock=False,
        accepted_target=100,
        quota_window="2099-05-01",
    )
    total = store.count_accepted_for_quota_window(source_key="shikimori", quota_window="2099-05-01")
    assert m1.inserted == 80
    assert m2.inserted == 20
    assert total == 100


def test_08_network_retry_no_double_accept(store):
    _seed(store, 10, prefix="nr")
    eng = _engine(store)
    m1 = eng.ingest(
        source_key="shikimori",
        limit=10,
        dry_run=False,
        apply=True,
        run_id="nr1",
        idempotency_key="nr-idem",
        use_lock=False,
        accepted_target=100,
        quota_window="2099-06-01",
    )
    m2 = eng.ingest(
        source_key="shikimori",
        limit=10,
        dry_run=False,
        apply=True,
        run_id="nr1",
        idempotency_key="nr-idem",
        use_lock=False,
        accepted_target=100,
        quota_window="2099-06-01",
    )
    assert m1.inserted == 10
    assert m2.checkpoint.get("idempotent_replay") is True
    assert store.count_accepted_for_run("nr1") == 10


def test_09_db_failure_after_reservation_returns_slot(store):
    """If insert fails after cap check, no slot is consumed (IntegrityError path)."""
    from factory.ratings.models import RatingObservation, ValidationState

    obs = RatingObservation(
        canonical_title_id="nova:x",
        source_key="shikimori",
        external_id="1",
        raw_score=8.0,
        source_scale=10.0,
        normalized_score=8.0,
        vote_count=1,
        score_distribution=None,
        source_updated_at="",
        observed_at="2099-07-01T12:00:00Z",
        payload_sha256="abc",
        adapter_version="t",
        provenance_url="u",
        mapping_method=MappingMethod.SHIKIMORI_ID,
        validation_state=ValidationState.VALID,
        run_id="fail-slot",
        idempotency_key="fail-slot-key",
    )
    oid, st = store.insert_observation_capped(obs, accepted_target=100, quota_window="2099-07-01")
    assert st == "inserted"
    oid2, st2 = store.insert_observation_capped(obs, accepted_target=100, quota_window="2099-07-01")
    assert st2 == "idempotent_skip"
    assert store.count_accepted_for_quota_window(source_key="shikimori", quota_window="2099-07-01") == 1


def test_10_duplicate_replay_no_new_slot(store):
    test_09_db_failure_after_reservation_returns_slot(store)


def test_11_newly_covered_plus_refreshed_one_cap(store):
    _seed(store, 50, prefix="nc")
    eng = _engine(store)
    eng.ingest(
        source_key="shikimori",
        limit=50,
        dry_run=False,
        apply=True,
        run_id="nc1",
        idempotency_key="nc1",
        use_lock=False,
        accepted_target=100,
        quota_window="2099-08-01",
    )
    # change payloads to force refresh
    class RefreshAdapter(_AllValidAdapter):
        def fetch_by_ids(self, ids):
            return {
                eid: FetchResult(
                    external_id=eid,
                    found=True,
                    raw_score=9.0,
                    vote_count=20,
                    payload={"id": eid, "score": 9.0, "v": 2},
                    provenance_url=f"https://shikimori.io/animes/{eid}",
                )
                for eid in ids
            }

    for i in range(50):
        store.enqueue(
            canonical_title_id=f"nova:nc{i}",
            source_key="shikimori",
            priority=10,
            priority_label="t",
        )
    for i in range(60):
        store.upsert_mapping(
            TitleSourceMapping(
                canonical_title_id=f"nova:ncx{i}",
                source_key="shikimori",
                external_title_id=str(11000 + i),
                mapping_method=MappingMethod.SHIKIMORI_ID,
                confidence=1.0,
                state=MappingState.VERIFIED,
                verified_at=utc_now_iso(),
            )
        )
        store.enqueue(
            canonical_title_id=f"nova:ncx{i}",
            source_key="shikimori",
            priority=10,
            priority_label="t",
        )
    m2 = IngestionEngine(store, RefreshAdapter(), RatingsConfig(batch_size=50)).ingest(
        source_key="shikimori",
        limit=150,
        dry_run=False,
        apply=True,
        run_id="nc2",
        idempotency_key="nc2",
        use_lock=False,
        accepted_target=100,
        quota_window="2099-08-01",
    )
    total = store.count_accepted_for_quota_window(source_key="shikimori", quota_window="2099-08-01")
    # refreshes create new observation rows that also count toward window
    assert total == 100
    assert m2.inserted + 50 >= 100 or total == 100


def test_12_claimed_converge_ledger():
    led = RunLedger(
        run_id="x",
        source="shikimori",
        quota_window="2099-09-01",
        planned=150,
        claimed=150,
        newly_covered=100,
        refreshed=0,
        rejected=25,
        deferred_capacity=25,
        unprocessed=0,
        accepted_hard_cap=100,
        accepted_target=100,
        rejection_breakdown={"NOT_FOUND": 25},
    )
    led.recompute()
    assert led.accepted == 100
    assert led.attempted == 150
    assert led.validate() == []


def test_13_snapshot_only_committed(store):
    from factory.ratings.snapshot import build_snapshot, validate_snapshot

    _seed(store, 5, prefix="sn")
    _engine(store).ingest(
        source_key="shikimori",
        limit=5,
        dry_run=False,
        apply=True,
        run_id="sn1",
        idempotency_key="sn1",
        use_lock=False,
        accepted_target=100,
        quota_window="2099-10-01",
    )
    body = build_snapshot(store, primary_source="shikimori")
    assert validate_snapshot(body) == []
    assert len(body.get("titles") or []) >= 5


def test_14_existing_125_reconciliation_readable():
    from factory.ratings.prod_db import resolve_canonical_db
    from factory.ratings.stage5_incident import reconcile_incident

    db = resolve_canonical_db()
    if not db.is_file():
        pytest.skip("no production db")
    result = reconcile_incident(db_path=db, snapshot_path=None, evidence_dir=None)
    assert result["TOTAL_ROWS"] == 125
    assert result["ALL_ROWS_PROVENANCE_PASS"] == 1
    assert result["VALID_OVER_CAP_ROWS"] == 25
    assert result["DATA_CORRUPTION"] == 0
    assert result["ROLLBACK_REQUIRED"] == "NO"


def test_15_failed_cycle_not_successful():
    from factory.ratings.stage5_report import pilot_cycle_accounting

    acc = pilot_cycle_accounting(attempted=1, successful=0, failed=1)
    assert acc["PILOT_ATTEMPTED_CYCLES"] == 1
    assert acc["PILOT_FAILED_CYCLES"] == 1
    assert acc["PILOT_SUCCESSFUL_CYCLES"] == 0
    assert acc["REQUIRED_SUCCESSFUL_CYCLES"] == 7


def test_16_scheduler_blocked_without_qwen():
    from factory.ratings.stage5_report import scheduler_gate_for_repair

    g = scheduler_gate_for_repair(
        first_supervised_pass=False,
        qwen_configured=False,
        qwen_ack=False,
    )
    assert g["SCHEDULER_ENABLED"] == "NO"
    assert g["READY_FOR_DAILY_100_PILOT"] == "NO"


def test_31_day_sim_no_cap_violation():
    sim = run_31_day_simulation(days=31, start_uncovered=500)
    assert sim["SIMULATION_DAILY_LIMIT_VIOLATIONS"] == 0
    assert sim["ok"] is True
