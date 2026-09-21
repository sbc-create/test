"""COMMUNITY-RATINGS-08 — live API surfaces the widget depends on.

Covers the end-to-end shapes the browser actually consumes: session bootstrap,
public read, cast/update/retract, the exposure beacon, read-only and kill-switch
fallbacks, and the monitor's inter-process metric source.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path

import pytest

from factory.community import metrics, metrics_store
from factory.community.api import PublicRatingsFacade
from factory.community.cohort import decide_cohort
from factory.community.identity_v1 import issue_token
from factory.community.rollout import (
    RolloutFlags,
    enable_1pct_canary,
    load_flags,
    save_flags,
    trigger_kill_switch,
)
from factory.community.service import CommunityVotesService
from factory.community.store import CommunityStore

CSRF = "csrf-stage08"
ORIGIN = "https://yummyani.site"


@pytest.fixture()
def tmp_flags(tmp_path, monkeypatch):
    p = tmp_path / "flags.json"
    monkeypatch.setenv("COMMUNITY_ROLLOUT_FLAGS_PATH", str(p))
    save_flags(RolloutFlags())
    return p


@pytest.fixture()
def store(tmp_path):
    s = CommunityStore(tmp_path / "cr08.sqlite")
    yield s
    s.close()


@pytest.fixture()
def identity_secret(monkeypatch):
    monkeypatch.setenv("COMMUNITY_IDENTITY_HMAC_SECRET", "test-identity-secret-cr08")
    monkeypatch.setenv("COMMUNITY_ROLLOUT_SALT", "test-rollout-salt-cr08")
    monkeypatch.delenv("COMMUNITY_IDENTITY_HMAC_SECRET_FILE", raising=False)
    monkeypatch.delenv("COMMUNITY_ROLLOUT_SALT_FILE", raising=False)


@pytest.fixture()
def metrics_path(tmp_path, monkeypatch):
    p = tmp_path / "metrics.sqlite"
    monkeypatch.setattr(metrics_store, "DEFAULT_STORE_PATH", p)
    metrics_store.reset_cache()
    metrics.reset_for_tests()
    # Cumulative by design in production; per-test here, or a drop recorded by
    # an earlier test would mark these counters PARTIAL.
    metrics_store.reset_drop_stats()
    yield p
    metrics_store.reset_cache()
    metrics_store.reset_drop_stats()


def _identity(eligible: bool) -> str:
    for i in range(20000):
        cand = f"{i:032x}"
        if decide_cohort(cand, rollout_percent=1).eligible is eligible:
            return cand
    raise AssertionError("no identity found")


def _cookie(identity_id: str) -> str:
    return f"yummy_cr_vid={issue_token(identity_id=identity_id)}; yummy_cr_csrf={CSRF}"


def _write(facade, *, method, subject, cookie, body=None, csrf=CSRF, origin=ORIGIN):
    return facade.mutate(
        method=method,
        subject_id=subject,
        body=body if body is not None else {},
        cookie_header=cookie,
        origin=origin,
        csrf_header=csrf,
        csrf_cookie=CSRF,
        idempotency_key=f"idem-{uuid.uuid4().hex}",
        content_type="application/json",
        peer_ip="203.0.113.20",
        body_len=32,
    )


# --------------------------------------------------------------------------
# session / public read
# --------------------------------------------------------------------------


def test_session_reports_cohort_and_csrf(store, tmp_flags, identity_secret):
    enable_1pct_canary()
    facade = PublicRatingsFacade(CommunityVotesService(store))
    out = facade.session_bootstrap(cookie_header=_cookie(_identity(True)))
    assert out["status"] == 200
    assert out["cohort"]["eligible"] is True
    assert out["cohort"]["rollout_percent"] == 1
    assert out["csrf_token"]
    # The identity id must never leave the server.
    assert "identity_id" not in out["cohort"]
    assert out["_identity_id"] not in json.dumps(
        {k: v for k, v in out.items() if k != "_identity_id"}
    )


def test_session_marks_ineligible_visitor_as_not_eligible(store, tmp_flags, identity_secret):
    enable_1pct_canary()
    facade = PublicRatingsFacade(CommunityVotesService(store))
    out = facade.session_bootstrap(cookie_header=_cookie(_identity(False)))
    assert out["cohort"]["eligible"] is False


def test_public_read_absent_is_a_label_not_zero(store, tmp_flags, identity_secret):
    enable_1pct_canary()
    facade = PublicRatingsFacade(CommunityVotesService(store))
    body = facade.get_public(
        subject_id=f"nova:{uuid.uuid4()}", cookie_header=_cookie(_identity(True))
    )
    assert body["status"] == 200
    assert body["native_vote_count"] == 0
    assert body["native_absent"] is True
    assert body["native_absent_label"] == "Пока нет пользовательских оценок"
    # N=0 must not surface as a score of any kind.
    assert body.get("native_user_average") in (None, "")
    assert body["public_brand_score"] in (None, "")


def test_public_read_never_exposes_external_scores(store, tmp_flags, identity_secret):
    enable_1pct_canary()
    facade = PublicRatingsFacade(CommunityVotesService(store))
    body = facade.get_public(
        subject_id=f"nova:{uuid.uuid4()}", cookie_header=_cookie(_identity(True))
    )
    assert body["public_score_mode"] == "NATIVE_ONLY"
    blob = json.dumps(body, ensure_ascii=False).lower()
    assert "shikimori" not in blob
    assert "aggregaterating" not in blob


def test_writes_ui_enabled_tracks_eligibility(store, tmp_flags, identity_secret):
    enable_1pct_canary()
    facade = PublicRatingsFacade(CommunityVotesService(store))
    subject = f"nova:{uuid.uuid4()}"
    yes = facade.get_public(subject_id=subject, cookie_header=_cookie(_identity(True)))
    no = facade.get_public(subject_id=subject, cookie_header=_cookie(_identity(False)))
    assert yes["writes_ui_enabled"] is True
    assert no["writes_ui_enabled"] is False


def test_read_only_flag_disables_the_write_ui(store, tmp_flags, identity_secret):
    enable_1pct_canary()
    flags = load_flags()
    flags.READ_ONLY = 1
    save_flags(flags)
    facade = PublicRatingsFacade(CommunityVotesService(store))
    body = facade.get_public(
        subject_id=f"nova:{uuid.uuid4()}", cookie_header=_cookie(_identity(True))
    )
    # Read still works; the control is withdrawn rather than left to fail.
    assert body["status"] == 200
    assert body["writes_ui_enabled"] is False


def test_kill_switch_withdraws_the_write_ui(store, tmp_flags, identity_secret):
    enable_1pct_canary()
    trigger_kill_switch("test")
    facade = PublicRatingsFacade(CommunityVotesService(store))
    body = facade.get_public(
        subject_id=f"nova:{uuid.uuid4()}", cookie_header=_cookie(_identity(True))
    )
    assert body["writes_ui_enabled"] is False
    assert body["cohort"]["rollout_percent"] == 0


# --------------------------------------------------------------------------
# cast / update / retract
# --------------------------------------------------------------------------


def test_cast_update_retract_round_trip(store, tmp_flags, identity_secret):
    enable_1pct_canary()
    facade = PublicRatingsFacade(CommunityVotesService(store))
    cookie = _cookie(_identity(True))
    subject = f"nova:{uuid.uuid4()}"

    cast = _write(facade, method="PUT", subject=subject, cookie=cookie, body={"score": 7})
    assert cast["status"] == 200 and cast["action"] == "CREATE"
    assert cast["my_vote"] == 7 and cast["native_vote_count"] == 1

    upd = _write(facade, method="PUT", subject=subject, cookie=cookie, body={"score": 9})
    assert upd["action"] == "UPDATE"
    assert upd["my_vote"] == 9
    # A second vote replaces the first — it never becomes a second active vote.
    assert upd["native_vote_count"] == 1

    ret = _write(facade, method="DELETE", subject=subject, cookie=cookie)
    assert ret["status"] == 200
    assert ret["my_vote"] is None
    assert ret["native_vote_count"] == 0
    assert ret.get("native_absent") is True


def test_repeat_vote_leaves_one_active_row(store, tmp_flags, identity_secret):
    enable_1pct_canary()
    facade = PublicRatingsFacade(CommunityVotesService(store))
    cookie = _cookie(_identity(True))
    subject = f"nova:{uuid.uuid4()}"
    for score in (3, 5, 8, 8, 1):
        _write(facade, method="PUT", subject=subject, cookie=cookie, body={"score": score})
    rows = store.conn.execute(
        "SELECT COUNT(*) AS c FROM community_votes WHERE subject_id=? AND status='ACCEPTED'",
        (subject,),
    ).fetchone()["c"]
    assert rows == 1


def test_preview_matches_the_write_it_predicts(store, tmp_flags, identity_secret):
    enable_1pct_canary()
    facade = PublicRatingsFacade(CommunityVotesService(store))
    cookie = _cookie(_identity(True))
    subject = f"nova:{uuid.uuid4()}"
    for score in (1, 4, 7, 10):
        preview = facade.preview(subject_id=subject, score=score, cookie_header=cookie)
        assert preview["status"] == 200
        write = _write(facade, method="PUT", subject=subject, cookie=cookie, body={"score": score})
        assert write["status"] == 200
        assert str(write["after"]) == str(preview["after"]), score
    _write(facade, method="DELETE", subject=subject, cookie=cookie)


def test_retract_of_the_only_vote_returns_to_absent(store, tmp_flags, identity_secret):
    enable_1pct_canary()
    facade = PublicRatingsFacade(CommunityVotesService(store))
    cookie = _cookie(_identity(True))
    subject = f"nova:{uuid.uuid4()}"
    _write(facade, method="PUT", subject=subject, cookie=cookie, body={"score": 6})
    _write(facade, method="DELETE", subject=subject, cookie=cookie)
    body = facade.get_public(subject_id=subject, cookie_header=cookie)
    assert body["native_absent"] is True
    assert body["native_vote_count"] == 0
    assert body["native_absent_label"] == "Пока нет пользовательских оценок"


# --------------------------------------------------------------------------
# exposure beacon
# --------------------------------------------------------------------------


def test_beacon_counts_only_eligible_visitors(store, tmp_flags, identity_secret, metrics_path):
    enable_1pct_canary()
    facade = PublicRatingsFacade(CommunityVotesService(store))

    denied = facade.widget_event(event="rendered", cookie_header=_cookie(_identity(False)))
    assert denied["status"] == 403
    assert denied["code"] == "CohortDenied"

    ok = facade.widget_event(event="rendered", cookie_header=_cookie(_identity(True)))
    assert ok["status"] == 200

    metrics_store.reset_cache()
    raw = metrics_store.read_raw(metrics_path)
    assert raw["counters"]["widget_rendered"] == 1
    assert raw["uniques"]["exposed_visitor"] == 1


def test_beacon_rejects_unknown_events(store, tmp_flags, identity_secret, metrics_path):
    enable_1pct_canary()
    facade = PublicRatingsFacade(CommunityVotesService(store))
    out = facade.widget_event(event="clicked", cookie_header=_cookie(_identity(True)))
    assert out["status"] == 400


def test_beacon_is_dead_while_kill_switch_is_on(store, tmp_flags, identity_secret, metrics_path):
    enable_1pct_canary()
    trigger_kill_switch("test")
    facade = PublicRatingsFacade(CommunityVotesService(store))
    out = facade.widget_event(event="rendered", cookie_header=_cookie(_identity(True)))
    assert out["status"] == 403


def test_exposure_counters_land_in_the_durable_store(store, tmp_flags, identity_secret, metrics_path):
    enable_1pct_canary()
    facade = PublicRatingsFacade(CommunityVotesService(store))
    facade.session_bootstrap(cookie_header=_cookie(_identity(True)))
    facade.session_bootstrap(cookie_header=_cookie(_identity(False)))

    metrics_store.reset_cache()
    snap = metrics_store.snapshot(path=metrics_path)
    assert snap["metrics"]["session_bootstraps"] == 2
    assert snap["metrics"]["eligible_cohort_impressions"] == 1
    assert snap["metrics"]["exposed_visitors"] == 1


# --------------------------------------------------------------------------
# monitor: inter-process source, and UNMEASURED that cannot become 0
# --------------------------------------------------------------------------


def test_monitor_reads_the_store_not_its_own_counters(tmp_path, monkeypatch, metrics_path):
    """The COMMUNITY-RATINGS-07 regression test.

    A writer increments the store; a *reader that has incremented nothing*
    must still see the writer's numbers. Before the fix the reader saw zeros.
    """
    metrics_store.incr("cast_accepted", 4, path=metrics_path)
    metrics_store.incr("session_bootstraps", 9, path=metrics_path)

    metrics.reset_for_tests()  # the reader's own in-memory counters are empty
    assert metrics.snapshot()["cast_accepted"] == 0

    metrics_store.reset_cache()
    snap = metrics_store.snapshot(path=metrics_path)
    assert snap["metrics"]["accepted_casts"] == 4
    assert snap["metrics"]["session_bootstraps"] == 9
    assert snap["provenance"]["accepted_casts"]["source"] == "metrics_store"


def test_monitor_tick_publishes_provenance_and_unmeasured(tmp_path, monkeypatch, metrics_path):
    from factory.community import monitor_once

    db = tmp_path / "ratings.sqlite"
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
        CREATE TABLE community_votes (rating_space_id TEXT, subject_id TEXT, actor_id TEXT,
            dimension TEXT DEFAULT 'overall', score INTEGER, status TEXT);
        CREATE TABLE community_aggregates (rating_space_id TEXT, subject_id TEXT,
            dimension TEXT DEFAULT 'overall', vote_sum INTEGER, vote_count INTEGER);
        """
    )
    conn.commit()
    conn.close()

    reports = tmp_path / "monitor"
    monkeypatch.setattr(monitor_once, "REPORT_DIR", reports)
    monkeypatch.setattr(monitor_once, "resolve_canonical_db", lambda: str(db))
    monkeypatch.setenv("COMMUNITY_ROLLOUT_FLAGS_PATH", str(tmp_path / "flags.json"))
    save_flags(RolloutFlags(PUBLIC_WRITE_ENABLED=1, PUBLIC_WRITE_ROLLOUT_PERCENT=1))

    metrics_store.incr("session_bootstraps", 3, path=metrics_path)
    metrics_store.reset_cache()

    report = monitor_once.run()

    assert report["metrics_source"].startswith("metrics_store")
    assert report["metrics_store_reachable"] is True
    assert report["metrics"]["session_bootstraps"] == 3
    # Nothing ever recorded these, so they are unmeasured — never zero.
    assert report["metrics"]["rate_limit_violations"] == metrics_store.UNMEASURED
    assert "rate_limit_violations" in report["UNMEASURED_METRICS"]
    for name in report["UNMEASURED_METRICS"]:
        assert report["metrics"][name] != 0
    assert report["metrics_provenance"]["session_bootstraps"]["status"] == "MEASURED"


