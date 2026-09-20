"""COMMUNITY-RATINGS-06 — identity, cohort, native formula, security matrix."""

from __future__ import annotations

import concurrent.futures
import os
import tempfile
import uuid
from decimal import Decimal
from pathlib import Path

import pytest

from factory.community.antifraud import AntifraudConfig, AntifraudGuard, RateLimited
from factory.community.api import PublicRatingsFacade, CommunityRatingsAPI
from factory.community.cohort import cohort_bucket, decide_cohort
from factory.community.formulas import NativeAggregate, round_display
from factory.community.identity_v1 import (
    IdentityForgery,
    issue_token,
    mint_identity_id,
    reject_client_supplied_user_id,
    verify_token,
)
from factory.community.rollout import (
    RolloutFlags,
    enable_1pct_canary,
    load_flags,
    save_flags,
    trigger_kill_switch,
)
from factory.community.service import CommunityVotesService, CommunityValidationError
from factory.community.store import CommunityStore


@pytest.fixture()
def tmp_flags(tmp_path, monkeypatch):
    p = tmp_path / "flags.json"
    monkeypatch.setenv("COMMUNITY_ROLLOUT_FLAGS_PATH", str(p))
    save_flags(RolloutFlags())
    return p


@pytest.fixture()
def store(tmp_path):
    db = tmp_path / "cr06.sqlite"
    s = CommunityStore(db)
    yield s
    s.close()


@pytest.fixture()
def identity_secret(monkeypatch):
    monkeypatch.setenv("COMMUNITY_IDENTITY_HMAC_SECRET", "test-identity-secret-cr06")
    monkeypatch.setenv("COMMUNITY_ROLLOUT_SALT", "test-rollout-salt-cr06")
    monkeypatch.delenv("COMMUNITY_IDENTITY_HMAC_SECRET_FILE", raising=False)
    monkeypatch.delenv("COMMUNITY_ROLLOUT_SALT_FILE", raising=False)


def test_identity_sign_verify_tamper(identity_secret):
    iid = mint_identity_id()
    tok = issue_token(identity_id=iid)
    assert verify_token(tok) == iid
    parts = tok.split(".")
    bad = f"{parts[0]}.{parts[1]}.{'0' * 64}"
    with pytest.raises(IdentityForgery):
        verify_token(bad)
    swapped = f"{parts[0]}.{mint_identity_id()}.{parts[2]}"
    with pytest.raises(IdentityForgery):
        verify_token(swapped)


def test_reject_client_user_id(identity_secret):
    with pytest.raises(IdentityForgery):
        reject_client_supplied_user_id({"user_id": "evil", "score": 5})
    with pytest.raises(IdentityForgery):
        reject_client_supplied_user_id({"actor_id": "x"})
    reject_client_supplied_user_id({"score": 5})


def test_cohort_stable_and_1pct(identity_secret):
    iid = "a" * 32
    b1 = cohort_bucket(iid)
    b2 = cohort_bucket(iid)
    assert b1 == b2
    assert 0 <= b1 < 100
    d0 = decide_cohort(iid, rollout_percent=0)
    assert d0.eligible is False
    # Find an identity that lands in bucket 0 for deterministic eligibility
    found = None
    for i in range(5000):
        cand = f"{i:032x}"
        if cohort_bucket(cand) == 0:
            found = cand
            break
    assert found
    assert decide_cohort(found, rollout_percent=1).eligible is True
    assert decide_cohort(found, rollout_percent=0).eligible is False


