"""Resilience contracts for the Release Orchestrator.

Covers the properties a live canary depends on and that the core contract
suite does not assert: crash resume from a mid-site stage, idempotency of a
repeated run, atomicity of the checkpoint write, and behaviour under
"Too many open files" (EMFILE / inotify exhaustion).
"""

from __future__ import annotations

import errno
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from factory.release_orchestrator import inotify_diag
from factory.release_orchestrator import runner as runner_mod
from factory.release_orchestrator.approval import build_approval
from factory.release_orchestrator.bypass import ENFORCE_ENV, refuse_if_enforced
from factory.release_orchestrator.manifest import digest_obj, write_manifest
from factory.release_orchestrator.registry import ReleaseRegistry, RegistryError, normalize_domain
from factory.release_orchestrator.restart import FakeSystemd, restart_once
from factory.release_orchestrator.rollback import prepare_rollback, restore_from_backup
from factory.release_orchestrator.runner import run_batch
from factory.release_orchestrator.service_binding import (
    ServiceBindingError,
    assert_live_binding,
    resolve_bindings,
)
from factory.release_orchestrator.state import (
    StateError,
    atomic_write_json,
    load_checkpoint,
    new_checkpoint,
    pending_sites,
    save_checkpoint,
    transition_site,
)


@pytest.fixture
def registry() -> ReleaseRegistry:
    return ReleaseRegistry.load()


def _manifest(registry: ReleaseRegistry, tmp_path: Path, *, n: int = 3) -> dict:
    now = datetime.now(timezone.utc)
    ids = ["lords-01", "lords-02", "lords-03"][:n]
    sites = []
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
        "release_id": "rel-resilience-01",
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


def _staged(registry: ReleaseRegistry, tmp_path: Path, *, n: int = 3) -> tuple[Path, str, Path, dict]:
    """Write manifest + ACTIVE approval; return (manifest_path, digest, approval_path, manifest)."""
    manifest = _manifest(registry, tmp_path, n=n)
    mpath = tmp_path / "manifest.json"
    digest = write_manifest(mpath, manifest)
    canonical = json.loads(mpath.read_text(encoding="utf-8"))
    approval = build_approval(
        approval_id="apr-resilience-0001",
        release_id=manifest["release_id"],
        manifest=canonical,
        approved_by="owner",
        allowed_indexability_changes=False,
        allowed_dns_changes=False,
        allowed_paid_operations=False,
        expires_at=manifest["expires_at"],
    )
    approval["manifest_digest"] = digest_obj(canonical)
    apath = tmp_path / "approval.json"
    apath.write_text(json.dumps(approval), encoding="utf-8")
    return mpath, digest, apath, canonical


# --------------------------------------------------------------------------
# Crash resume
# --------------------------------------------------------------------------


def test_crash_resume_skips_passed_site_and_never_restarts_it(
    registry: ReleaseRegistry, tmp_path: Path
) -> None:
    """A site already at POST_DEPLOY_PASS must not be touched again on resume."""
    mpath, digest, apath, manifest = _staged(registry, tmp_path)
    report = tmp_path / "report"
    report.mkdir()

    # Simulate a crash after the canary passed and lords-02 reached STAGED.
    order = ["lords-01", "lords-02", "lords-03"]
    cp = new_checkpoint(manifest["release_id"], order)
    for stage in ("PREFLIGHT", "BUILT", "ARTIFACT_VERIFIED", "ROLLBACK_PREPARED",
                  "STAGED", "RESTART_REQUESTED", "RUNTIME_WAIT", "RUNTIME_VERIFIED",
                  "SMOKE_RUN_1", "SMOKE_RUN_2", "POST_DEPLOY_PASS"):
        transition_site(cp, "lords-01", stage)
    save_checkpoint(report / "checkpoint.json", cp)

    fake = FakeSystemd()
    result = run_batch(
        release_id=manifest["release_id"],
        manifest_path=mpath,
        manifest_digest=digest,
        approval_path=apath,
        report_dir=report,
        work_root=tmp_path / "work",
        registry=registry,
        systemd=fake,
        mutate=False,
        shadow=True,
    )

    assert result.global_state == "BATCH_PASS"
    assert result.sites["lords-01"] == "POST_DEPLOY_PASS"
    canary_unit = registry.get("lords-01").service_name
    assert canary_unit not in fake.restart_calls, "resume re-restarted an already passed site"
    # The two pending sites were each restarted exactly once.
    assert sorted(fake.restart_calls) == sorted(
        [registry.get("lords-02").service_name, registry.get("lords-03").service_name]
    )