def test_monitor_reports_unmeasured_when_store_is_missing(tmp_path, monkeypatch):
    from factory.community import monitor_once

    db = tmp_path / "ratings.sqlite"
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
        CREATE TABLE community_votes (rating_space_id TEXT, subject_id TEXT, actor_id TEXT,
            dimension TEXT DEFAULT 'overall', score INTEGER, status TEXT);
        CREATE TABLE community_aggregates (rating_space_id TEXT, subject_id TEXT,
            dimension TEXT DEFAULT 'overall', vote_sum INTEGER, vote_count INTEGER);
        """
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(monitor_once, "REPORT_DIR", tmp_path / "monitor")
    monkeypatch.setattr(monitor_once, "resolve_canonical_db", lambda: str(db))
    monkeypatch.setattr(metrics_store, "DEFAULT_STORE_PATH", tmp_path / "absent.sqlite")
    metrics_store.reset_cache()
    monkeypatch.setenv("COMMUNITY_ROLLOUT_FLAGS_PATH", str(tmp_path / "flags.json"))
    save_flags(RolloutFlags(PUBLIC_WRITE_ENABLED=1, PUBLIC_WRITE_ROLLOUT_PERCENT=1))

    report = monitor_once.run()

    assert report["metrics_store_reachable"] is False
    assert report["metrics"]["cast_attempts"] == metrics_store.UNMEASURED
    # An unreachable source must never be summarised as a healthy zero.
    assert report["metrics"]["accepted_casts"] != 0
    # The ledger-derived gates still work, because they have their own source.
    assert report["SQLITE_INTEGRITY_CHECK"] == "ok"
    assert report["DUPLICATE_ACTIVE_VOTES"] == 0
    assert report["KILL_SWITCH_TRIGGERED"] == 0


def test_monitor_kills_on_duplicate_active_votes(tmp_path, monkeypatch, metrics_path):
    from factory.community import monitor_once

    db = tmp_path / "ratings.sqlite"
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
        CREATE TABLE community_votes (rating_space_id TEXT, subject_id TEXT, actor_id TEXT,
            dimension TEXT DEFAULT 'overall', score INTEGER, status TEXT);
        CREATE TABLE community_aggregates (rating_space_id TEXT, subject_id TEXT,
            dimension TEXT DEFAULT 'overall', vote_sum INTEGER, vote_count INTEGER);
        INSERT INTO community_votes VALUES ('yummy','s','a','overall',5,'ACCEPTED');
        INSERT INTO community_votes VALUES ('yummy','s','a','overall',6,'ACCEPTED');
        """
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(monitor_once, "REPORT_DIR", tmp_path / "monitor")
    monkeypatch.setattr(monitor_once, "resolve_canonical_db", lambda: str(db))
    monkeypatch.setenv("COMMUNITY_ROLLOUT_FLAGS_PATH", str(tmp_path / "flags.json"))
    save_flags(RolloutFlags(PUBLIC_WRITE_ENABLED=1, PUBLIC_WRITE_ROLLOUT_PERCENT=1))

    report = monitor_once.run()
    # One (space, subject, actor, dimension) key holds two active votes: the
    # metric counts offending keys, not offending rows.
    assert report["DUPLICATE_ACTIVE_VOTES"] == 1
    assert report["KILL_SWITCH_TRIGGERED"] == 1
    assert report["KILL_SWITCH_REASON"] == "DUPLICATE_ACTIVE_VOTES"
    assert load_flags().KILL_SWITCH == 1
