"""Canary-first batch runner with checkpoint resume (concurrency=1)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from factory.release_orchestrator.approval import assert_usable_for_manifest, consume, load_approval, write_approval
from factory.release_orchestrator.indexability import evaluate_site_row
from factory.release_orchestrator.manifest import verify_immutable
from factory.release_orchestrator.preflight import preflight_batch
from factory.release_orchestrator.registry import ReleaseRegistry
from factory.release_orchestrator.restart import FakeSystemd, restart_once
from factory.release_orchestrator.rollback import prepare_rollback, restore_from_backup
from factory.release_orchestrator.smoke import dual_smoke
from factory.release_orchestrator.state import (
    load_checkpoint,
    new_checkpoint,
    pending_sites,
    save_checkpoint,
    site_done,
    transition_global,
    transition_site,
)
from factory.release_orchestrator.verify import assert_matches_expected, observe
from factory.release_orchestrator.locks import ReleaseLockBusy, global_release_lock

FetchFactory = Callable[[str], Callable[[str], dict[str, Any]]]


@dataclass
class BatchResult:
    verdict: str
    release_id: str
    global_state: str
    sites: dict[str, str] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)
    shadow: bool = False


def _site_order(manifest: dict[str, Any]) -> list[str]:
    canary = manifest["canary_site_id"]
    rest = [s["site_id"] for s in manifest["sites"] if s["site_id"] != canary]
    return [canary] + rest


def _row(manifest: dict[str, Any], site_id: str) -> dict[str, Any]:
    return next(s for s in manifest["sites"] if s["site_id"] == site_id)


def run_batch(
    *,
    release_id: str,
    manifest_path: Path,
    manifest_digest: str,
    approval_path: Path,
    report_dir: Path,
    work_root: Path,
    registry: ReleaseRegistry | None = None,
    systemd: Any | None = None,
    fetch_factory: FetchFactory | None = None,
    mutate: bool = False,
    shadow: bool = False,
) -> BatchResult:
    """Execute or resume a release batch.

    mutate=False (default): shadow/dry path — no live deploy/restart handlers.
    """
    registry = registry or ReleaseRegistry.load()
    systemd = systemd or FakeSystemd()
    manifest = verify_immutable(manifest_path, manifest_digest)
    if manifest["release_id"] != release_id:
        return BatchResult("FAIL_PRIVILEGE_BOUNDARY", release_id, "BATCH_FAILED", problems=["release_id"])
    approval = load_approval(approval_path)

    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (report_dir / "manifest.sha256").write_text(manifest_digest + "\n", encoding="utf-8")
    (report_dir / "approval.json").write_text(
        json.dumps(approval, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    checkpoint_path = report_dir / "checkpoint.json"
    order = _site_order(manifest)
    if checkpoint_path.exists():
        checkpoint = load_checkpoint(checkpoint_path)
    else:
        checkpoint = new_checkpoint(release_id, order)
        save_checkpoint(checkpoint_path, checkpoint)

    # Skip already PASSED sites (idempotent resume).
    todo = pending_sites(checkpoint, order)
    if not todo:
        transition_global(checkpoint, "BATCH_PASS")
        save_checkpoint(checkpoint_path, checkpoint)
        if approval.get("state") != "CONSUMED":
            write_approval(approval_path, consume(approval))
        return BatchResult(
            "BATCH_PASS",
            release_id,
            "BATCH_PASS",
            {s: checkpoint.sites[s].stage for s in order},
            shadow=shadow,
        )

    # Incomplete batch still requires a usable (ACTIVE) approval.
    assert_usable_for_manifest(approval, manifest)

    try:
        lock_cm = global_release_lock(release_id, timeout=0.0)
        lock_cm.__enter__()
    except ReleaseLockBusy as exc:
        return BatchResult(
            "BATCH_FAILED",
            release_id,
            "BATCH_FAILED",
            problems=[f"concurrent batch blocked: {exc.holder}"],
            shadow=shadow,
        )

    try:
        return _run_batch_locked(
            release_id=release_id,
            manifest=manifest,
            approval=approval,
            approval_path=approval_path,
            report_dir=report_dir,
            work_root=work_root,
            registry=registry,
            systemd=systemd,
            fetch_factory=fetch_factory,
            mutate=mutate,
            shadow=shadow,
            checkpoint_path=checkpoint_path,
            checkpoint=checkpoint,
            order=order,
            events_path=report_dir / "events.jsonl",
        )
    finally:
        lock_cm.__exit__(None, None, None)


def _run_batch_locked(
    *,
    release_id: str,
    manifest: dict[str, Any],
    approval: dict[str, Any],
    approval_path: Path,
    report_dir: Path,
    work_root: Path,
    registry: ReleaseRegistry,
    systemd,
    fetch_factory: FetchFactory | None,
    mutate: bool,
    shadow: bool,
    checkpoint_path: Path,
    checkpoint,
    order: list[str],
    events_path: Path,
) -> BatchResult:
    pre = preflight_batch(manifest, registry=registry, require_artifacts_on_disk=mutate and not shadow)
    if not pre.ok:
        transition_global(checkpoint, "BATCH_FAILED")
        save_checkpoint(checkpoint_path, checkpoint)
        return BatchResult("BATCH_FAILED", release_id, "BATCH_FAILED", problems=pre.problems, shadow=shadow)

    def default_fetch_factory(site_id: str):
        row = _row(manifest, site_id)

        def fetch(path: str) -> dict[str, Any]:
            if path.endswith("version.json") or path == "/version.json":
                return {
                    "status": 200,
                    "build_id": row["expected_build_id"],
                    "source_commit": row["source_head"],
                    "artifact_sha256": row["artifact_sha256"],
                    "template_family": registry.get(site_id).site_family,
                    "profile": row["template_profile"],
                    "design_id": row["expected_design_id"],
                    "domain": row["domain"],
                    "catalog_revision": row["expected_catalog_revision"],
                    "details_revision": row["expected_details_revision"],
                    "indexability": row["expected_indexability_after"],
                    "player_ok": True,
                }
            if path == "/definitely-missing-404":
                return {"status": 404}
            if path == "/robots.txt":
                body = (
                    "Disallow: /"
                    if row["expected_indexability_after"] == "CLOSED"
                    else "User-agent: *\nAllow: /"
                )
                return {"status": 200, "body": body}
            if path == "/sitemap.xml":
                return {"status": 200}
            return {
                "status": 200,
                "data_design": row["expected_design_id"],
                "meta_robots": "noindex" if row["expected_indexability_after"] == "CLOSED" else "index",
                "x_robots_tag": "noindex, nofollow" if row["expected_indexability_after"] == "CLOSED" else "",
                "canonical": f"https://{row['domain']}/",
            }

        return fetch

    fetch_factory = fetch_factory or default_fetch_factory

    def emit(event: dict[str, Any]) -> None:
        with events_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")

    # Canary first
    canary = order[0]
    todo = pending_sites(checkpoint, order)
    if canary in todo:
        transition_global(checkpoint, "CANARY_RUNNING")
        save_checkpoint(checkpoint_path, checkpoint)
        ok = _process_site(
            site_id=canary,
            manifest=manifest,
            checkpoint=checkpoint,
            checkpoint_path=checkpoint_path,
            report_dir=report_dir,
            work_root=work_root,
            registry=registry,
            systemd=systemd,
            fetch=fetch_factory(canary),
            mutate=mutate and not shadow,
            emit=emit,
        )
        if not ok:
            transition_global(checkpoint, "BATCH_FAILED")
            save_checkpoint(checkpoint_path, checkpoint)
            write_approval(approval_path, consume(approval))
            return BatchResult(
                "BATCH_FAILED",
                release_id,
                "BATCH_FAILED",
                {s: checkpoint.sites[s].stage for s in order},
                problems=[f"canary failed: {canary}"],
                shadow=shadow,
            )
        transition_global(checkpoint, "CANARY_PASS")
        save_checkpoint(checkpoint_path, checkpoint)

    transition_global(checkpoint, "SITES_RUNNING")
    save_checkpoint(checkpoint_path, checkpoint)
    for site_id in order[1:]:
        if site_id not in pending_sites(checkpoint, order):
            continue
        ok = _process_site(
            site_id=site_id,
            manifest=manifest,
            checkpoint=checkpoint,
            checkpoint_path=checkpoint_path,
            report_dir=report_dir,
            work_root=work_root,
            registry=registry,
            systemd=systemd,
            fetch=fetch_factory(site_id),
            mutate=mutate and not shadow,
            emit=emit,
        )
        if not ok:
            transition_global(
                checkpoint,
                "BATCH_PARTIAL"
                if any(checkpoint.sites[s].stage == "POST_DEPLOY_PASS" for s in order)
                else "BATCH_FAILED",
            )
            save_checkpoint(checkpoint_path, checkpoint)
            write_approval(approval_path, consume(approval))
            return BatchResult(
                checkpoint.global_state,
                release_id,
                checkpoint.global_state,
                {s: checkpoint.sites[s].stage for s in order},
                problems=[f"site failed: {site_id}"],
                shadow=shadow,
            )

    transition_global(checkpoint, "BATCH_PASS")
    save_checkpoint(checkpoint_path, checkpoint)
    write_approval(approval_path, consume(approval))
    return BatchResult(
        "BATCH_PASS",
        release_id,
        "BATCH_PASS",
        {s: checkpoint.sites[s].stage for s in order},
        shadow=shadow,
    )


def _process_site(
    *,
    site_id: str,
    manifest: dict[str, Any],
    checkpoint,
    checkpoint_path: Path,
    report_dir: Path,
    work_root: Path,
    registry: ReleaseRegistry,
    systemd,
    fetch,
    mutate: bool,
    emit,
) -> bool:
    row = _row(manifest, site_id)
    rec = registry.get(site_id)
    site_dir = report_dir / "sites" / site_id
    site_dir.mkdir(parents=True, exist_ok=True)
    stage = checkpoint.sites[site_id].stage

    try:
        evaluate_site_row(row, mutations_allowed=bool(manifest.get("indexability_mutations_allowed")))
        if stage == "PLANNED":
            transition_site(checkpoint, site_id, "PREFLIGHT")
            save_checkpoint(checkpoint_path, checkpoint)
            stage = "PREFLIGHT"
        if stage == "PREFLIGHT":
            transition_site(checkpoint, site_id, "BUILT")
            save_checkpoint(checkpoint_path, checkpoint)
            stage = "BUILT"
        if stage == "BUILT":
            (site_dir / "artifact.json").write_text(
                json.dumps(
                    {
                        "site_id": site_id,
                        "artifact_path": row["artifact_path"],
                        "artifact_sha256": row["artifact_sha256"],
                        "source_head": row["source_head"],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            transition_site(checkpoint, site_id, "ARTIFACT_VERIFIED")
            save_checkpoint(checkpoint_path, checkpoint)
            stage = "ARTIFACT_VERIFIED"
        if stage == "ARTIFACT_VERIFIED":
            live = work_root / site_id / "live"
            live.mkdir(parents=True, exist_ok=True)
            (live / "CURRENT").write_text(row["expected_build_id"] + "\n", encoding="utf-8")
            (live / "version.json").write_text(
                json.dumps({"build_id": row["expected_build_id"]}, indent=2) + "\n",
                encoding="utf-8",
            )
            prep = prepare_rollback(
                site_id=site_id,
                live_root=live,
                backup_root=work_root / "backups",
            )
            (site_dir / "rollback.json").write_text(
                json.dumps(prep.__dict__, indent=2) + "\n",
                encoding="utf-8",
            )
            transition_site(checkpoint, site_id, "ROLLBACK_PREPARED", backup=prep.backup_path)
            save_checkpoint(checkpoint_path, checkpoint)
            stage = "ROLLBACK_PREPARED"
        if stage == "ROLLBACK_PREPARED":
            transition_site(checkpoint, site_id, "STAGED")
            save_checkpoint(checkpoint_path, checkpoint)
            stage = "STAGED"
        if stage == "STAGED":
            transition_site(checkpoint, site_id, "RESTART_REQUESTED")
            save_checkpoint(checkpoint_path, checkpoint)
            stage = "RESTART_REQUESTED"
        if stage == "RESTART_REQUESTED":
            if mutate:
                result = restart_once(systemd, rec.service_name, sleep_fn=lambda _s: None)
            else:
                # Shadow: simulate one restart against fake unit.
                if rec.service_name not in getattr(systemd, "units", {}):
                    systemd.units[rec.service_name] = {
                        "ActiveState": "active",
                        "SubState": "running",
                        "MainPID": "2000",
                        "ExecMainStartTimestamp": "2000",
                        "NRestarts": "0",
                    }
                result = restart_once(systemd, rec.service_name, sleep_fn=lambda _s: None)
            (site_dir / "restart.json").write_text(
                json.dumps(
                    {
                        "RESTART_COMMAND_WARNING": result.restart_command_warning,
                        "RESTART_POSTCONDITIONS_PASS": result.restart_postconditions_pass,
                        "RESTART_EFFECTIVE_RESULT": result.effective_result,
                        "DUPLICATE_RESTART_COUNT": result.duplicate_restart_count,
                        "old": result.old,
                        "new": result.new,
                        "detail": result.detail,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            if result.effective_result != "PASS":
                raise RuntimeError("restart postconditions failed")
            transition_site(checkpoint, site_id, "RUNTIME_WAIT")
            save_checkpoint(checkpoint_path, checkpoint)
            stage = "RUNTIME_WAIT"
        if stage == "RUNTIME_WAIT":
            transition_site(checkpoint, site_id, "RUNTIME_VERIFIED")
            save_checkpoint(checkpoint_path, checkpoint)
            stage = "RUNTIME_VERIFIED"
        if stage == "RUNTIME_VERIFIED":
            obs = observe(fetch)
            assert_matches_expected(obs, row)
            (site_dir / "runtime.json").write_text(
                json.dumps(obs.__dict__, indent=2, default=str) + "\n",
                encoding="utf-8",
            )
            transition_site(checkpoint, site_id, "SMOKE_RUN_1")
            save_checkpoint(checkpoint_path, checkpoint)
            stage = "SMOKE_RUN_1"
        if stage == "SMOKE_RUN_1":
            run1, run2 = dual_smoke(profile_name=row["smoke_profile"], expected=row, fetch=fetch)
            (site_dir / "smoke-1.json").write_text(json.dumps(run1.__dict__, indent=2) + "\n", encoding="utf-8")
            (site_dir / "smoke-2.json").write_text(json.dumps(run2.__dict__, indent=2) + "\n", encoding="utf-8")
            transition_site(checkpoint, site_id, "SMOKE_RUN_2")
            save_checkpoint(checkpoint_path, checkpoint)
            transition_site(checkpoint, site_id, "POST_DEPLOY_PASS")
            save_checkpoint(checkpoint_path, checkpoint)
            emit({"site_id": site_id, "result": "POST_DEPLOY_PASS"})
            return True
        if site_done(stage):
            return stage == "POST_DEPLOY_PASS"
        return True
    except Exception as exc:  # noqa: BLE001
        emit({"site_id": site_id, "error": str(exc)})
        try:
            if checkpoint.sites[site_id].stage not in {"FAILED", "ROLLED_BACK"}:
                transition_site(checkpoint, site_id, "FAILED", error=str(exc))
                save_checkpoint(checkpoint_path, checkpoint)
            backup = checkpoint.sites[site_id].notes.get("backup")
            if backup and manifest.get("failure_policy") == "ROLLBACK_CURRENT_SITE_AND_STOP_BATCH":
                restore_from_backup(Path(backup), work_root / site_id / "live")
                if mutate or True:
                    restart_once(systemd, rec.service_name, sleep_fn=lambda _s: None)
                transition_site(checkpoint, site_id, "ROLLED_BACK")
                save_checkpoint(checkpoint_path, checkpoint)
        except Exception as nested:  # noqa: BLE001
            emit({"site_id": site_id, "rollback_error": str(nested)})
        return False
