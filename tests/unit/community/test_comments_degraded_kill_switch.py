"""Degraded mode + kill switch drill tests."""

from __future__ import annotations

from factory.community.comments.degraded import DegradedController, SlaConfig
from factory.community.comments.kill_switch import (
    KillSwitchCapabilities,
    drill_and_restore,
    load_capabilities,
    save_capabilities,
)
from factory.community.comments import states
from factory.community.store import CommunityStore


def test_sla_defaults():
    s = SlaConfig()
    assert s.target_latency_sec == 120
    assert s.degraded_threshold_sec == 300
    assert s.critical_oldest_sec == 600


def test_not_degraded_when_healthy():
    ctl = DegradedController()
    assert ctl.should_accept_as_degraded(0, 10, circuit_open=False, schema_mismatch_rate=0.0) is False
    assert ctl.initial_status_for_new_comment(queue_depth=0, oldest_age=10) == states.PUBLISHED_UNREVIEWED


def test_degraded_on_oldest_age():
    ctl = DegradedController()
    assert ctl.should_accept_as_degraded(1, 301) is True
    assert ctl.should_accept_as_degraded(1, 600) is True
    assert ctl.initial_status_for_new_comment(queue_depth=1, oldest_age=400) == (
        states.PENDING_MODERATION_DEGRADED
    )


def test_degraded_on_circuit_and_queue():
    ctl = DegradedController()
    assert ctl.should_accept_as_degraded(0, 0, circuit_open=True) is True
    assert ctl.should_accept_as_degraded(50, 0) is True


def test_degraded_on_schema_mismatch_rate():
    ctl = DegradedController()
    for _ in range(4):
        ctl.record_schema_mismatch()
    assert ctl.should_accept_as_degraded(0, 0, schema_mismatch_rate=ctl.schema_mismatch_rate) is True


def test_kill_switch_drill_and_restore(tmp_path, monkeypatch):
    flags = tmp_path / "ks.json"
    audit = tmp_path / "ks_audit.jsonl"
    monkeypatch.setenv("COMMUNITY_COMMENTS_KILL_SWITCH_PATH", str(flags))
    monkeypatch.setenv("COMMUNITY_COMMENTS_KILL_SWITCH_AUDIT_PATH", str(audit))
    store = CommunityStore(tmp_path / "ks.sqlite")
    result = drill_and_restore(path=flags, store=store, actor="test")
    assert result["restored"] is True
    assert result["engaged"]["block_writes"] == 1
    assert result["engaged"]["stop_worker"] == 1
    assert result["engaged"]["hide_module"] == 1
    assert result["engaged"]["keep_reading_approved"] == 1
    after = load_capabilities(flags)
    assert after.block_writes == 0
    assert after.stop_worker == 0
    assert after.hide_module == 0
    assert after.keep_reading_approved == 1
    assert audit.is_file()
    lines = audit.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 2
    n = store.conn.execute(
        "SELECT COUNT(*) AS n FROM community_comment_kill_switch_audit"
    ).fetchone()["n"]
    assert n >= 2
    store.close()


def test_save_capabilities_roundtrip(tmp_path, monkeypatch):
    flags = tmp_path / "ks2.json"
    monkeypatch.setenv("COMMUNITY_COMMENTS_KILL_SWITCH_PATH", str(flags))
    monkeypatch.setenv(
        "COMMUNITY_COMMENTS_KILL_SWITCH_AUDIT_PATH", str(tmp_path / "a2.jsonl")
    )
    caps = KillSwitchCapabilities(block_writes=1, hide_new_public=1, reason="manual")
    save_capabilities(caps, flags, actor="ops")
    loaded = load_capabilities(flags)
    assert loaded.block_writes == 1
    assert loaded.hide_new_public == 1