def test_pending_sites_excludes_terminal_stages() -> None:
    """The resume filter itself, independent of the stage ladder that also guards it."""
    order = ["lords-01", "lords-02", "lords-03"]
    cp = new_checkpoint("rel-x", order)
    assert pending_sites(cp, order) == order

    for stage in ("PREFLIGHT", "BUILT", "ARTIFACT_VERIFIED", "ROLLBACK_PREPARED",
                  "STAGED", "RESTART_REQUESTED", "RUNTIME_WAIT", "RUNTIME_VERIFIED",
                  "SMOKE_RUN_1", "SMOKE_RUN_2", "POST_DEPLOY_PASS"):
        transition_site(cp, "lords-01", stage)
    transition_site(cp, "lords-02", "FAILED")
    transition_site(cp, "lords-02", "ROLLED_BACK")

    # Passed and rolled-back sites are done; only lords-03 still needs work.
    assert pending_sites(cp, order) == ["lords-03"]


def test_crash_resume_continues_site_from_mid_stage(
    registry: ReleaseRegistry, tmp_path: Path
) -> None:
    """A site interrupted at STAGED resumes there, not from PLANNED."""
    mpath, digest, apath, manifest = _staged(registry, tmp_path, n=2)
    report = tmp_path / "report"
    report.mkdir()

    order = ["lords-01", "lords-02"]
    cp = new_checkpoint(manifest["release_id"], order)
    # Canary interrupted mid-site, with its rollback backup already recorded.
    live = tmp_path / "work" / "lords-01" / "live"
    live.mkdir(parents=True)
    (live / "CURRENT").write_text("build-lords-01\n", encoding="utf-8")
    (live / "version.json").write_text('{"build_id": "build-lords-01"}\n', encoding="utf-8")
    prep = prepare_rollback(
        site_id="lords-01", live_root=live, backup_root=tmp_path / "work" / "backups"
    )
    for stage in ("PREFLIGHT", "BUILT", "ARTIFACT_VERIFIED"):
        transition_site(cp, "lords-01", stage)
    transition_site(cp, "lords-01", "ROLLBACK_PREPARED", backup=prep.backup_path)
    transition_site(cp, "lords-01", "STAGED")
    save_checkpoint(report / "checkpoint.json", cp)

    fake = FakeSystemd()
    result = run_batch(
        release_id=manifest["release_id"],
        manifest_path=mpath,
        manifest_digest=digest,
        approval_path=apath,
        report_dir=report,
        work_root=tmp_path / "work",
        registry=registry,
        systemd=fake,
        mutate=False,
        shadow=True,
    )

    assert result.global_state == "BATCH_PASS"
    # Exactly one restart per site — the interrupted one was not restarted twice.
    assert len(fake.restart_calls) == 2
    assert fake.restart_calls.count(registry.get("lords-01").service_name) == 1

    reloaded = load_checkpoint(report / "checkpoint.json")
    assert reloaded.sites["lords-01"].stage == "POST_DEPLOY_PASS"
    # The stage ladder was not replayed from the beginning.
    replayed = [
        e for e in reloaded.events
        if e.get("site_id") == "lords-01" and e.get("stage") == "PREFLIGHT"
    ]
    assert len(replayed) == 1


# --------------------------------------------------------------------------
# Idempotency
# --------------------------------------------------------------------------


