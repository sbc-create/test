"""Tenant and site resolution.

The whole isolation story rests on one decision: `tenant_id` and `site_id` are
*derived by the server*, from the request host or from a service credential,
and are never read from anything the caller can type. A query parameter, a JSON
body field, a cookie or a value baked into the frontend config are all attacker
controlled, so this module refuses them outright rather than validating them —
:func:`reject_client_supplied_scope` raises on their mere presence, because a
request that carries `tenant_id` at all is either a bug in an adapter or a
probe, and both deserve the same answer.

The second decision is that a discussion is keyed by content, not by address:

    (tenant_id, site_id, resource_type, canonical_content_id)

A slug change, a domain migration or a canonical-URL rewrite must not orphan a
thread, which is exactly what would happen if the URL were the key.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .errors import BadRequest, CrossTenantDenied, NotFound, ValidationFailed

# Tenants this platform is authorised to serve. The list is closed: an unknown
# tenant is a configuration error, never an implicit new customer.
ALLOWED_TENANTS = ("lords", "zona", "animedia", "yummy")

# Conservative identifier shape: lowercase, digits, dash, underscore. It keeps
# ids safe in cache keys, file paths, metric labels and SQL parameters alike.
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")

# Resource kinds a thread may hang off. Closed for the same reason as tenants.
RESOURCE_TYPES = ("title", "episode", "collection", "article", "person")

MODERATION_MODES = ("pre", "post")
SEO_MODES = ("user_initiated", "ssr_first_page", "ssr_paginated")

# Fields a client is never allowed to send. Presence is refused, not ignored:
# silently dropping them would let a caller believe the override worked.
CLIENT_FORBIDDEN_SCOPE_FIELDS = frozenset(
    {"tenant_id", "site_id", "tenant", "site", "x-tenant-id", "x-site-id"}
)


def validate_identifier(value: str, *, field_name: str) -> str:
    if not isinstance(value, str) or not _ID_RE.match(value):
        raise ValidationFailed(f"{field_name} has an invalid shape", field=field_name)
    return value


def reject_client_supplied_scope(payload: Mapping[str, Any] | None) -> None:
    """Refuse any request that tries to name its own tenant or site."""
    if not payload:
        return
    for key in payload:
        if str(key).strip().lower() in CLIENT_FORBIDDEN_SCOPE_FIELDS:
            raise BadRequest(
                "tenant and site are resolved by the server and may not be supplied",
                offending_field=str(key),
            )


@dataclass(frozen=True, slots=True)
class TenantScope:
    """The server-derived scope carried by every single operation.

    Every store call takes one of these. That is what makes a missing `WHERE
    tenant_id = ?` a type error at the call site rather than a leak found in
    production.
    """

    tenant_id: str
    site_id: str

    def __post_init__(self) -> None:
        validate_identifier(self.tenant_id, field_name="tenant_id")
        validate_identifier(self.site_id, field_name="site_id")
        if self.tenant_id not in ALLOWED_TENANTS:
            raise ValidationFailed(f"tenant {self.tenant_id!r} is not allowed", field="tenant_id")

    @property
    def key(self) -> str:
        return f"{self.tenant_id}:{self.site_id}"

    def assert_owns(self, tenant_id: str, site_id: str) -> None:
        """Guard used right after every row read.

        Raises :class:`CrossTenantDenied`, which is a 404 on the wire, so a
        probe cannot tell a foreign object from a missing one.
        """
        if tenant_id != self.tenant_id or site_id != self.site_id:
            raise CrossTenantDenied(
                "object belongs to another tenant/site",
                expected=self.key,
                actual=f"{tenant_id}:{site_id}",
            )


@dataclass(frozen=True, slots=True)
class ResourceRef:
    """What a thread is about. Stable across slug, domain and canonical churn."""

    resource_type: str
    canonical_content_id: str

    def __post_init__(self) -> None:
        if self.resource_type not in RESOURCE_TYPES:
            raise ValidationFailed(
                f"resource_type {self.resource_type!r} is not supported", field="resource_type"
            )
        validate_identifier(self.canonical_content_id, field_name="canonical_content_id")


@dataclass(frozen=True)
class SiteBinding:
    """Everything one site pins about the shared module.

    Pinning is the point. `module_version` and `artifact_checksum` are required
    and must be exact — there is no `latest`, because a floating version turns
    "which code is on animedia right now" into a question nobody can answer
    after the fact.
    """

    tenant_id: str
    site_id: str
    hosts: tuple[str, ...]
    allowed_origins: tuple[str, ...]
    module_version: str
    artifact_checksum: str
    theme: str = "auto"
    language: str = "ru"
    moderation_mode: str = "pre"
    read_enabled: int = 0
    write_enabled: int = 0
    publication_enabled: int = 0
    seo_mode: str = "user_initiated"
    rollout_percent: int = 0
    max_depth: int = 3
    max_length: int = 4000
    max_links: int = 2
    extra: Mapping[str, Any] = field(default_factory=dict)

    # Version strings that would make the deployed artifact unknowable.
    _FLOATING = frozenset({"latest", "main", "head", "", "*", "stable", "current"})

    def __post_init__(self) -> None:
        validate_identifier(self.tenant_id, field_name="tenant_id")
        validate_identifier(self.site_id, field_name="site_id")
        if self.tenant_id not in ALLOWED_TENANTS:
            raise ValidationFailed(f"tenant {self.tenant_id!r} is not allowed", field="tenant_id")
        if str(self.module_version).strip().lower() in self._FLOATING:
            raise ValidationFailed(
                "module_version must be an exact pinned version, not a floating ref",
                field="module_version",
            )
        if not re.fullmatch(r"[0-9a-f]{64}", str(self.artifact_checksum)):
            raise ValidationFailed(
                "artifact_checksum must be a sha256 hex digest", field="artifact_checksum"
            )
        if self.moderation_mode not in MODERATION_MODES:
            raise ValidationFailed(
                f"moderation_mode {self.moderation_mode!r} is not supported",
                field="moderation_mode",
            )
        if self.seo_mode not in SEO_MODES:
            raise ValidationFailed(f"seo_mode {self.seo_mode!r} is not supported", field="seo_mode")
        if not 0 <= int(self.rollout_percent) <= 100:
            raise ValidationFailed("rollout_percent must be 0..100", field="rollout_percent")
        if not self.hosts:
            raise ValidationFailed("a site binding needs at least one host", field="hosts")
        for host in self.hosts:
            if host != host.strip().lower() or ":" in host or "/" in host:
                raise ValidationFailed(
                    "hosts must be bare lowercase hostnames without port or path", field="hosts"
                )
        for origin in self.allowed_origins:
            # Exact origins only. A wildcard here would undo the CORS allowlist.
            if not origin.startswith(("https://", "http://")) or origin.endswith("/"):
                raise ValidationFailed(
                    "allowed_origins must be exact scheme+host[:port] origins",
                    field="allowed_origins",
                )
            if "*" in origin:
                raise ValidationFailed("wildcard origins are not permitted", field="allowed_origins")
        if self.max_depth < 1 or self.max_depth > 10:
            raise ValidationFailed("max_depth must be 1..10", field="max_depth")

    @property
    def scope(self) -> TenantScope:
        return TenantScope(self.tenant_id, self.site_id)

    def to_public_config(self) -> dict[str, Any]:
        """What the browser widget is allowed to know.

        Note what is absent: no credentials, no endpoint allowlist, no internal
        ids. The widget learns presentation and limits, nothing that would help
        it address another site.
        """
        return {
            "site_id": self.site_id,
            "module_version": self.module_version,
            "theme": self.theme,
            "language": self.language,
            "max_length": self.max_length,
            "max_depth": self.max_depth,
            "moderation_mode": self.moderation_mode,
            "read_enabled": int(self.read_enabled),
            "write_enabled": int(self.write_enabled),
            "seo_mode": self.seo_mode,
        }


class SiteRegistry:
    """Host → site binding. The only trusted source of scope."""

    def __init__(self, bindings: Iterable[SiteBinding]) -> None:
        self._by_key: dict[str, SiteBinding] = {}
        self._by_host: dict[str, SiteBinding] = {}
        for binding in bindings:
            key = f"{binding.tenant_id}:{binding.site_id}"
            if key in self._by_key:
                raise ValidationFailed(f"duplicate site binding {key}", field="site_id")
            self._by_key[key] = binding
            for host in binding.hosts:
                if host in self._by_host:
                    # Two sites on one host would make resolution ambiguous, and
                    # an ambiguous tenant is a cross-tenant leak waiting to happen.
                    raise ValidationFailed(
                        f"host {host!r} is claimed by two sites", field="hosts"
                    )
                self._by_host[host] = binding

    @classmethod
    def from_file(cls, path: str | Path) -> SiteRegistry:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_mapping(raw)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> SiteRegistry:
        bindings = []
        for entry in raw.get("sites", []):
            known = {f.name for f in SiteBinding.__dataclass_fields__.values()}  # type: ignore[attr-defined]
            kwargs = {k: v for k, v in entry.items() if k in known}
            kwargs["hosts"] = tuple(entry.get("hosts", ()))
            kwargs["allowed_origins"] = tuple(entry.get("allowed_origins", ()))
            bindings.append(SiteBinding(**kwargs))
        return cls(bindings)

    @staticmethod
    def normalise_host(host: str) -> str:
        """Strip port, trailing dot and case. Reject anything else odd."""
        if not isinstance(host, str):
            raise ValidationFailed("host must be a string", field="host")
        value = host.strip().lower().rstrip(".")
        if value.startswith("["):  # IPv6 literal with optional port
            value = value.partition("]")[0].lstrip("[")
        elif value.count(":") == 1:
            value = value.partition(":")[0]
        if not value or "/" in value or " " in value:
            raise ValidationFailed("host is not a valid hostname", field="host")
        return value

    def resolve_host(self, host: str) -> SiteBinding:
        """Trusted resolution path for browser traffic."""
        binding = self._by_host.get(self.normalise_host(host))
        if binding is None:
            # Unknown Host header must not enumerate configured sites.
            raise NotFound("no site is bound to this host", host=host)
        return binding

    def resolve_service(self, tenant_id: str, site_id: str) -> SiteBinding:
        """Trusted resolution path for a scoped service credential.

        The caller must already have proven, by verifying a token, that it is
        entitled to this pair. This method is not authentication; it turns an
        authenticated pair into a binding and refuses unknown pairs.
        """
        binding = self._by_key.get(f"{tenant_id}:{site_id}")
        if binding is None:
            raise NotFound("no such site", tenant_id=tenant_id, site_id=site_id)
        return binding

    def get(self, tenant_id: str, site_id: str) -> SiteBinding:
        return self.resolve_service(tenant_id, site_id)

    def all_bindings(self) -> tuple[SiteBinding, ...]:
        return tuple(self._by_key.values())

    def origin_allowed(self, binding: SiteBinding, origin: str | None) -> bool:
        """Exact-match CORS. No suffix matching, no wildcards, no null origin."""
        if not origin:
            return False
        return origin.strip() in binding.allowed_origins
