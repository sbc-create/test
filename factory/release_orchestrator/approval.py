"""Owner approval binding for a single immutable release manifest."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from factory.release_orchestrator.manifest import digest_obj, load_manifest

APPROVAL_REPLAY = "OWNER_APPROVAL_REPLAY_BLOCKED"
APPROVAL_EXPIRED = "EXPIRED_APPROVAL_BLOCKED"
APPROVAL_DIGEST_MISMATCH = "OWNER_APPROVAL_MANIFEST_DIGEST_MISMATCH"
APPROVAL_SCOPE_MISMATCH = "OWNER_APPROVAL_SCOPE_MISMATCH"
APPROVAL_CONSUMED = "OWNER_APPROVAL_FINAL_STATE=CONSUMED"


class ApprovalError(ValueError):
    def __init__(self, code: str, detail: str = ""):
        self.code = code
        super().__init__(code if not detail else f"{code}: {detail}")


def _parse_dt(value: str) -> datetime:
    text = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def build_approval(
    *,
    approval_id: str,
    release_id: str,
    manifest: dict[str, Any],
    approved_by: str,
    allowed_indexability_changes: bool,
    allowed_dns_changes: bool,
    allowed_paid_operations: bool,
    expires_at: str,
    approved_at: str | None = None,
) -> dict[str, Any]:
    sites = manifest["sites"]
    return {
        "schema_version": "1.0.0",
        "approval_id": approval_id,
        "release_id": release_id,
        "manifest_digest": digest_obj(manifest),
        "exact_site_ids": [s["site_id"] for s in sites],
        "exact_artifact_digests": {s["site_id"]: s["artifact_sha256"] for s in sites},
        "allowed_indexability_changes": allowed_indexability_changes,
        "allowed_dns_changes": allowed_dns_changes,
        "allowed_paid_operations": allowed_paid_operations,
        "expires_at": expires_at,
        "approved_by": approved_by,
        "approved_at": approved_at or datetime.now(timezone.utc).isoformat(),
        "state": "ACTIVE",
    }


def load_approval(path: Path | str) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ApprovalError(APPROVAL_SCOPE_MISMATCH, "approval root")
    return data


def write_approval(path: Path | str, approval: dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(approval, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def assert_usable_for_manifest(approval: dict[str, Any], manifest: dict[str, Any] | Path) -> None:
    if isinstance(manifest, (str, Path)):
        manifest = load_manifest(manifest)
    if approval.get("state") == "CONSUMED":
        raise ApprovalError(APPROVAL_REPLAY, APPROVAL_CONSUMED)
    if approval.get("state") in {"EXPIRED", "REVOKED"}:
        raise ApprovalError(APPROVAL_EXPIRED, str(approval.get("state")))
    if approval.get("release_id") != manifest.get("release_id"):
        raise ApprovalError(APPROVAL_SCOPE_MISMATCH, "release_id")
    digest = digest_obj(manifest)
    if approval.get("manifest_digest") != digest:
        raise ApprovalError(APPROVAL_DIGEST_MISMATCH, digest)
    now = datetime.now(timezone.utc)
    if _parse_dt(str(approval["expires_at"])) <= now:
        raise ApprovalError(APPROVAL_EXPIRED, approval["expires_at"])
    expected_sites = list(approval.get("exact_site_ids") or [])
    actual_sites = [s["site_id"] for s in manifest["sites"]]
    if expected_sites != actual_sites:
        raise ApprovalError(APPROVAL_SCOPE_MISMATCH, "exact_site_ids")
    digests = approval.get("exact_artifact_digests") or {}
    for site in manifest["sites"]:
        sid = site["site_id"]
        if digests.get(sid) != site["artifact_sha256"]:
            raise ApprovalError(APPROVAL_SCOPE_MISMATCH, f"artifact:{sid}")
    if bool(manifest.get("dns_mutations_allowed")) and not approval.get("allowed_dns_changes"):
        raise ApprovalError(APPROVAL_SCOPE_MISMATCH, "dns")
    if bool(manifest.get("paid_operations_allowed")) and not approval.get("allowed_paid_operations"):
        raise ApprovalError(APPROVAL_SCOPE_MISMATCH, "paid")
    if bool(manifest.get("indexability_mutations_allowed")) and not approval.get(
        "allowed_indexability_changes"
    ):
        raise ApprovalError(APPROVAL_SCOPE_MISMATCH, "indexability")


def consume(approval: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(approval)
    out["state"] = "CONSUMED"
    return out
