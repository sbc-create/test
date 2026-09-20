"""Immutable release manifest: canonical JSON + digest + schema validation."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from factory.release_orchestrator.registry import ReleaseRegistry, RegistryError

SCHEMA_VERSION = "1.0.0"

DENIED_DIGEST_MISMATCH = "RELEASE_DENIED_MANIFEST_DIGEST_MISMATCH"
DENIED_UNKNOWN_FIELD = "RELEASE_DENIED_UNKNOWN_FIELD"
DENIED_DUPLICATE_SITE = "RELEASE_DENIED_DUPLICATE_SITE_ID"
DENIED_DUPLICATE_DOMAIN = "RELEASE_DENIED_DUPLICATE_DOMAIN"
DENIED_DUPLICATE_SERVICE = "RELEASE_DENIED_DUPLICATE_SERVICE"
DENIED_ARTIFACT_COLLISION = "RELEASE_DENIED_ARTIFACT_PATH_DIGEST_COLLISION"
DENIED_EXPIRED = "RELEASE_DENIED_EXPIRED"
DENIED_SECRETS = "RELEASE_DENIED_SECRETS_PRESENT"

SECRET_KEY_FRAGMENTS = (
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "private_key",
    "credential",
)


class ManifestError(ValueError):
    def __init__(self, code: str, detail: str = ""):
        self.code = code
        message = code if not detail else f"{code}: {detail}"
        super().__init__(message)


def _parse_dt(value: str) -> datetime:
    text = value.replace("Z", "+00:00")
    return datetime.fromisoformat(text)


def canonical_dumps(obj: Any) -> str:
    """Canonical JSON: sorted keys, no insignificant whitespace, UTF-8, no NaN."""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_obj(obj: Any) -> str:
    return digest_bytes(canonical_dumps(obj).encode("utf-8"))


def _walk_for_secrets(node: Any, path: str = "") -> list[str]:
    hits: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            key_l = str(key).lower()
            here = f"{path}.{key}" if path else str(key)
            if any(frag in key_l for frag in SECRET_KEY_FRAGMENTS):
                hits.append(here)
            hits.extend(_walk_for_secrets(value, here))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            hits.extend(_walk_for_secrets(value, f"{path}[{i}]"))
    return hits


def validate_manifest_structure(manifest: dict[str, Any], *, registry: ReleaseRegistry | None = None) -> None:
    if not isinstance(manifest, dict):
        raise ManifestError(DENIED_UNKNOWN_FIELD, "root must be object")
    required = {
        "schema_version",
        "release_id",
        "owner_approval_id",
        "created_at",
        "expires_at",
        "requested_by",
        "release_mode",
        "canary_site_id",
        "failure_policy",
        "indexability_mutations_allowed",
        "dns_mutations_allowed",
        "paid_operations_allowed",
        "sites",
    }
    unknown = set(manifest) - required
    if unknown:
        raise ManifestError(DENIED_UNKNOWN_FIELD, ",".join(sorted(unknown)))
    missing = required - set(manifest)
    if missing:
        raise ManifestError(DENIED_UNKNOWN_FIELD, f"missing:{','.join(sorted(missing))}")
    if manifest["schema_version"] != SCHEMA_VERSION:
        raise ManifestError(DENIED_UNKNOWN_FIELD, "schema_version")

    secret_hits = _walk_for_secrets(manifest)
    if secret_hits:
        raise ManifestError(DENIED_SECRETS, ",".join(secret_hits))

    sites = manifest["sites"]
    if not isinstance(sites, list) or not sites:
        raise ManifestError(DENIED_UNKNOWN_FIELD, "sites")

    site_ids: set[str] = set()
    domains: set[str] = set()
    path_digests: dict[str, str] = {}
    site_required = {
        "site_id",
        "domain",
        "source_head",
        "artifact_path",
        "artifact_sha256",
        "manifest_sha256",
        "template_profile",
        "expected_design_id",
        "expected_build_id",
        "expected_indexability_before",
        "expected_indexability_after",
        "expected_catalog_revision",
        "expected_details_revision",
        "smoke_profile",
        "rollback_required",
    }

    for row in sites:
        if not isinstance(row, dict):
            raise ManifestError(DENIED_UNKNOWN_FIELD, "site row")
        extra = set(row) - site_required
        if extra:
            raise ManifestError(DENIED_UNKNOWN_FIELD, f"site:{','.join(sorted(extra))}")
        miss = site_required - set(row)
        if miss:
            raise ManifestError(DENIED_UNKNOWN_FIELD, f"site-missing:{','.join(sorted(miss))}")
        sid = row["site_id"]
        dom = row["domain"]
        if sid in site_ids:
            raise ManifestError(DENIED_DUPLICATE_SITE, sid)
        if dom in domains:
            raise ManifestError(DENIED_DUPLICATE_DOMAIN, dom)
        site_ids.add(sid)
        domains.add(dom)
        apath = row["artifact_path"]
        adigest = row["artifact_sha256"]
        if apath in path_digests and path_digests[apath] != adigest:
            raise ManifestError(DENIED_ARTIFACT_COLLISION, apath)
        path_digests[apath] = adigest

    canary = manifest["canary_site_id"]
    if canary not in site_ids:
        raise ManifestError(DENIED_UNKNOWN_FIELD, f"canary_site_id not in sites: {canary}")

    if registry is not None:
        try:
            registry.require_unique_services(site_ids)
            for sid in site_ids:
                rec = registry.get(sid)
                row = next(s for s in sites if s["site_id"] == sid)
                if row["domain"] != rec.domain:
                    raise ManifestError(DENIED_UNKNOWN_FIELD, f"domain mismatch for {sid}")
        except RegistryError as exc:
            raise ManifestError(DENIED_DUPLICATE_SERVICE, str(exc)) from exc

    now = datetime.now(timezone.utc)
    try:
        expires = _parse_dt(manifest["expires_at"])
    except ValueError as exc:
        raise ManifestError(DENIED_UNKNOWN_FIELD, "expires_at") from exc
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= now:
        raise ManifestError(DENIED_EXPIRED, manifest["expires_at"])


def load_manifest(path: Path | str) -> dict[str, Any]:
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ManifestError(DENIED_UNKNOWN_FIELD, "root")
    return data


def write_manifest(path: Path | str, manifest: dict[str, Any]) -> str:
    """Write canonical JSON and companion .sha256. Returns digest."""
    validate_manifest_structure(manifest)
    digest = digest_obj(manifest)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_dumps(manifest) + "\n"
    p.write_text(payload, encoding="utf-8")
    (p.parent / f"{p.name}.sha256").write_text(f"{digest}  {p.name}\n", encoding="utf-8")
    return digest


def verify_immutable(path: Path | str, expected_digest: str) -> dict[str, Any]:
    manifest = load_manifest(path)
    actual = digest_obj(manifest)
    if actual != expected_digest:
        raise ManifestError(DENIED_DIGEST_MISMATCH, f"expected={expected_digest} actual={actual}")
    validate_manifest_structure(manifest)
    return manifest


def bind_approval(manifest: dict[str, Any], approval_id: str) -> dict[str, Any]:
    out = deepcopy(manifest)
    out["owner_approval_id"] = approval_id
    return out