def test_repeated_run_is_idempotent_no_second_restart(
    registry: ReleaseRegistry, tmp_path: Path
) -> None:
    """Running a completed batch again performs no deploy, restart or state change."""
    mpath, digest, apath, manifest = _staged(registry, tmp_path)
    report = tmp_path / "report"
    fake = FakeSystemd()
    common = dict(
        release_id=manifest["release_id"],
        manifest_path=mpath,
        manifest_digest=digest,
        approval_path=apath,
        report_dir=report,
        work_root=tmp_path / "work",
        registry=registry,
        systemd=fake,
        mutate=False,
        shadow=True,
    )

    first = run_batch(**common)
    assert first.global_state == "BATCH_PASS"
    calls_after_first = list(fake.restart_calls)
    checkpoint_after_first = (report / "checkpoint.json").read_text(encoding="utf-8")
    assert len(calls_after_first) == 3

    second = run_batch(**common)
    assert second.global_state == "BATCH_PASS"
    assert fake.restart_calls == calls_after_first, "idempotent run issued another restart"

    third = run_batch(**common)
    assert third.global_state == "BATCH_PASS"
    assert fake.restart_calls == calls_after_first

    # Site stages are stable; only the global BATCH_PASS re-stamp may append.
    after = load_checkpoint(report / "checkpoint.json")
    before = json.loads(checkpoint_after_first)
    assert {k: v.stage for k, v in after.sites.items()} == {
        k: v["stage"] for k, v in before["sites"].items()
    }
    assert json.loads(apath.read_text(encoding="utf-8"))["state"] == "CONSUMED"


# --------------------------------------------------------------------------
# Atomic state machine
# --------------------------------------------------------------------------


def test_atomic_write_leaves_no_temp_file_behind(tmp_path: Path) -> None:
    target = tmp_path / "checkpoint.json"
    atomic_write_json(target, {"a": 1})
    atomic_write_json(target, {"a": 2})
    assert json.loads(target.read_text(encoding="utf-8")) == {"a": 2}
    assert [p.name for p in tmp_path.iterdir()] == ["checkpoint.json"]


def test_atomic_write_crash_before_replace_keeps_previous_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A crash between write and rename must not truncate or corrupt the checkpoint."""
    target = tmp_path / "checkpoint.json"
    atomic_write_json(target, {"generation": 1})

    def boom(_src, _dst):
        raise OSError(errno.EIO, "simulated crash before rename")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        atomic_write_json(target, {"generation": 2})

    assert json.loads(target.read_text(encoding="utf-8")) == {"generation": 1}
    assert [p.name for p in tmp_path.iterdir()] == ["checkpoint.json"], "temp file leaked"


def test_checkpoint_roundtrip_is_lossless(tmp_path: Path) -> None:
    cp = new_checkpoint("rel-x", ["lords-01", "lords-02"])
    transition_site(cp, "lords-01", "PREFLIGHT")
    transition_site(cp, "lords-01", "BUILT", note="carried")
    path = tmp_path / "checkpoint.json"
    save_checkpoint(path, cp)
    back = load_checkpoint(path)
    assert back.release_id == cp.release_id
    assert back.sites["lords-01"].stage == "BUILT"
    assert back.sites["lords-01"].notes == {"note": "carried"}
    assert back.sites["lords-02"].stage == "PLANNED"


def test_illegal_transitions_are_rejected() -> None:
    cp = new_checkpoint("rel-x", ["lords-01"])
    # Skipping ahead is refused.
    with pytest.raises(StateError):
        transition_site(cp, "lords-01", "STAGED")
    # Unknown stage is refused.
    with pytest.raises(StateError):
        transition_site(cp, "lords-01", "NOT_A_STAGE")
    # Terminal stage accepts nothing further.
    for stage in ("PREFLIGHT", "BUILT", "ARTIFACT_VERIFIED", "ROLLBACK_PREPARED",
                  "STAGED", "RESTART_REQUESTED", "RUNTIME_WAIT", "RUNTIME_VERIFIED",
                  "SMOKE_RUN_1", "SMOKE_RUN_2", "POST_DEPLOY_PASS"):
        transition_site(cp, "lords-01", stage)
    with pytest.raises(StateError):
        transition_site(cp, "lords-01", "PREFLIGHT")


# --------------------------------------------------------------------------
# "Too many open files" / inotify exhaustion
# --------------------------------------------------------------------------


def test_restart_emfile_stderr_is_warning_not_failure() -> None:
    """systemd's 'Too many open files' on stderr is not proof the restart failed."""
    fake = FakeSystemd()
    fake.units["lords-02.service"] = {
        "ActiveState": "active",
        "SubState": "running",
        "MainPID": "10",
        "ExecMainStartTimestamp": "100",
        "NRestarts": "0",
    }
    fake.restart_stderr_error = True
    result = restart_once(fake, "lords-02.service", sleep_fn=lambda _s: None)

    assert "Too many open files" in result.detail
    assert result.restart_command_warning == 1
    assert result.restart_postconditions_pass == 1
    assert result.effective_result == "PASS"
    assert result.duplicate_restart_count == 0
    assert len(fake.restart_calls) == 1


