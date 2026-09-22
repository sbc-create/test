"""Authoritative release registry: site-profiles + release-registry overlay.

Exact-domain lookup only. Forbidden:
- TLD-based policy selection
- fallback .site/.org/.biz
- substring domain matching
- hardcoded allowlists outside this registry
- guessed systemd units
- one service for different site_ids without explicit contract
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from factory.paths import PATHS

REGISTRY_REL = Path("config/release-registry.json")
PROFILES_REL = Path("config/site-profiles")

# Allowlisted handler verbs — never free-form shell.
ALLOWED_HANDLERS = frozenset(
    {
        "lords_static_build",
        "lords_static_deploy",
        "lords_static_rollback",
        "nova_static_build",
        "nova_static_deploy",
        "nova_static_rollback",
        "yummy_compose_build",
        "yummy_compose_deploy",
        "yummy_compose_rollback",
        "systemd_restart_unit",
        "noop_shadow",
    }
)


class RegistryError(ValueError):
    """Registry incomplete, inconsistent, or lookup violated exact-domain rules."""


@dataclass(frozen=True)
class SiteReleaseRecord:
    site_id: str
    domain: str
    www_policy: str
    site_family: str
    template_profile: str
    design_id: str
    repository: str
    source_branch: str
    build_command: str
    artifact_type: str
    artifact_destination: str
    runtime: str
    service_name: str
    container_name_if_any: str | None
    health_url: str
    version_url: str
    smoke_profile: str
    expected_indexability: str
    robots_policy: str
    sitemap_policy: str
    canonical_policy: str
    analytics_policy: str
    deploy_handler: str
    restart_handler: str
    rollback_handler: str
    data_sources: tuple[str, ...]
    owner_state: str
    enabled: bool
    profile_domains: tuple[str, ...]
    profile_indexing_enabled: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "site_id": self.site_id,
            "domain": self.domain,
            "www_policy": self.www_policy,
            "site_family": self.site_family,
            "template_profile": self.template_profile,
            "design_id": self.design_id,
            "repository": self.repository,
            "source_branch": self.source_branch,
            "build_command": self.build_command,
            "artifact_type": self.artifact_type,
            "artifact_destination": self.artifact_destination,
            "runtime": self.runtime,
            "service_name": self.service_name,
            "container_name_if_any": self.container_name_if_any,
            "health_url": self.health_url,
            "version_url": self.version_url,
            "smoke_profile": self.smoke_profile,
            "expected_indexability": self.expected_indexability,
            "robots_policy": self.robots_policy,
            "sitemap_policy": self.sitemap_policy,
            "canonical_policy": self.canonical_policy,
            "analytics_policy": self.analytics_policy,
            "deploy_handler": self.deploy_handler,
            "restart_handler": self.restart_handler,
            "rollback_handler": self.rollback_handler,
            "data_sources": list(self.data_sources),
            "owner_state": self.owner_state,
            "enabled": self.enabled,
            "profile_domains": list(self.profile_domains),
            "profile_indexing_enabled": self.profile_indexing_enabled,
        }


def _repo_root() -> Path:
    return PATHS.root


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RegistryError(f"missing registry file: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise RegistryError(f"unreadable registry file: {path}: {exc}") from exc


def normalize_domain(raw: str) -> str:
    """Normalize for exact equality. Strips scheme/path/port and a single www. prefix.

    Does not strip arbitrary leading characters (no lstrip('www.')).
    Does not invent alternate TLDs.
    """
    value = (raw or "").strip().lower()
    if "://" in value:
        value = value.split("://", 1)[1]
    value = value.split("/", 1)[0]
    value = value.split(":", 1)[0]
    if value.startswith("www."):
        value = value[4:]
    return value


def load_overlay(path: Path | None = None) -> dict[str, Any]:
    root = _repo_root()
    overlay_path = path or (root / REGISTRY_REL)
    data = _load_json(overlay_path)
    if not isinstance(data, dict):
        raise RegistryError("release-registry root must be an object")
    if data.get("schema_version") != "1.0.0":
        raise RegistryError(f"unsupported release-registry schema_version: {data.get('schema_version')}")
    if data.get("registry_id") != "site-factory-core-release":
        raise RegistryError("registry_id must be site-factory-core-release")
    return data


def load_profile(site_id: str) -> dict[str, Any]:
    path = _repo_root() / PROFILES_REL / f"{site_id}.json"
    data = _load_json(path)
    if not isinstance(data, dict):
        raise RegistryError(f"profile for {site_id} is not an object")
    if data.get("site_id") != site_id:
        raise RegistryError(f"profile site_id mismatch for {site_id}")
    return data


def _validate_handlers(row: dict[str, Any]) -> None:
    for key in ("build_command", "deploy_handler", "restart_handler", "rollback_handler"):
        verb = row.get(key)
        if verb not in ALLOWED_HANDLERS:
            raise RegistryError(f"{row.get('site_id')}: handler {key}={verb!r} not allowlisted")


def _indexability_from_profile(profile: dict[str, Any]) -> str:
    seo = profile.get("seo_profile") or {}
    return "OPEN" if seo.get("indexing_enabled") is True else "CLOSED"


def build_records(overlay: dict[str, Any] | None = None) -> list[SiteReleaseRecord]:
    data = overlay or load_overlay()
    sites = data.get("sites")
    if not isinstance(sites, list) or not sites:
        raise RegistryError("release-registry.sites must be a non-empty array")

    records: list[SiteReleaseRecord] = []
    seen_ids: set[str] = set()
    seen_domains: set[str] = set()
    service_owners: dict[str, str] = {}

    for row in sites:
        if not isinstance(row, dict):
            raise RegistryError("site row must be an object")
        site_id = row["site_id"]
        domain = normalize_domain(row["domain"])
        if site_id in seen_ids:
            raise RegistryError(f"duplicate site_id in release-registry: {site_id}")
        if domain in seen_domains:
            raise RegistryError(f"duplicate domain in release-registry: {domain}")
        seen_ids.add(site_id)
        seen_domains.add(domain)

        service = str(row["service_name"])
        if service in service_owners and service_owners[service] != site_id:
            raise RegistryError(
                f"service_name {service} claimed by {service_owners[service]} and {site_id} "
                "without explicit shared-service contract"
            )
        service_owners[service] = site_id

        _validate_handlers(row)
        profile = load_profile(site_id)
        profile_domains = tuple(normalize_domain(d) for d in profile.get("domains") or [])
        if domain not in profile_domains:
            raise RegistryError(
                f"{site_id}: release-registry domain {domain} not in site-profile domains {profile_domains}"
            )
        expected = row["expected_indexability"]
        profile_ix = _indexability_from_profile(profile)
        if expected != profile_ix:
            raise RegistryError(
                f"{site_id}: expected_indexability={expected} disagrees with "
                f"site-profile indexing_enabled→{profile_ix}"
            )

        records.append(
            SiteReleaseRecord(
                site_id=site_id,
                domain=domain,
                www_policy=row["www_policy"],
                site_family=row["site_family"],
                template_profile=row["template_profile"],
                design_id=row["design_id"],
                repository=row["repository"],
                source_branch=row["source_branch"],
                build_command=row["build_command"],
                artifact_type=row["artifact_type"],
                artifact_destination=row["artifact_destination"],
                runtime=row["runtime"],
                service_name=service,
                container_name_if_any=row.get("container_name_if_any"),
                health_url=row["health_url"],
                version_url=row["version_url"],
                smoke_profile=row["smoke_profile"],
                expected_indexability=expected,
                robots_policy=row["robots_policy"],
                sitemap_policy=row["sitemap_policy"],
                canonical_policy=row["canonical_policy"],
                analytics_policy=row["analytics_policy"],
                deploy_handler=row["deploy_handler"],
                restart_handler=row["restart_handler"],
                rollback_handler=row["rollback_handler"],
                data_sources=tuple(row.get("data_sources") or ()),
                owner_state=row["owner_state"],
                enabled=bool(row["enabled"]),
                profile_domains=profile_domains,
                profile_indexing_enabled=profile_ix == "OPEN",
            )
        )
    return records


class ReleaseRegistry:
    """In-memory Core release registry with exact-domain and site_id indexes."""

    def __init__(self, records: Iterable[SiteReleaseRecord]):
        self._by_id: dict[str, SiteReleaseRecord] = {}
        self._by_domain: dict[str, SiteReleaseRecord] = {}
        for rec in records:
            self._by_id[rec.site_id] = rec
            self._by_domain[rec.domain] = rec

    @classmethod
    def load(cls, path: Path | None = None) -> "ReleaseRegistry":
        return cls(build_records(load_overlay(path) if path else None))

    def get(self, site_id: str) -> SiteReleaseRecord:
        try:
            return self._by_id[site_id]
        except KeyError as exc:
            raise RegistryError(f"unknown site_id: {site_id}") from exc

    def by_domain(self, domain: str) -> SiteReleaseRecord:
        key = normalize_domain(domain)
        # Refuse substring / suffix matching: only exact key.
        if key not in self._by_domain:
            raise RegistryError(f"unknown domain (exact match required): {key}")
        return self._by_domain[key]

    def enabled_sites(self) -> list[SiteReleaseRecord]:
        return [r for r in self._by_id.values() if r.enabled]

    def all_sites(self) -> list[SiteReleaseRecord]:
        return list(self._by_id.values())

    def require_unique_services(self, site_ids: Iterable[str]) -> None:
        owners: dict[str, str] = {}
        for sid in site_ids:
            rec = self.get(sid)
            if rec.service_name in owners and owners[rec.service_name] != sid:
                raise RegistryError(
                    f"duplicate service in batch: {rec.service_name} "
                    f"({owners[rec.service_name]} vs {sid})"
                )
            owners[rec.service_name] = sid
