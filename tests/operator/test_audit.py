"""Audit, snapshot and rollback tests."""

from __future__ import annotations

import pytest

from seo_operator.audit import (
    AuditLog,
    Change,
    ChangeKind,
    ConflictError,
    apply_rollback,
    protect_tenant_fields,
)


def make_change(**kw):
    defaults = {
        "site_id": "site-a",
        "entity_id": "title-1001",
        "kind": ChangeKind.TITLE,
        "field_name": "title",
        "before": "Старое название",
        "after": "Новое название",
        "reason": "CTR ниже медианы рубрики",
    }
    defaults.update(kw)
    return Change(**defaults)


def test_change_requires_a_reason():
    with pytest.raises(ValueError, match="reason"):
        make_change(reason="")


def test_noop_change_is_rejected():
    with pytest.raises(ValueError, match="no-op"):
        make_change(before="одно и то же", after="одно и то же")


def test_rollback_payload_restores_the_before_value():
    change = make_change()
    payload = change.rollback_payload
    assert payload["restore_value"] == "Старое название"
    assert apply_rollback(payload, current_value="Новое название") == "Старое название"


def test_rollback_refuses_to_clobber_a_newer_human_edit():
    change = make_change()
    with pytest.raises(ConflictError):
        apply_rollback(change.rollback_payload, current_value="Правка редактора")


def test_non_strict_rollback_can_force():
    change = make_change()
    assert (
        apply_rollback(change.rollback_payload, current_value="Правка", strict=False)
        == "Старое название"
    )


def test_record_carries_before_after_and_experiment():
    change = make_change(experiment_id="exp-001")
    record = change.to_record()
    assert record["before"]["value"] == "Старое название"
    assert record["after"]["value"] == "Новое название"
    assert record["experiment_id"] == "exp-001"
    assert record["rollback_payload"]["restore_value"] == "Старое название"
    assert record["before"]["digest"] != record["after"]["digest"]


def test_audit_log_roundtrip(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    log.append(make_change(experiment_id="exp-001").to_record())
    log.append(make_change(entity_id="t-2", experiment_id="exp-002").to_record())
    assert len(log.records()) == 2
    assert len(log.by_experiment("exp-001")) == 1


def test_audit_log_survives_restart(tmp_path):
    path = tmp_path / "audit.jsonl"
    AuditLog(path).append(make_change().to_record())
    assert len(AuditLog(path).records()) == 1  # fresh instance, same file


class TestTenantFieldProtection:
    def test_manual_fields_survive_sync(self):
        existing = {"title": "Ручной заголовок редактора", "duration": 1200}
        incoming = {"title": "Catalogue Title", "duration": 1400}
        merged = protect_tenant_fields(incoming, existing)
        assert merged["title"] == "Ручной заголовок редактора"
        assert merged["duration"] == 1400  # non-editorial field syncs freely

    def test_empty_manual_field_is_filled_by_sync(self):
        merged = protect_tenant_fields({"title": "Catalogue"}, {"title": ""})
        assert merged["title"] == "Catalogue"

    def test_new_fields_are_added(self):
        merged = protect_tenant_fields({"season": 2}, {"title": "Ручной"})
        assert merged["season"] == 2
        assert merged["title"] == "Ручной"