def test_restart_emfile_with_failed_postconditions_is_failure() -> None:
    """The warning is not laundered into a pass when the unit did not come back."""
    fake = FakeSystemd()
    fake.units["lords-02.service"] = {
        "ActiveState": "active",
        "SubState": "running",
        "MainPID": "10",
        "ExecMainStartTimestamp": "100",
        "NRestarts": "0",
    }
    fake.restart_stderr_error = True
    fake.fail_postconditions = True
    result = restart_once(
        fake, "lords-02.service", timeout_seconds=0, sleep_fn=lambda _s: None
    )

    assert result.effective_result == "FAIL"
    assert result.restart_postconditions_pass == 0
    assert len(fake.restart_calls) == 1, "a failed restart must not be retried silently"


def test_emfile_during_checkpoint_write_does_not_corrupt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exhausted file descriptors surface as an error, never as a half-written state."""
    target = tmp_path / "checkpoint.json"
    atomic_write_json(target, {"generation": 1})

    def emfile(*_a, **_kw):
        raise OSError(errno.EMFILE, "Too many open files")

    monkeypatch.setattr(tempfile, "mkstemp", emfile)
    with pytest.raises(OSError) as exc:
        atomic_write_json(target, {"generation": 2})
    assert exc.value.errno == errno.EMFILE

    assert json.loads(target.read_text(encoding="utf-8")) == {"generation": 1}


def test_inotify_diagnose_is_read_only_and_never_remediates() -> None:
    """Diagnosis reports; it never raises sysctl limits on its own."""
    report = inotify_diag.diagnose()
    assert report.remediation_applied is False
    payload = report.as_dict()
    assert set(payload) >= {
        "max_user_instances",
        "observed_instances",
        "fd_soft_limit",
        "likely_cause",
        "remediation_applied",
    }

    asked = inotify_diag.diagnose(apply_remediation=True)
    assert asked.remediation_applied is False, "remediation must stay an owner decision"
    assert any("refused in-library" in n for n in asked.notes)


def test_inotify_unmeasured_is_reported_not_guessed(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unreadable sysctl stays unmeasured rather than defaulting to a number."""
    monkeypatch.setattr(inotify_diag, "_read_sysctl", lambda _name: None)
    report = inotify_diag.diagnose()
    assert report.max_user_instances is None
    assert report.likely_cause == "unmeasured"


# --------------------------------------------------------------------------
# Bypass paths
# --------------------------------------------------------------------------


def test_bypass_gate_refuses_only_when_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENFORCE_ENV, raising=False)
    refuse_if_enforced("lords-staging-apply.sh")  # no enforcement → returns

    for enabled in ("1", "true", "TRUE", "yes"):
        monkeypatch.setenv(ENFORCE_ENV, enabled)
        with pytest.raises(SystemExit) as exc:
            refuse_if_enforced("lords-staging-apply.sh")
        assert exc.value.code == 78

    monkeypatch.setenv(ENFORCE_ENV, "0")
    refuse_if_enforced("lords-staging-apply.sh")


@pytest.mark.parametrize(
    "script",
    [
        "automation/host/lords-staging-apply.sh",
        "automation/host/nova-daily-refresh.sh",
        "automation/host/finalize-public-sites.sh",
        "automation/host/install-units.sh",
        "automation/host/lords-content-refresh.sh",
        "automation/host/yummy-content-run.sh",
    ],
)
def test_legacy_deploy_scripts_carry_the_bypass_gate(script: str) -> None:
    """Every legacy deploy/restart path must refuse when the orchestrator is required."""
    root = Path(__file__).resolve().parents[2]
    path = root / script
    assert path.exists(), f"{script} missing"
    body = path.read_text(encoding="utf-8")
    assert ENFORCE_ENV in body, f"{script} has no {ENFORCE_ENV} gate"
    assert "78" in body, f"{script} does not exit 78 on the enforced path"


# --------------------------------------------------------------------------
# Exact-domain registry
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "candidate",
    [
        "lordfilm47.org",          # different TLD
        "film47.space",            # substring
        "lordfilm47.space.evil",   # suffix extension
        "evil-lordfilm47.space",   # prefix extension
        "sub.lordfilm47.space",    # subdomain
        "lordserial33.bizz",       # near miss
    ],
)
def test_registry_refuses_near_miss_domains(registry: ReleaseRegistry, candidate: str) -> None:
    with pytest.raises(RegistryError):
        registry.by_domain(candidate)


