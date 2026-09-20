"""Five-site intake → draft registration + immutable batch planning."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from factory.release_orchestrator.manifest import digest_obj
from factory.release_orchestrator.registry import ReleaseRegistry, RegistryError, normalize_domain


class IntakeError(ValueError):
    pass


def load_intake(path: Path | str) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "sites" not in data:
        raise IntakeError("intake must be object with sites[]")
    return data


def validate_intake(intake: dict[str, Any], registry: ReleaseRegistry | None = None) -> list[str]:
    problems: list[str] = []
    registry = registry or ReleaseRegistry.load()
    existing_ids = {r.site_id for r in registry.all_sites()}
    existing_domains = {r.domain for r in registry.all_sites()}
    seen_ids: set[str] = set()
    seen_domains: set[str] = set()
    profiles: dict[str, list[str]] = {}

    for row in intake.get("sites") or []:
        sid = row.get("site_id")
        domain = normalize_domain(str(row.get("domain") or ""))
        if not sid or not domain:
            problems.append("site missing site_id/domain")
            continue
        if sid in seen_ids:
            problems.append(f"duplicate intake site_id: {sid}")
        if domain in seen_domains:
            problems.append(f"duplicate intake domain: {domain}")
        seen_ids.add(sid)
        seen_domains.add(domain)
        if sid in existing_ids:
            problems.append(f"site_id conflicts with registry: {sid}")
        if domain in existing_domains:
            problems.append(f"domain conflicts with registry: {domain}")
        # New sites must not auto-open indexing.
        if row.get("desired_indexability") == "OPEN":
            problems.append(
                f"{sid}: desired_indexability=OPEN requires explicit release manifest approval later; "
                "intake registers as draft CLOSED by default"
            )
        family = str(row.get("family") or "")
        profile = str(row.get("template_profile") or "")
        profiles.setdefault(family, []).append(profile)

    for family, plist in profiles.items():
        if len(plist) >= 2 and len(set(plist)) < len(plist):
            problems.append(f"family {family}: duplicate template_profile values {plist}")
    return problems


def drafts_from_intake(intake: dict[str, Any]) -> list[dict[str, Any]]:
    """Register drafts — always CLOSED until release manifest says otherwise."""
    drafts = []
    for row in intake.get("sites") or []:
        draft = deepcopy(row)
        draft["owner_state"] = "draft"
        draft["expected_indexability"] = "CLOSED"
        draft["enabled"] = False
        drafts.append(draft)
    return drafts


def plan_manifest_from_registry(
    *,
    release_id: str,
    site_ids: list[str],
    canary_site_id: str,
    source_head: str,
    requested_by: str,
    artifacts: dict[str, dict[str, str]],
    registry: ReleaseRegistry | None = None,
    ttl_hours: int = 24,
    release_mode: str = "shadow",
) -> dict[str, Any]:
    """Build an immutable manifest using registry values only (no manual domain/service)."""
    registry = registry or ReleaseRegistry.load()
    if canary_site_id not in site_ids:
        raise IntakeError("canary_site_id must be in site_ids")
    now = datetime.now(timezone.utc)
    sites = []
    for sid in site_ids:
        try:
            rec = registry.get(sid)
        except RegistryError as exc:
            raise IntakeError(str(exc)) from exc
        art = artifacts.get(sid) or {}
        for key in ("artifact_path", "artifact_sha256", "manifest_sha256", "expected_build_id",
                    "expected_catalog_revision", "expected_details_revision"):
            if key not in art:
                raise IntakeError(f"{sid}: missing artifact field {key}")
        sites.append(
            {
                "site_id": sid,
                "domain": rec.domain,
                "source_head": source_head,
                "artifact_path": art["artifact_path"],
                "artifact_sha256": art["artifact_sha256"],
                "manifest_sha256": art["manifest_sha256"],
                "template_profile": rec.template_profile,
                "expected_design_id": rec.design_id,
                "expected_build_id": art["expected_build_id"],
                "expected_indexability_before": rec.expected_indexability,
                "expected_indexability_after": rec.expected_indexability,
                "expected_catalog_revision": art["expected_catalog_revision"],
                "expected_details_revision": art["expected_details_revision"],
                "smoke_profile": rec.smoke_profile,
                "rollback_required": True,
            }
        )
    manifest = {
        "schema_version": "1.0.0",
        "release_id": release_id,
        "owner_approval_id": None,
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=ttl_hours)).isoformat(),
        "requested_by": requested_by,
        "release_mode": release_mode,
        "canary_site_id": canary_site_id,
        "failure_policy": "ROLLBACK_CURRENT_SITE_AND_STOP_BATCH",
        "indexability_mutations_allowed": False,
        "dns_mutations_allowed": False,
        "paid_operations_allowed": False,
        "sites": sites,
    }
    # Touch digest to prove determinism callers can compute.
    digest_obj(manifest)
    return manifest
