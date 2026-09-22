"""Unit tests for Site Factory Release Orchestrator core contracts."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from factory.release_orchestrator.approval import (
    ApprovalError,
    assert_usable_for_manifest,
    build_approval,
    consume,
)
from factory.release_orchestrator.distinctness import build_distinctness_matrix
from factory.release_orchestrator.indexability import IndexabilityError, assert_transition_allowed
from factory.release_orchestrator.intake import plan_manifest_from_registry
from factory.release_orchestrator.manifest import (
    DENIED_DIGEST_MISMATCH,
    ManifestError,
    digest_obj,
    validate_manifest_structure,
    verify_immutable,
    write_manifest,
)
from factory.release_orchestrator.privilege import PrivilegeError, parse_runner_argv
from factory.release_orchestrator.registry import ReleaseRegistry, RegistryError, normalize_domain
from factory.release_orchestrator.restart import FakeSystemd, restart_once
from factory.release_orchestrator.rollback import prepare_rollback
from factory.release_orchestrator.runner import run_batch
from factory.release_orchestrator.smoke import compare_runs, dual_smoke, SmokeError, SmokeRun
from factory.release_orchestrator.state import new_checkpoint, pending_sites, save_checkpoint, transition_site


@pytest.fixture
def registry() -> ReleaseRegistry:
    return ReleaseRegistry.load()


def test_exact_domain_lookup_no_tld_fallback(registry: ReleaseRegistry) -> None:
    rec = registry.by_domain("lordfilm47.space")
    assert rec.site_id == "lords-01"
    with pytest.raises(RegistryError):
        registry.by_domain("lordfilm47.org")
    with pytest.raises(RegistryError):
        registry.by_domain("film47.space")  # substring
    assert normalize_domain("https://WWW.lordfilm47.space/path") == "lordfilm47.space"


def test_service_uniqueness_contract(registry: ReleaseRegistry) -> None:
    registry.require_unique_services(["lords-01", "lords-02", "lords-03"])
    # Each site has its own unit.
    assert registry.get("lords-01").service_name != registry.get("lords-02").service_name


def _sample_manifest(registry: ReleaseRegistry, tmp_path: Path, *, n: int = 3) -> dict:
    now = datetime.now(timezone.utc)
    sites = []
    ids = ["lords-01", "lords-02", "lords-03"][:n]
    for sid in ids:
        rec = registry.get(sid)
        art = tmp_path / sid / "artifact"
        art.parent.mkdir(parents=True, exist_ok=True)
        art.write_text("artifact\n", encoding="utf-8")
        sites.append(
            {
                "site_id": sid,
                "domain": rec.domain,
                "source_head": "a" * 40,
                "artifact_path": str(art),
                "artifact_sha256": "b" * 64,
                "manifest_sha256": "c" * 64,
                "template_profile": rec.template_profile,
                "expected_design_id": rec.design_id,
                "expected_build_id": f"build-{sid}",
                "expected_indexability_before": rec.expected_indexability,
                "expected_indexability_after": rec.expected_indexability,
                "expected_catalog_revision": "cat-1",
                "expected_details_revision": "det-1",
                "smoke_profile": rec.smoke_profile,
                "rollback_required": True,
            }
        )
    return {
        "schema_version": "1.0.0",
        "release_id": "rel-test-orchestrator-01",
        "owner_approval_id": None,
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=6)).isoformat(),
        "requested_by": "pytest",
        "release_mode": "shadow",
        "canary_site_id": ids[0],
        "failure_policy": "ROLLBACK_CURRENT_SITE_AND_STOP_BATCH",
        "indexability_mutations_allowed": False,
        "dns_mutations_allowed": False,
        "paid_operations_allowed": False,
        "sites": sites,
    }


def test_manifest_immutable_digest(tmp_path: Path, registry: ReleaseRegistry) -> None:
    manifest = _sample_manifest(registry, tmp_path)
    path = tmp_path / "release.json"
    digest = write_manifest(path, manifest)
    verify_immutable(path, digest)
    # Tamper
    data = json.loads(path.read_text(encoding="utf-8"))
    data["requested_by"] = "tampered"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ManifestError) as exc:
        verify_immutable(path, digest)
    assert exc.value.code == DENIED_DIGEST_MISMATCH


def test_duplicate_site_and_artifact_collision(registry: ReleaseRegistry, tmp_path: Path) -> None:
    manifest = _sample_manifest(registry, tmp_path, n=2)
    manifest["sites"].append(dict(manifest["sites"][0]))
    with pytest.raises(ManifestError):
        validate_manifest_structure(manifest, registry=registry)

    manifest = _sample_manifest(registry, tmp_path, n=2)
    manifest["sites"][1]["artifact_path"] = manifest["sites"][0]["artifact_path"]
    manifest["sites"][1]["artifact_sha256"] = "d" * 64
    with pytest.raises(ManifestError):
        validate_manifest_structure(manifest, registry=registry)


def test_approval_replay_and_expiry(registry: ReleaseRegistry, tmp_path: Path) -> None:
    manifest = _sample_manifest(registry, tmp_path)
    approval = build_approval(
        approval_id="apr-test-0001",
        release_id=manifest["release_id"],
        manifest=manifest,
        approved_by="owner",
        allowed_indexability_changes=False,
        allowed_dns_changes=False,
        allowed_paid_operations=False,
        expires_at=manifest["expires_at"],
    )
    assert_usable_for_manifest(approval, manifest)
    consumed = consume(approval)
    with pytest.raises(ApprovalError):
        assert_usable_for_manifest(consumed, manifest)

    expired = dict(approval)
    expired["expires_at"] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    with pytest.raises(ApprovalError):
        assert_usable_for_manifest(expired, manifest)

    other = dict(manifest)
    other["requested_by"] = "other"
    bad = dict(approval)
    bad["manifest_digest"] = digest_obj(other)
    with pytest.raises(ApprovalError):
        assert_usable_for_manifest(bad, manifest)


def test_runner_rejects_arbitrary_args() -> None:
    with pytest.raises(PrivilegeError):
        parse_runner_argv(["--release-id", "rel-x", "--force"])
    with pytest.raises(PrivilegeError):
        parse_runner_argv(["--service", "nginx.service"])
    req = parse_runner_argv(
        [
            "--release-id",
            "rel-x",
            "--manifest",
            "/tmp/m.json",
            "--manifest-digest",
            "a" * 64,
            "--approval",
            "/tmp/a.json",
        ]
    )
    assert req.release_id == "rel-x"


def test_restart_warning_postconditions_pass_no_duplicate() -> None:
    fake = FakeSystemd()
    fake.units["lords-01.service"] = {
        "ActiveState": "active",
        "SubState": "running",
        "MainPID": "10",
        "ExecMainStartTimestamp": "100",
        "NRestarts": "0",
    }
    fake.restart_stderr_error = True
    result = restart_once(fake, "lords-01.service", sleep_fn=lambda _s: None)
    assert result.restart_command_warning == 1
    assert result.restart_postconditions_pass == 1
    assert result.effective_result == "PASS"
    assert len(fake.restart_calls) == 1


def test_indexability_guards() -> None:
    assert_transition_allowed(before="OPEN", after="OPEN", mutations_allowed=False, site_id="x")
    assert_transition_allowed(before="CLOSED", after="CLOSED", mutations_allowed=False, site_id="x")
    with pytest.raises(IndexabilityError):
        assert_transition_allowed(before="OPEN", after="CLOSED", mutations_allowed=False, site_id="x")
    with pytest.raises(IndexabilityError):
        assert_transition_allowed(before="CLOSED", after="OPEN", mutations_allowed=False, site_id="x")


def test_rollback_rehearsal(tmp_path: Path) -> None:
    live = tmp_path / "live"
    live.mkdir()
    (live / "CURRENT").write_text("build\n", encoding="utf-8")
    (live / "version.json").write_text("{}\n", encoding="utf-8")
    prep = prepare_rollback(site_id="lords-01", live_root=live, backup_root=tmp_path / "bak")
    assert prep.rollback_prepared == 1
    assert prep.rollback_digest_match == 1
    assert prep.rollback_rehearsal_pass == 1


def test_smoke_dual_detects_concurrent_deploy() -> None:
    run1 = SmokeRun("b1", "a" * 64, "d1", {"/": 200}, "CLOSED", "c1")
    run2 = SmokeRun("b2", "a" * 64, "d1", {"/": 200}, "CLOSED", "c1")
    with pytest.raises(SmokeError):
        compare_runs(run1, run2)


def test_concurrency_one(tmp_path: Path) -> None:
    cp = new_checkpoint("rel-x", ["a", "b"])
    transition_site(cp, "a", "PREFLIGHT")
    transition_site(cp, "a", "BUILT")
    transition_site(cp, "a", "ARTIFACT_VERIFIED")
    transition_site(cp, "a", "ROLLBACK_PREPARED")
    transition_site(cp, "a", "STAGED")
    # Move b into staged illegally while a is staged
    transition_site(cp, "b", "PREFLIGHT")
    transition_site(cp, "b", "BUILT")
    transition_site(cp, "b", "ARTIFACT_VERIFIED")
    transition_site(cp, "b", "ROLLBACK_PREPARED")
    with pytest.raises(Exception):
        transition_site(cp, "b", "STAGED")


def test_shadow_batch_lords(tmp_path: Path, registry: ReleaseRegistry) -> None:
    manifest = _sample_manifest(registry, tmp_path, n=3)
    mpath = tmp_path / "manifest.json"
    digest = write_manifest(mpath, manifest)
    approval = build_approval(
        approval_id="apr-shadow-0001",
        release_id=manifest["release_id"],
        manifest=json.loads(mpath.read_text(encoding="utf-8")),
        # reload canonical
        approved_by="owner",
        allowed_indexability_changes=False,
        allowed_dns_changes=False,
        allowed_paid_operations=False,
        expires_at=manifest["expires_at"],
    )
    # Re-bind to canonical file digest
    canonical = json.loads(mpath.read_text(encoding="utf-8"))
    approval["manifest_digest"] = digest_obj(canonical)
    apath = tmp_path / "approval.json"
    apath.write_text(json.dumps(approval), encoding="utf-8")

    result = run_batch(
        release_id=manifest["release_id"],
        manifest_path=mpath,
        manifest_digest=digest,
        approval_path=apath,
        report_dir=tmp_path / "report",
        work_root=tmp_path / "work",
        registry=registry,
        mutate=False,
        shadow=True,
    )
    assert result.global_state == "BATCH_PASS"
    assert all(v == "POST_DEPLOY_PASS" for v in result.sites.values())

    # Resume idempotent after CONSUMED: no duplicate deploy/restart.
    result2 = run_batch(
        release_id=manifest["release_id"],
        manifest_path=mpath,
        manifest_digest=digest,
        approval_path=apath,
        report_dir=tmp_path / "report",
        work_root=tmp_path / "work",
        registry=registry,
        mutate=False,
        shadow=True,
    )
    assert result2.global_state == "BATCH_PASS"
    assert json.loads(apath.read_text(encoding="utf-8"))["state"] == "CONSUMED"


def test_distinctness_rejects_clones() -> None:
    sites = [
        {"site_id": "a", "data_design": "same", "ia": "1", "home_block_order": "1",
         "card_profile": "1", "typography": "1", "geometry": "1", "navigation": "1",
         "title_passport": "1", "recommendations": "1", "footer": "1", "responsive_screenshots": "1"},
        {"site_id": "b", "data_design": "same", "ia": "1", "home_block_order": "1",
         "card_profile": "1", "typography": "1", "geometry": "1", "navigation": "1",
         "title_passport": "1", "recommendations": "1", "footer": "1", "responsive_screenshots": "1"},
    ]
    report = build_distinctness_matrix(sites)
    assert report.ok is False


def test_restart_failure_postconditions() -> None:
    fake = FakeSystemd()
    fake.units["lords-01.service"] = {
        "ActiveState": "active",
        "SubState": "running",
        "MainPID": "10",
        "ExecMainStartTimestamp": "100",
        "NRestarts": "0",
    }
    fake.fail_postconditions = True
    fake.restart_stderr_error = True
    result = restart_once(fake, "lords-01.service", sleep_fn=lambda _s: None, timeout_seconds=0)
    assert result.effective_result == "FAIL"
    assert result.restart_postconditions_pass == 0
    assert result.restart_command_warning == 1


def test_bypass_refuse_env(monkeypatch) -> None:
    from factory.release_orchestrator.bypass import refuse_if_enforced
    import pytest

    monkeypatch.setenv("RELEASE_ORCHESTRATOR_REQUIRED", "1")
    with pytest.raises(SystemExit) as exc:
        refuse_if_enforced("lords-staging-apply.sh")
    assert exc.value.code == 78


def test_global_lock_blocks_second(tmp_path, monkeypatch) -> None:
    from factory.release_orchestrator import locks as locks_mod
    from factory.release_orchestrator.locks import global_release_lock, ReleaseLockBusy

    monkeypatch.setattr(locks_mod, "global_lock_path", lambda: tmp_path / "g.lock")
    with global_release_lock("rel-a"):
        with pytest.raises(ReleaseLockBusy):
            with global_release_lock("rel-b"):
                pass


def test_plan_manifest_uses_registry_domains(registry: ReleaseRegistry, tmp_path: Path) -> None:
    artifacts = {
        "lords-01": {
            "artifact_path": str(tmp_path / "a"),
            "artifact_sha256": "a" * 64,
            "manifest_sha256": "b" * 64,
            "expected_build_id": "b1",
            "expected_catalog_revision": "c1",
            "expected_details_revision": "d1",
        }
    }
    manifest = plan_manifest_from_registry(
        release_id="rel-plan-0001",
        site_ids=["lords-01"],
        canary_site_id="lords-01",
        source_head="e" * 40,
        requested_by="pytest",
        artifacts=artifacts,
        registry=registry,
    )
    assert manifest["sites"][0]["domain"] == "lordfilm47.space"
    assert "service_name" not in manifest["sites"][0]