def test_registry_normalizes_scheme_case_and_path(registry: ReleaseRegistry) -> None:
    for spelling in (
        "lordserial33.biz",
        "LORDSERIAL33.BIZ",
        "https://lordserial33.biz",
        "https://www.lordserial33.biz/catalog?x=1",
        "http://lordserial33.biz/",
    ):
        assert normalize_domain(spelling) == "lordserial33.biz"
        assert registry.by_domain(spelling).site_id == "lords-02"


def test_registry_maps_each_lords_domain_to_its_own_unit(registry: ReleaseRegistry) -> None:
    pairs = {
        "lordfilm47.space": "lords-01",
        "lordserial33.biz": "lords-02",
        "1lordserials1.online": "lords-03",
    }
    units = set()
    for domain, site_id in pairs.items():
        rec = registry.by_domain(domain)
        assert rec.site_id == site_id
        units.add(rec.service_name)
    assert len(units) == 3, "two Lords sites share a systemd unit"


# --------------------------------------------------------------------------
# Rollback
# --------------------------------------------------------------------------


def test_rollback_restores_exact_bytes(tmp_path: Path) -> None:
    live = tmp_path / "live"
    (live / "nested").mkdir(parents=True)
    (live / "CURRENT").write_text("build-A\n", encoding="utf-8")
    (live / "version.json").write_text('{"build_id": "build-A"}\n', encoding="utf-8")
    (live / "nested" / "asset.bin").write_bytes(b"\x00\x01\x02payload")

    prep = prepare_rollback(site_id="lords-02", live_root=live, backup_root=tmp_path / "bak")
    assert prep.rollback_prepared == 1
    assert prep.rollback_digest_match == 1
    assert prep.rollback_rehearsal_pass == 1

    # Corrupt the live tree the way a bad deploy would.
    (live / "CURRENT").write_text("build-B\n", encoding="utf-8")
    (live / "nested" / "asset.bin").write_bytes(b"corrupted")
    (live / "stray.txt").write_text("left over\n", encoding="utf-8")

    restore_from_backup(Path(prep.backup_path), live)

    assert (live / "CURRENT").read_text(encoding="utf-8") == "build-A\n"
    assert (live / "nested" / "asset.bin").read_bytes() == b"\x00\x01\x02payload"
    assert not (live / "stray.txt").exists(), "restore left a file the backup never had"


def test_rollback_refuses_incomplete_backup(tmp_path: Path) -> None:
    live = tmp_path / "live"
    live.mkdir()
    (live / "CURRENT").write_text("build-A\n", encoding="utf-8")
    # version.json deliberately absent → backup is not a valid restore point.
    with pytest.raises(Exception):
        prepare_rollback(site_id="lords-02", live_root=live, backup_root=tmp_path / "bak")


# --------------------------------------------------------------------------
# Exact service mapping (registry claim vs routed reality)
# --------------------------------------------------------------------------


