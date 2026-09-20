"""Privilege boundary: unprivileged planner → root-owned runner.

Runner accepts ONLY release_id + approved manifest path/digest.
Service names, artifact paths, and handlers come from the trusted registry.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from factory.release_orchestrator.approval import assert_usable_for_manifest, load_approval
from factory.release_orchestrator.manifest import verify_immutable
from factory.release_orchestrator.registry import ALLOWED_HANDLERS, ReleaseRegistry

FORBIDDEN_RUNNER_FLAGS = frozenset(
    {
        "--force",
        "--shell",
        "--command",
        "--service",
        "--unit",
        "--path",
        "--domain",
        "--exec",
    }
)


class PrivilegeError(ValueError):
    pass


@dataclass(frozen=True)
class RunnerRequest:
    release_id: str
    manifest_path: Path
    manifest_digest: str
    approval_path: Path


def parse_runner_argv(argv: list[str]) -> RunnerRequest:
    """Parse root-runner argv. Rejects arbitrary commands/services/paths flags."""
    if any(a in FORBIDDEN_RUNNER_FLAGS or a.startswith("--force") for a in argv):
        raise PrivilegeError("runner rejects force/shell/service/path flags")
    args: dict[str, str] = {}
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok in {"--release-id", "--manifest", "--manifest-digest", "--approval"}:
            if i + 1 >= len(argv):
                raise PrivilegeError(f"missing value for {tok}")
            args[tok] = argv[i + 1]
            i += 2
            continue
        raise PrivilegeError(f"unsupported runner argument: {tok}")
    required = ("--release-id", "--manifest", "--manifest-digest", "--approval")
    for key in required:
        if key not in args:
            raise PrivilegeError(f"missing {key}")
    return RunnerRequest(
        release_id=args["--release-id"],
        manifest_path=Path(args["--manifest"]),
        manifest_digest=args["--manifest-digest"],
        approval_path=Path(args["--approval"]),
    )


def load_trusted_context(request: RunnerRequest, registry: ReleaseRegistry | None = None) -> dict[str, Any]:
    registry = registry or ReleaseRegistry.load()
    manifest = verify_immutable(request.manifest_path, request.manifest_digest)
    if manifest["release_id"] != request.release_id:
        raise PrivilegeError("release_id mismatch")
    approval = load_approval(request.approval_path)
    assert_usable_for_manifest(approval, manifest)
    # Resolve handlers exclusively from registry for sites in manifest.
    plan = []
    for site in manifest["sites"]:
        rec = registry.get(site["site_id"])
        for handler in (rec.deploy_handler, rec.restart_handler, rec.rollback_handler):
            if handler not in ALLOWED_HANDLERS:
                raise PrivilegeError(f"handler not allowlisted: {handler}")
        plan.append(
            {
                "site_id": rec.site_id,
                "domain": rec.domain,
                "service_name": rec.service_name,
                "artifact_path": site["artifact_path"],
                "artifact_sha256": site["artifact_sha256"],
                "deploy_handler": rec.deploy_handler,
                "restart_handler": rec.restart_handler,
                "rollback_handler": rec.rollback_handler,
            }
        )
    return {"manifest": manifest, "approval": approval, "plan": plan, "registry": "core"}


# Bootstrap is intentionally documentation + marker files, not a shell dump.
BOOTSTRAP_STEPS = (
    "install root-owned site-factory-release-runner executable",
    "install systemd unit site-factory-release-runner.service (optional path/timer)",
    "install narrow sudoers/polkit: ONLY invoke runner with --release-id/--manifest/--manifest-digest/--approval",
    "create state dirs under /var/lib/site-factory/releases with root ownership",
    "set RELEASE_ORCHESTRATOR_REQUIRED=1 on legacy host BYPASS scripts",
)


def bootstrap_checklist() -> list[str]:
    return list(BOOTSTRAP_STEPS)


Handler = Callable[[dict[str, Any]], dict[str, Any]]


class HandlerBus:
    """Allowlisted handler dispatch. No arbitrary shell."""

    def __init__(self) -> None:
        self._handlers: dict[str, Handler] = {}

    def register(self, name: str, fn: Handler) -> None:
        if name not in ALLOWED_HANDLERS:
            raise PrivilegeError(f"cannot register non-allowlisted handler: {name}")
        self._handlers[name] = fn

    def call(self, name: str, ctx: dict[str, Any]) -> dict[str, Any]:
        if name not in self._handlers:
            raise PrivilegeError(f"handler not installed: {name}")
        return self._handlers[name](ctx)
