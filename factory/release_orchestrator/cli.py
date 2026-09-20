"""CLI for Site Factory Release Orchestrator.

Does not accept arbitrary restart commands or free-form service names.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from factory.paths import PATHS
from factory.release_orchestrator import STAGE, TARGET_BRANCH, TARGET_WORKTREE
from factory.release_orchestrator.approval import (
    ApprovalError,
    assert_usable_for_manifest,
    build_approval,
    load_approval,
    write_approval,
)
from factory.release_orchestrator.dashboard import write_dashboard
from factory.release_orchestrator.inotify_diag import diagnose
from factory.release_orchestrator.intake import IntakeError, load_intake, plan_manifest_from_registry, validate_intake
from factory.release_orchestrator.manifest import (
    ManifestError,
    digest_obj,
    load_manifest,
    validate_manifest_structure,
    write_manifest,
)
from factory.release_orchestrator.preflight import preflight_batch
from factory.release_orchestrator.privilege import bootstrap_checklist, parse_runner_argv
from factory.release_orchestrator.registry import RegistryError, ReleaseRegistry
from factory.release_orchestrator.reports import write_final_reports
from factory.release_orchestrator.runner import run_batch
from factory.release_orchestrator.state import load_checkpoint

EXIT_OK, EXIT_FAIL, EXIT_BLOCKED = 0, 1, 2


def _reports_dir(release_id: str) -> Path:
    return PATHS.root / "reports" / "releases" / release_id


def cmd_plan(args: argparse.Namespace) -> int:
    intake = load_intake(args.intake)
    problems = validate_intake(intake)
    if problems and not args.allow_open_drafts:
        # Filter OPEN warnings if operator only wants conflict checks — still print.
        print(json.dumps({"problems": problems}, ensure_ascii=False, indent=2))
        if any("conflicts" in p or "duplicate" in p for p in problems):
            return EXIT_BLOCKED
    registry = ReleaseRegistry.load()
    site_ids = args.sites.split(",") if args.sites else [r.site_id for r in registry.enabled_sites()[:3]]
    artifacts = {}
    for sid in site_ids:
        # Planner requires explicit artifact map file when provided.
        artifacts[sid] = {
            "artifact_path": str(Path(args.artifact_root) / sid / "artifact"),
            "artifact_sha256": "0" * 64,
            "manifest_sha256": "1" * 64,
            "expected_build_id": f"build-{sid}",
            "expected_catalog_revision": "cat-1",
            "expected_details_revision": "det-1",
        }
    if args.artifacts_json:
        artifacts.update(json.loads(Path(args.artifacts_json).read_text(encoding="utf-8")))
    try:
        manifest = plan_manifest_from_registry(
            release_id=args.release_id,
            site_ids=site_ids,
            canary_site_id=args.canary or site_ids[0],
            source_head=args.source_head,
            requested_by=args.requested_by,
            artifacts=artifacts,
            release_mode=args.mode,
        )
    except IntakeError as exc:
        print(f"[BLOCKED_INPUT] {exc}", file=sys.stderr)
        return EXIT_BLOCKED
    out = Path(args.out)
    digest = write_manifest(out, manifest)
    print(json.dumps({"release_id": args.release_id, "manifest": str(out), "digest": digest}, indent=2))
    return EXIT_OK


def cmd_validate(args: argparse.Namespace) -> int:
    try:
        manifest = load_manifest(args.manifest)
        validate_manifest_structure(manifest, registry=ReleaseRegistry.load())
        report = preflight_batch(manifest, require_artifacts_on_disk=False)
    except (ManifestError, RegistryError) as exc:
        print(f"[BLOCKED_INPUT] {exc}", file=sys.stderr)
        return EXIT_BLOCKED
    print(json.dumps({"digest": digest_obj(manifest), **report.as_dict()}, indent=2))
    return EXIT_OK if report.ok else EXIT_BLOCKED


def cmd_approve_status(args: argparse.Namespace) -> int:
    try:
        approval = load_approval(args.approval)
        print(json.dumps(approval, indent=2, ensure_ascii=False))
        return EXIT_OK
    except Exception as exc:  # noqa: BLE001
        print(f"[BLOCKED_INPUT] {exc}", file=sys.stderr)
        return EXIT_BLOCKED


def cmd_record_approval(args: argparse.Namespace) -> int:
    """Record owner approval binding (unprivileged). Does not run deploy."""
    manifest = load_manifest(args.manifest)
    approval = build_approval(
        approval_id=args.approval_id,
        release_id=manifest["release_id"],
        manifest=manifest,
        approved_by=args.approved_by,
        allowed_indexability_changes=args.allow_indexability,
        allowed_dns_changes=False,
        allowed_paid_operations=False,
        expires_at=args.expires_at or manifest["expires_at"],
    )
    write_approval(args.out, approval)
    print(json.dumps({"approval_id": approval["approval_id"], "state": approval["state"]}, indent=2))
    return EXIT_OK


def cmd_run(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    digest = args.manifest_digest or digest_obj(load_manifest(manifest_path))
    report_dir = _reports_dir(args.release_id)
    work_root = PATHS.var / "release-orchestrator" / args.release_id
    try:
        result = run_batch(
            release_id=args.release_id,
            manifest_path=manifest_path,
            manifest_digest=digest,
            approval_path=Path(args.approval),
            report_dir=report_dir,
            work_root=work_root,
            mutate=bool(args.mutate),
            shadow=bool(args.shadow) and not bool(args.mutate),
        )
    except (ApprovalError, ManifestError, RegistryError) as exc:
        print(f"[BLOCKED_AUTHORIZATION] {exc}", file=sys.stderr)
        return EXIT_BLOCKED
    write_final_reports(report_dir, verdict=result.verdict)
    print(json.dumps(result.__dict__, indent=2, ensure_ascii=False))
    return EXIT_OK if result.verdict in {"BATCH_PASS", "CANARY_PASS"} or result.global_state == "BATCH_PASS" else EXIT_FAIL


def cmd_status(args: argparse.Namespace) -> int:
    path = _reports_dir(args.release_id) / "checkpoint.json"
    if not path.exists():
        print(f"[BLOCKED_INPUT] no checkpoint for {args.release_id}", file=sys.stderr)
        return EXIT_BLOCKED
    cp = load_checkpoint(path)
    write_dashboard(_reports_dir(args.release_id), cp)
    print(json.dumps(cp.as_dict(), indent=2, ensure_ascii=False))
    return EXIT_OK


def cmd_resume(args: argparse.Namespace) -> int:
    args.shadow = True
    args.mutate = False
    return cmd_run(args)


def cmd_rollback(args: argparse.Namespace) -> int:
    print(
        json.dumps(
            {
                "status": "BLOCKED_INPUT",
                "reason": "scoped rollback must go through root runner with registry rollback_handler",
                "release_id": args.release_id,
                "site_id": args.site_id,
            },
            indent=2,
        )
    )
    return EXIT_BLOCKED


def cmd_inotify(args: argparse.Namespace) -> int:
    report = diagnose(apply_remediation=False)
    print(json.dumps(report.as_dict(), indent=2))
    return EXIT_OK


def cmd_bootstrap_print(_: argparse.Namespace) -> int:
    print(json.dumps({
        "stage": STAGE,
        "target_branch": TARGET_BRANCH,
        "target_worktree": TARGET_WORKTREE,
        "one_time_bootstrap": bootstrap_checklist(),
        "note": "Обычный batch не требует ручного SSH/systemctl/curl.",
    }, ensure_ascii=False, indent=2))
    return EXIT_OK


def cmd_runner_check(args: argparse.Namespace) -> int:
    try:
        req = parse_runner_argv(args.argv)
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL_PRIVILEGE_BOUNDARY] {exc}", file=sys.stderr)
        return EXIT_FAIL
    print(json.dumps(req.__dict__, indent=2, default=str))
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="site-factory-release", description="Site Factory Release Orchestrator")
    sub = p.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan", help="plan immutable manifest from intake/registry")
    plan.add_argument("--intake", required=True)
    plan.add_argument("--release-id", required=True)
    plan.add_argument("--source-head", required=True)
    plan.add_argument("--requested-by", default="operator")
    plan.add_argument("--sites", default="")
    plan.add_argument("--canary", default="")
    plan.add_argument("--artifact-root", default="/tmp/sf-release-artifacts")
    plan.add_argument("--artifacts-json", default="")
    plan.add_argument("--out", required=True)
    plan.add_argument("--mode", default="shadow")
    plan.add_argument("--allow-open-drafts", action="store_true")
    plan.set_defaults(func=cmd_plan)

    validate = sub.add_parser("validate", help="validate manifest + preflight")
    validate.add_argument("--manifest", required=True)
    validate.set_defaults(func=cmd_validate)

    st = sub.add_parser("approve-status", help="show approval state")
    st.add_argument("--approval", required=True)
    st.add_argument("--release-id", default="")
    st.set_defaults(func=cmd_approve_status)

    rec = sub.add_parser("record-approval", help="bind owner approval to manifest digest")
    rec.add_argument("--manifest", required=True)
    rec.add_argument("--approval-id", required=True)
    rec.add_argument("--approved-by", required=True)
    rec.add_argument("--out", required=True)
    rec.add_argument("--expires-at", default="")
    rec.add_argument("--allow-indexability", action="store_true")
    rec.set_defaults(func=cmd_record_approval)

    run = sub.add_parser("run", help="run or resume batch (shadow by default)")
    run.add_argument("--release-id", required=True)
    run.add_argument("--manifest", required=True)
    run.add_argument("--manifest-digest", default="")
    run.add_argument("--approval", required=True)
    run.add_argument(
        "--shadow",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="shadow/dry path (default). Use --no-shadow with --mutate for live.",
    )
    run.add_argument("--mutate", action="store_true", help="live mutations; requires root runner in production")
    run.set_defaults(func=cmd_run)

    status = sub.add_parser("status", help="checkpoint + dashboard")
    status.add_argument("--release-id", required=True)
    status.set_defaults(func=cmd_status)

    resume = sub.add_parser("resume", help="resume from checkpoint")
    resume.add_argument("--release-id", required=True)
    resume.add_argument("--manifest", required=True)
    resume.add_argument("--manifest-digest", default="")
    resume.add_argument("--approval", required=True)
    resume.set_defaults(func=cmd_resume)

    rb = sub.add_parser("rollback", help="scoped site rollback via runner")
    rb.add_argument("--release-id", required=True)
    rb.add_argument("--site-id", required=True)
    rb.set_defaults(func=cmd_rollback)

    sub.add_parser("inotify-diagnose", help="read-only inotify diagnosis").set_defaults(func=cmd_inotify)
    sub.add_parser("bootstrap-print", help="print one-time owner bootstrap checklist").set_defaults(
        func=cmd_bootstrap_print
    )

    rc = sub.add_parser("runner-check", help="validate root-runner argv contract")
    rc.add_argument("argv", nargs="*")
    rc.set_defaults(func=cmd_runner_check)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