def _fake_host(tmp_path: Path, *, domain: str, routed_port: int,
               units: dict[str, int]) -> tuple[Path, Path]:
    """Build a throwaway nginx dir + systemd dir describing one routed domain."""
    nginx = tmp_path / "nginx"
    nginx.mkdir()
    (nginx / "site.conf").write_text(
        "server {\n"
        "    listen 80;\n"
        f"    server_name {domain} www.{domain};\n"
        "    root /var/www/acme;\n"
        "}\n"
        "server {\n"
        "    listen 443 ssl http2;\n"
        f"    server_name {domain};\n"
        "    location / {\n"
        f"        proxy_pass http://127.0.0.1:{routed_port};\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    unit_dir = tmp_path / "units"
    unit_dir.mkdir()
    for name, port in units.items():
        (unit_dir / name).write_text(
            f"[Service]\nExecStart=/usr/bin/python3 /srv/serve.py --port {port}\n",
            encoding="utf-8",
        )
    return nginx, unit_dir


def test_binding_detects_declared_but_unrouted_unit(
    registry: ReleaseRegistry, tmp_path: Path
) -> None:
    """The exact defect on this host: registry names a unit nginx does not route to."""
    nginx, units = _fake_host(
        tmp_path,
        domain="lordserial33.biz",
        routed_port=9111,
        units={"lords-02.service": 9102, "nova-lords-02.service": 9111},
    )
    report = resolve_bindings(
        ["lords-02"], registry=registry, nginx_dir=nginx, unit_dir=units
    )
    assert report.ok is False
    binding = report.bindings[0]
    assert binding.routed_port == 9111
    assert binding.routed_service == "nova-lords-02.service"
    assert binding.registry_service_port == 9102
    assert "MISMATCH" in binding.reason

    with pytest.raises(ServiceBindingError):
        assert_live_binding(
            ["lords-02"], registry=registry, nginx_dir=nginx, unit_dir=units
        )


def test_binding_confirms_matching_unit(registry: ReleaseRegistry, tmp_path: Path) -> None:
    nginx, units = _fake_host(
        tmp_path,
        domain="lordserial33.biz",
        routed_port=9102,
        units={"lords-02.service": 9102},
    )
    report = assert_live_binding(
        ["lords-02"], registry=registry, nginx_dir=nginx, unit_dir=units
    )
    assert report.ok is True
    assert report.bindings[0].routed_service == "lords-02.service"
    assert report.bindings[0].reason == "MATCH"


def test_binding_unmeasured_route_is_not_a_pass(
    registry: ReleaseRegistry, tmp_path: Path
) -> None:
    """No nginx evidence means unmeasured — never silently treated as matching."""
    nginx, units = _fake_host(
        tmp_path, domain="some-other.example", routed_port=9111,
        units={"lords-02.service": 9102},
    )
    report = resolve_bindings(["lords-02"], registry=registry, nginx_dir=nginx, unit_dir=units)
    assert report.ok is False
    assert report.bindings[0].routed_port is None
    assert report.bindings[0].reason == "NGINX_ROUTE_UNMEASURED"


def test_binding_ambiguous_port_is_not_a_pass(
    registry: ReleaseRegistry, tmp_path: Path
) -> None:
    """Two units claiming one port cannot identify a restart target."""
    nginx, units = _fake_host(
        tmp_path, domain="lordserial33.biz", routed_port=9111,
        units={"lords-02.service": 9111, "nova-lords-02.service": 9111},
    )
    report = resolve_bindings(["lords-02"], registry=registry, nginx_dir=nginx, unit_dir=units)
    assert report.ok is False
    assert report.bindings[0].routed_service is None
    assert "AMBIGUOUS_UNITS_ON_PORT_9111" in report.bindings[0].reason


def test_live_run_refuses_on_binding_mismatch(
    registry: ReleaseRegistry, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A mutating release stops before any restart when the binding is wrong."""
    mpath, digest, apath, manifest = _staged(registry, tmp_path, n=1)

    def refuse(_site_ids, **_kw):
        raise ServiceBindingError("BLOCKED_SERVICE_BINDING — lords-01: MISMATCH")

    monkeypatch.setattr(runner_mod, "assert_live_binding", refuse)
    fake = FakeSystemd()
    result = run_batch(
        release_id=manifest["release_id"],
        manifest_path=mpath,
        manifest_digest=digest,
        approval_path=apath,
        report_dir=tmp_path / "report",
        work_root=tmp_path / "work",
        registry=registry,
        systemd=fake,
        mutate=True,
        shadow=False,
    )
    assert result.verdict == "BLOCKED_SERVICE_BINDING"
    assert result.global_state == "BATCH_FAILED"
    assert fake.restart_calls == [], "a restart was issued despite a wrong service binding"


def test_shadow_run_is_not_gated_by_live_binding(
    registry: ReleaseRegistry, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The gate is live-only: shadow rehearsal must stay runnable on this host."""
    mpath, digest, apath, manifest = _staged(registry, tmp_path, n=1)

    def explode(_site_ids, **_kw):
        raise AssertionError("live binding gate must not run in shadow mode")

    monkeypatch.setattr(runner_mod, "assert_live_binding", explode)
    result = run_batch(
        release_id=manifest["release_id"],
        manifest_path=mpath,
        manifest_digest=digest,
        approval_path=apath,
        report_dir=tmp_path / "report",
        work_root=tmp_path / "work",
        registry=registry,
        systemd=FakeSystemd(),
        mutate=False,
        shadow=True,
    )
    assert result.global_state == "BATCH_PASS"