def test_native_formula_preview_equals_write(store):
    svc = CommunityVotesService(store)
    subject = f"nova:00000000-cr06-{uuid.uuid4().hex[:8]}"
    actor = f"canary-cr06-{uuid.uuid4().hex[:8]}"
    # first vote
    prev = svc.preview_one(
        rating_space_id="yummy", subject_id=subject, actor_id=actor, score=7, yummy_prior_inputs={}
    )
    assert prev["action"] == "create"
    assert prev["after"] == "7.0"
    put = svc.put_vote(
        idempotency_key=f"k-{uuid.uuid4().hex}",
        rating_space_id="yummy",
        subject_id=subject,
        actor_id=actor,
        score=7,
        yummy_prior_inputs={},
    )
    assert put["after"] == "7.0"
    # normalize: put uses round_display 0.1 — check equality via S/N
    agg = store.get_aggregate(rating_space_id="yummy", subject_id=subject)
    assert int(agg["vote_sum"]) == 7 and int(agg["vote_count"]) == 1
    # update
    prev2 = svc.preview_one(
        rating_space_id="yummy", subject_id=subject, actor_id=actor, score=9, yummy_prior_inputs={}
    )
    put2 = svc.put_vote(
        idempotency_key=f"k-{uuid.uuid4().hex}",
        rating_space_id="yummy",
        subject_id=subject,
        actor_id=actor,
        score=9,
        yummy_prior_inputs={},
    )
    assert prev2["after"] == "9.0"
    assert put2["after"] == "9.0"
    assert int(store.get_aggregate(rating_space_id="yummy", subject_id=subject)["vote_count"]) == 1
    # retract
    svc.delete_vote(
        idempotency_key=f"k-{uuid.uuid4().hex}",
        rating_space_id="yummy",
        subject_id=subject,
        actor_id=actor,
        yummy_prior_inputs={},
    )
    agg3 = store.get_aggregate(rating_space_id="yummy", subject_id=subject)
    assert int(agg3["vote_count"]) == 0 and int(agg3["vote_sum"]) == 0


def test_score_validation():
    from factory.community.service import validate_score

    for bad in (0, 11, -1, 1.5, "7", None, True, [1], {"a": 1}):
        with pytest.raises(CommunityValidationError):
            if isinstance(bad, float):
                validate_score(bad)  # type: ignore[arg-type]
            else:
                validate_score(bad)  # type: ignore[arg-type]
    assert validate_score(10) == 10


def test_public_facade_cohort_and_csrf(store, tmp_flags, identity_secret, monkeypatch):
    enable_1pct_canary()
    # force eligible identity via monkeypatch of decide? better: mint until eligible
    facade = PublicRatingsFacade(CommunityVotesService(store))
    # find eligible
    eligible_id = None
    for i in range(10000):
        cand = f"{i:032x}"
        if decide_cohort(cand, rollout_percent=1).eligible:
            eligible_id = cand
            break
    assert eligible_id
    tok = issue_token(identity_id=eligible_id)
    cookie = f"yummy_cr_vid={tok}"
    csrf = "csrf-test-token"
    cookie2 = cookie + f"; yummy_cr_csrf={csrf}"
    subject = f"nova:00000000-cr06-{uuid.uuid4().hex[:8]}"
    # missing csrf
    bad = facade.mutate(
        method="PUT",
        subject_id=subject,
        body={"score": 8},
        cookie_header=cookie2,
        origin="https://yummyani.site",
        csrf_header="wrong",
        csrf_cookie=csrf,
        idempotency_key=f"idem-{uuid.uuid4().hex}",
        content_type="application/json",
        peer_ip="203.0.113.10",
        body_len=20,
    )
    assert bad["status"] == 403
    # client user id
    bad2 = facade.mutate(
        method="PUT",
        subject_id=subject,
        body={"score": 8, "user_id": "hax"},
        cookie_header=cookie2,
        origin="https://yummyani.site",
        csrf_header=csrf,
        csrf_cookie=csrf,
        idempotency_key=f"idem-{uuid.uuid4().hex}",
        content_type="application/json",
        peer_ip="203.0.113.10",
        body_len=40,
    )
    assert bad2["status"] == 401
    # good write
    ok = facade.mutate(
        method="PUT",
        subject_id=subject,
        body={"score": 8},
        cookie_header=cookie2,
        origin="https://yummyani.site",
        csrf_header=csrf,
        csrf_cookie=csrf,
        idempotency_key=f"idem-{uuid.uuid4().hex}",
        content_type="application/json",
        peer_ip="203.0.113.10",
        body_len=20,
    )
    assert ok["status"] == 200
    assert ok["my_vote"] == 8
    # ineligible denied
    ineligible = None
    for i in range(10000):
        cand = f"{i:032x}"
        if not decide_cohort(cand, rollout_percent=1).eligible:
            ineligible = cand
            break
    tok_i = issue_token(identity_id=ineligible)
    denied = facade.mutate(
        method="PUT",
        subject_id=subject,
        body={"score": 3},
        cookie_header=f"yummy_cr_vid={tok_i}; yummy_cr_csrf={csrf}",
        origin="https://yummyani.site",
        csrf_header=csrf,
        csrf_cookie=csrf,
        idempotency_key=f"idem-{uuid.uuid4().hex}",
        content_type="application/json",
        peer_ip="203.0.113.11",
        body_len=20,
    )
    assert denied["status"] == 403
    assert denied["code"] == "CohortDenied"
    # cleanup
    facade.mutate(
        method="DELETE",
        subject_id=subject,
        body={},
        cookie_header=cookie2,
        origin="https://yummyani.site",
        csrf_header=csrf,
        csrf_cookie=csrf,
        idempotency_key=f"idem-{uuid.uuid4().hex}",
        content_type="application/json",
        peer_ip="203.0.113.10",
        body_len=2,
    )


