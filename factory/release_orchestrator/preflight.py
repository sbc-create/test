"""Batch preflight: refuse half-start on known-invalid manifests."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from factory.release_orchestrator.indexability import evaluate_site_row
from factory.release_orchestrator.manifest import ManifestError, validate_manifest_structure
from factory.release_orchestrator.registry import ReleaseRegistry, RegistryError
from factory.release_orchestrator.smoke import PROFILES


@dataclass
class PreflightReport:
    ok: bool
    problems: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "problems": list(self.problems)}


def preflight_batch(
    manifest: dict[str, Any],
    *,
    registry: ReleaseRegistry | None = None,
    require_artifacts_on_disk: bool = True,
) -> PreflightReport:
    problems: list[str] = []
    registry = registry or ReleaseRegistry.load()

    try:
        validate_manifest_structure(manifest, registry=registry)
    except ManifestError as exc:
        problems.append(str(exc))

    # Global resource floors (read-only checks; do not mutate).
    usage = shutil.disk_usage("/")
    if usage.free < 512 * 1024 * 1024:
        problems.append(f"disk free too low: {usage.free}")
    # Memory: best-effort from /proc
    meminfo = Path("/proc/meminfo")
    if meminfo.exists():
        for line in meminfo.read_text(encoding="utf-8").splitlines():
            if line.startswith("MemAvailable:"):
                kb = int(line.split()[1])
                if kb < 256 * 1024:
                    problems.append(f"MemAvailable too low: {kb} kB")
                break

    site_ids = [s["site_id"] for s in manifest.get("sites") or []]
    try:
        registry.require_unique_services(site_ids)
    except RegistryError as exc:
        problems.append(str(exc))

    for row in manifest.get("sites") or []:
        sid = row.get("site_id")
        try:
            rec = registry.get(sid)
        except RegistryError as exc:
            problems.append(str(exc))
            continue
        if not rec.enabled:
            problems.append(f"{sid}: disabled in registry")
        if row.get("domain") != rec.domain:
            problems.append(f"{sid}: domain mismatch registry")
        if row.get("smoke_profile") not in PROFILES:
            problems.append(f"{sid}: unknown smoke_profile {row.get('smoke_profile')}")
        try:
            evaluate_site_row(
                row,
                mutations_allowed=bool(manifest.get("indexability_mutations_allowed")),
            )
        except Exception as exc:  # noqa: BLE001 — collect all
            problems.append(f"{sid}: {exc}")
        artifact = Path(str(row.get("artifact_path") or ""))
        if require_artifacts_on_disk:
            if not artifact.exists():
                problems.append(f"{sid}: artifact missing: {artifact}")
            else:
                # ownership/permission readability
                if not os.access(artifact, os.R_OK):
                    problems.append(f"{sid}: artifact not readable")

    if manifest.get("dns_mutations_allowed"):
        problems.append("dns_mutations_allowed=true rejected by default preflight")
    if manifest.get("paid_operations_allowed"):
        problems.append("paid_operations_allowed=true rejected by default preflight")

    return PreflightReport(ok=not problems, problems=problems)
