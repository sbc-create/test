"""Audit append-only + durable state: локи, идемпотентность, квоты, карантин."""
import json
import sqlite3

import pytest


def test_audit_chain_is_verifiable(audit):
    for i in range(5):
        audit.append(actor="test", action=f"a{i}", payload={"i": i}, site_id="demo-fixture")
    ok, msg = audit.verify_chain()
    assert ok, msg


def test_audit_update_is_rejected_by_database(audit):
    audit.append(actor="test", action="a", payload={})
    with pytest.raises(sqlite3.IntegrityError):
        audit._conn.execute("UPDATE audit SET action='tampered' WHERE seq=1")


def test_audit_delete_is_rejected_by_database(audit):
    audit.append(actor="test", action="a", payload={})
    with pytest.raises(sqlite3.IntegrityError):
        audit._conn.execute("DELETE FROM audit WHERE seq=1")


def test_tampering_breaks_chain_detection(audit):
    audit.append(actor="test", action="a", payload={"x": 1})
    audit.append(actor="test", action="b", payload={"x": 2})
    # Обход триггера напрямую по файлу — цепочка всё равно ловит подмену.
    audit._conn.execute("DROP TRIGGER audit_no_update")
    audit._conn.execute("UPDATE audit SET payload=? WHERE seq=1", (json.dumps({"x": 999}),))
    audit._conn.commit()
    ok, msg = audit.verify_chain()
    assert not ok and "seq=1" in msg


@pytest.mark.parametrize("payload,expected_redacted", [
    ({"api_key": "abcdef123456"}, True),
    ({"oauth_token": "y0_secretvalue"}, True),
    ({"password": "hunter2"}, True),
    ({"secret_ref": "secret://cms/operator"}, False),
    ({"site_id": "demo-fixture"}, False),
])
def test_secrets_are_redacted_before_write(audit, payload, expected_redacted):
    rec = audit.append(actor="test", action="x", payload=payload)
    values = list(rec.payload.values())
    assert ("***REDACTED***" in values) is expected_redacted


def test_token_shaped_string_is_redacted(audit):
    # Собираем по частям, чтобы в репозитории не лежал литерал, похожий на настоящий токен
    # (иначе `seo secrets check` справедливо ругался бы на собственные тесты).
    fake = "gh" + "p_" + "abcdefghijklmnopqrstuvwxyz012345"
    rec = audit.append(actor="test", action="x", payload={"note": f"использован {fake}"})
    assert fake not in rec.payload["note"]
    assert "***REDACTED***" in rec.payload["note"]


# --- state --------------------------------------------------------------------

def test_job_enqueue_is_idempotent(store):
    from seo_operator.state import Job
    job = Job(job_key="collect:demo:2026-08-22", kind="collect", payload={})
    assert store.enqueue(job) is True
    assert store.enqueue(job) is False
    assert store.pending_job_count() == 1


def test_transient_failure_retries_then_quarantines(store):
    from seo_operator.state import Job
    store.enqueue(Job(job_key="j1", kind="collect", payload={}, max_attempts=3))
    row = store.claim_job()
    assert store.fail_job(row["id"], "timeout", transient=True) == "pending"
    assert store.fail_job(row["id"], "timeout", transient=True) == "pending"
    assert store.fail_job(row["id"], "timeout", transient=True) == "quarantined"


def test_auth_failure_quarantines_immediately(store):
    from seo_operator.state import Job
    store.enqueue(Job(job_key="j2", kind="collect", payload={}))
    row = store.claim_job()
    # Права/политика/схема не чинятся повтором — бесконечный retry только жжёт квоту.
    assert store.fail_job(row["id"], "403 forbidden", transient=False) == "quarantined"
    assert len(store.quarantined_jobs()) == 1


def test_lock_is_exclusive(store):
    with store.lock("site:demo-fixture") as first:
        assert first is True
        with store.lock("site:demo-fixture") as second:
            assert second is False
    with store.lock("site:demo-fixture") as third:
        assert third is True


def test_quota_budget_is_enforced(store):
    for _ in range(3):
        assert store.consume_quota("yandex_recrawl", "demo-fixture", budget=3) is True
    assert store.consume_quota("yandex_recrawl", "demo-fixture", budget=3) is False


def test_blocker_is_reported_once(store):
    assert store.record_blocker("fp1", "authorization", "нет manifest", {}) is True
    assert store.record_blocker("fp1", "authorization", "нет manifest", {}) is False
    assert len(store.unreported_blockers()) == 1
    store.mark_blockers_reported()
    assert store.unreported_blockers() == []


def test_observation_records_freshness_metadata(store):
    store.record_observation(
        site_id="demo-fixture", source="gsc", metric="clicks", value=100.0,
        observed_date="2026-08-01", timezone_name="Europe/Moscow",
        source_window="2026-07-01..2026-08-01", data_freshness="complete_through=2026-08-01",
        completeness=1.0)
    rows = store.observations("demo-fixture", "clicks")
    assert rows[0]["completeness"] == 1.0
    assert rows[0]["timezone"] == "Europe/Moscow"


def test_incomplete_observations_filtered_out(store):
    store.record_observation(
        site_id="demo-fixture", source="gsc", metric="clicks", value=5.0,
        observed_date="2026-08-22", timezone_name="UTC", source_window="w",
        data_freshness="partial", completeness=0.3)
    assert store.observations("demo-fixture", "clicks", min_completeness=0.9) == []