def test_kill_switch_blocks_writes(store, tmp_flags, identity_secret):
    enable_1pct_canary()
    trigger_kill_switch("test")
    facade = PublicRatingsFacade(CommunityVotesService(store), AntifraudGuard())
    facade.guard.sync_from_rollout()
    eligible = None
    for i in range(10000):
        cand = f"{i:032x}"
        if decide_cohort(cand, rollout_percent=1).eligible:
            eligible = cand
            break
    tok = issue_token(identity_id=eligible)
    csrf = "c"
    out = facade.mutate(
        method="PUT",
        subject_id="nova:x",
        body={"score": 5},
        cookie_header=f"yummy_cr_vid={tok}; yummy_cr_csrf={csrf}",
        origin="https://yummyani.site",
        csrf_header=csrf,
        csrf_cookie=csrf,
        idempotency_key="k1",
        content_type="application/json",
        peer_ip="10.0.0.1",
        body_len=10,
    )
    assert out["status"] == 503


def test_rate_limit_identity(identity_secret):
    guard = AntifraudGuard(
        AntifraudConfig(
            per_identity_max_10m=3,
            rate_limit_max=100,
            burst_max=100,
            title_rate_limit_max=100,
            global_rate_limit_max=1000,
        )
    )
    for _ in range(3):
        guard.check_rate(account_id="", token_id="abc", ip_hmac_prefix="", subject_id="t1")
    with pytest.raises(RateLimited):
        guard.check_rate(account_id="", token_id="abc", ip_hmac_prefix="", subject_id="t1")


def test_concurrent_no_duplicate(store):
    svc = CommunityVotesService(store)
    subject = f"nova:00000000-cr06c-{uuid.uuid4().hex[:8]}"
    actor = f"canary-cr06c-{uuid.uuid4().hex[:8]}"
    key = f"idem-shared-{uuid.uuid4().hex}"

    def once():
        return svc.put_vote(
            idempotency_key=key,
            rating_space_id="yummy",
            subject_id=subject,
            actor_id=actor,
            score=6,
            yummy_prior_inputs={},
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(lambda _: once(), range(8)))
    assert all(r["status"] == 200 for r in results)
    agg = store.get_aggregate(rating_space_id="yummy", subject_id=subject)
    assert int(agg["vote_count"]) == 1
    assert int(agg["vote_sum"]) == 6


def test_cross_space_denied(store, tmp_flags, identity_secret):
    enable_1pct_canary()
    facade = PublicRatingsFacade(CommunityVotesService(store))
    eligible = None
    for i in range(10000):
        cand = f"{i:032x}"
        if decide_cohort(cand, rollout_percent=1).eligible:
            eligible = cand
            break
    tok = issue_token(identity_id=eligible)
    csrf = "c"
    out = facade.mutate(
        method="PUT",
        subject_id="t",
        body={"score": 5, "rating_space_id": "animedia"},
        cookie_header=f"yummy_cr_vid={tok}; yummy_cr_csrf={csrf}",
        origin="https://yummyani.site",
        csrf_header=csrf,
        csrf_cookie=csrf,
        idempotency_key="k",
        content_type="application/json",
        peer_ip="1.2.3.4",
        body_len=50,
        rating_space_id="animedia",
    )
    assert out["status"] == 403


def test_display_one_decimal():
    assert round_display(Decimal("7.44"), "0.1") == Decimal("7.4")
    assert round_display(Decimal("7.45"), "0.1") == Decimal("7.5")


def test_rollout_clamp_max_1pct(tmp_flags):
    flags = RolloutFlags(PUBLIC_WRITE_ENABLED=1, PUBLIC_WRITE_ROLLOUT_PERCENT=50)
    saved = save_flags(flags)
    assert saved.PUBLIC_WRITE_ROLLOUT_PERCENT == 1
    assert saved.PUBLIC_WRITE_MAX_PERCENT == 1
