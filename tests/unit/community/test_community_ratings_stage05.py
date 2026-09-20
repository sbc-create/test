"""Stage05 property + security suite for community ratings."""

from __future__ import annotations

import concurrent.futures
import uuid
from decimal import Decimal

import pytest

from factory.community.antifraud import AntifraudConfig, AntifraudGuard, KillSwitchActive, OriginRejected, RateLimited, ReadOnlyMode
from factory.community.api import CommunityRatingsAPI
from factory.community.formulas import (
    DEFAULT_PRIOR_STRENGTH_M,
    NativeAggregate,
    YummyPublic,
    build_yummy_prior,
    round_display,
)
from factory.community.provenance import prove_no_double_count
from factory.community.service import CommunityVotesService
from factory.community.store import CommunityStore
from factory.ratings.prod_db import resolve_canonical_db


@pytest.fixture()
def store():
    s = CommunityStore(resolve_canonical_db())
    yield s
    # cleanup test actors
    s.conn.execute("DELETE FROM community_votes WHERE actor_id LIKE 'canary-cr05-test-%'")
    s.conn.execute(
        "DELETE FROM community_aggregates WHERE subject_id LIKE 'nova:00000000-cr05-%'"
    )
    s.conn.commit()
    s.close()


def test_property_score_domain_and_counts():
    a = NativeAggregate(0, 0)
    assert a.average is None
    for score in range(1, 11):
        b = a.after_create(score)
        assert 1 <= score <= 10
        assert b.vote_count == 1
        assert b.vote_sum == score
    with pytest.raises(Exception):
        NativeAggregate(-1, 1).assert_invariants()


def test_property_preview_rebuild_double_count(store):
    proof = prove_no_double_count()
    assert proof["SOURCE_LINEAGE_DOUBLE_COUNT_COUNT"] == 0
    assert proof["animedia_projected_rejected"] is True
    assert proof["PRIOR_COMPONENTS_INDEPENDENT"] == 1
    p, _ = build_yummy_prior(animedia_native=Decimal("8"), shikimori=Decimal("7"))
    y = YummyPublic(0, 0, p, m=10)
    assert y.displayed_vote_count() == 0
    assert DEFAULT_PRIOR_STRENGTH_M == 10
    assert round_display(Decimal("7.16"), "0.1") == Decimal("7.2")


def test_api_csrf_origin_kill_readonly_rate(store):
    guard = AntifraudGuard(AntifraudConfig(rate_limit_max=3, burst_max=3, title_rate_limit_max=3))
    api = CommunityRatingsAPI(CommunityVotesService(store), guard)
    subject = f"nova:00000000-cr05-{uuid.uuid4().hex[:8]}"
    actor = f"canary-cr05-test-{uuid.uuid4().hex[:8]}"
    # CSRF fail
    bad = api.put_vote(
        idempotency_key=f"k-{uuid.uuid4().hex}",
        rating_space_id="yummy",
        subject_id=subject,
        actor_id=actor,
        score=7,
        origin="https://evil.example",
        csrf_token="a",
        session_csrf="b",
    )
    assert bad["status"] == 403
    # good origin
    ok = api.put_vote(
        idempotency_key=f"k-{uuid.uuid4().hex}",
        rating_space_id="yummy",
        subject_id=subject,
        actor_id=actor,
        score=7,
        origin="https://yummyani.site",
        csrf_token="tok",
        session_csrf="tok",
        account_id=actor,
    )
    assert ok.get("status") == 200 or ok.get("my_vote") == 7 or "after" in ok
    # kill switch
    guard.set_kill_switch(True)
    killed = api.put_vote(
        idempotency_key=f"k-{uuid.uuid4().hex}",
        rating_space_id="yummy",
        subject_id=subject,
        actor_id=actor,
        score=8,
        origin="https://yummyani.site",
        csrf_token="tok",
        session_csrf="tok",
        account_id=actor,
    )
    assert killed["status"] == 503 and killed["code"] == "KillSwitchActive"
    guard.set_kill_switch(False)
    guard.set_read_only(True)
    ro = api.delete_vote(
        idempotency_key=f"k-{uuid.uuid4().hex}",
        rating_space_id="yummy",
        subject_id=subject,
        actor_id=actor,
        origin="https://yummyani.site",
        csrf_token="tok",
        session_csrf="tok",
        account_id=actor,
    )
    assert ro["status"] == 503 and ro["code"] == "ReadOnlyMode"
    guard.set_read_only(False)


def test_idempotency_concurrent_and_retract(store):
    svc = CommunityVotesService(store)
    subject = f"nova:00000000-cr05-{uuid.uuid4().hex[:8]}"
    actor = f"canary-cr05-test-{uuid.uuid4().hex[:8]}"
    prev = svc.preview_one(rating_space_id="yummy", subject_id=subject, actor_id=actor, score=7)
    idem = f"idem-{uuid.uuid4().hex}"

    def once():
        return svc.put_vote(
            idempotency_key=idem,
            rating_space_id="yummy",
            subject_id=subject,
            actor_id=actor,
            score=7,
        )

    with concurrent.futures.ThreadPoolExecutor(4) as pool:
        outs = [f.result() for f in [pool.submit(once) for _ in range(4)]]
    n = store.conn.execute(
        """SELECT COUNT(*) FROM community_votes
           WHERE rating_space_id='yummy' AND subject_id=? AND actor_id=? AND status='ACCEPTED'""",
        (subject, actor),
    ).fetchone()[0]
    assert n == 1
    assert prev.get("after") == outs[0].get("after")
    before = store.conn.execute(
        "SELECT COUNT(*) FROM community_vote_events WHERE actor_id=?", (actor,)
    ).fetchone()[0]
    svc.put_vote(
        idempotency_key=idem,
        rating_space_id="yummy",
        subject_id=subject,
        actor_id=actor,
        score=7,
    )
    after = store.conn.execute(
        "SELECT COUNT(*) FROM community_vote_events WHERE actor_id=?", (actor,)
    ).fetchone()[0]
    assert after == before
    upd = svc.put_vote(
        idempotency_key=f"u-{uuid.uuid4().hex}",
        rating_space_id="yummy",
        subject_id=subject,
        actor_id=actor,
        score=9,
    )
    assert upd.get("native_vote_count") == 1
    # cross-space isolation
    assert (
        store.conn.execute(
            "SELECT COUNT(*) FROM community_votes WHERE rating_space_id='animedia' AND actor_id=?",
            (actor,),
        ).fetchone()[0]
        == 0
    )
    svc.delete_vote(
        idempotency_key=f"d-{uuid.uuid4().hex}",
        rating_space_id="yummy",
        subject_id=subject,
        actor_id=actor,
    )
    left = store.conn.execute(
        """SELECT COUNT(*) FROM community_votes
           WHERE rating_space_id='yummy' AND subject_id=? AND actor_id=? AND status='ACCEPTED'""",
        (subject, actor),
    ).fetchone()[0]
    assert left == 0


def test_malformed_scores_rejected(store):
    svc = CommunityVotesService(store)
    subject = f"nova:00000000-cr05-{uuid.uuid4().hex[:8]}"
    actor = f"canary-cr05-test-{uuid.uuid4().hex[:8]}"
    for bad in (0, 11, -1):
        with pytest.raises(Exception):
            svc.put_vote(
                idempotency_key=f"bad-{uuid.uuid4().hex}",
                rating_space_id="yummy",
                subject_id=subject,
                actor_id=actor,
                score=bad,
            )
