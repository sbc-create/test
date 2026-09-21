"""Resolve which systemd unit actually serves a domain, and compare to the registry.

The registry declares ``service_name`` per site. That declaration is a claim, not
evidence. On this host the claim and the routed reality disagree: nginx proxies
each Lords domain to a port served by a ``*-nova-*`` unit, while the registry
names a legacy ``lords-0N.service`` listening on a different port.

Restarting the declared-but-unrouted unit would leave the live domain untouched
while smoke — which talks to the domain — still passed. That is a false PASS, so
a live release must refuse to start until the binding is confirmed.

Everything here is read-only: it parses nginx configuration and systemd unit
files. It never restarts, rewrites or reloads anything.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

NGINX_SITE_DIR = Path("/etc/nginx/lords")
SYSTEMD_UNIT_DIR = Path("/etc/systemd/system")

# `server_name a.example b.example;`
_SERVER_NAME_RE = re.compile(r"^\s*server_name\s+([^;]+);", re.MULTILINE)
# `proxy_pass http://127.0.0.1:9111;` / `.../healthz;` — own line or inside a
# one-line `location / { ... }`, so the directive is not anchored to line start.
_PROXY_PASS_RE = re.compile(r"\bproxy_pass\s+https?://127\.0\.0\.1:(\d+)")
# `ExecStart=/usr/bin/python3 /srv/... --port 9111`
_EXEC_PORT_RE = re.compile(r"--port[=\s]+(\d+)")
# `Environment=LORDS_PORT=9102`
_ENV_PORT_RE = re.compile(r"^\s*Environment=(?:LORDS_)?PORT=(\d+)", re.MULTILINE)


class ServiceBindingError(RuntimeError):
    pass


@dataclass
class DomainBinding:
    domain: str
    site_id: str
    registry_service: str
    routed_port: int | None = None
    routed_service: str | None = None
    registry_service_port: int | None = None
    match: bool = False
    reason: str = "unmeasured"

    def as_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "site_id": self.site_id,
            "registry_service": self.registry_service,
            "routed_port": self.routed_port,
            "routed_service": self.routed_service,
            "registry_service_port": self.registry_service_port,
            "match": self.match,
            "reason": self.reason,
        }


@dataclass
class BindingReport:
    bindings: list[DomainBinding] = field(default_factory=list)
    nginx_dir: str = str(NGINX_SITE_DIR)
    unit_dir: str = str(SYSTEMD_UNIT_DIR)

    @property
    def ok(self) -> bool:
        return bool(self.bindings) and all(b.match for b in self.bindings)

    def mismatches(self) -> list[DomainBinding]:
        return [b for b in self.bindings if not b.match]

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "nginx_dir": self.nginx_dir,
            "unit_dir": self.unit_dir,
            "bindings": [b.as_dict() for b in self.bindings],
        }


def _unit_port(text: str) -> int | None:
    """Port a unit listens on, from --port or an Environment= declaration."""
    for line in text.splitlines():
        if line.startswith("ExecStart="):
            m = _EXEC_PORT_RE.search(line)
            if m:
                return int(m.group(1))
    m = _ENV_PORT_RE.search(text)
    return int(m.group(1)) if m else None


def unit_ports(unit_dir: Path = SYSTEMD_UNIT_DIR) -> dict[str, int]:
    """Map unit name → listening port for every readable *.service file."""
    out: dict[str, int] = {}
    if not unit_dir.exists():
        return out
    for unit in sorted(unit_dir.glob("*.service")):
        if "@" in unit.name:
            continue  # template unit; instance port is not statically knowable
        try:
            text = unit.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        port = _unit_port(text)
        if port is not None:
            out[unit.name] = port
    return out


def routed_port_for_domain(domain: str, nginx_dir: Path = NGINX_SITE_DIR) -> int | None:
    """Upstream port nginx proxies ``domain`` to, from active (non-.bak) confs."""
    if not nginx_dir.exists():
        return None
    target = domain.lower().strip().rstrip(".")
    for conf in sorted(nginx_dir.glob("*.conf")):
        try:
            text = conf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        # Only the apex server block counts; a www-redirect block has no proxy_pass.
        for block in text.split("server {"):
            names: set[str] = set()
            for m in _SERVER_NAME_RE.finditer(block):
                names.update(n.lower().rstrip(".") for n in m.group(1).split())
            if target not in names:
                continue
            port = _PROXY_PASS_RE.search(block)
            if port:
                return int(port.group(1))
    return None


def resolve_bindings(
    site_ids: list[str],
    *,
    registry: Any = None,
    nginx_dir: Path = NGINX_SITE_DIR,
    unit_dir: Path = SYSTEMD_UNIT_DIR,
) -> BindingReport:
    """Compare each site's declared unit against the one nginx actually routes to."""
    if registry is None:
        from factory.release_orchestrator.registry import ReleaseRegistry

        registry = ReleaseRegistry.load()

    ports = unit_ports(unit_dir)
    by_port: dict[int, list[str]] = {}
    for unit, port in ports.items():
        by_port.setdefault(port, []).append(unit)

    report = BindingReport(nginx_dir=str(nginx_dir), unit_dir=str(unit_dir))
    for site_id in site_ids:
        rec = registry.get(site_id)
        binding = DomainBinding(
            domain=rec.domain,
            site_id=site_id,
            registry_service=rec.service_name,
            registry_service_port=ports.get(rec.service_name),
        )
        routed = routed_port_for_domain(rec.domain, nginx_dir)
        binding.routed_port = routed

        if routed is None:
            binding.reason = "NGINX_ROUTE_UNMEASURED"
        else:
            candidates = by_port.get(routed, [])
            if len(candidates) == 1:
                binding.routed_service = candidates[0]
            elif len(candidates) > 1:
                binding.routed_service = None
                binding.reason = f"AMBIGUOUS_UNITS_ON_PORT_{routed}: {sorted(candidates)}"
            else:
                binding.reason = f"NO_UNIT_FOUND_FOR_PORT_{routed}"

            if binding.routed_service is not None:
                if binding.routed_service == rec.service_name:
                    binding.match = True
                    binding.reason = "MATCH"
                else:
                    binding.reason = (
                        f"MISMATCH: registry declares {rec.service_name}"
                        f"(port={binding.registry_service_port}) but {rec.domain} is routed to "
                        f"port {routed} served by {binding.routed_service}"
                    )
        report.bindings.append(binding)
    return report


def assert_live_binding(site_ids: list[str], **kwargs: Any) -> BindingReport:
    """Gate for live (mutating) releases. Raises unless every binding is confirmed."""
    report = resolve_bindings(site_ids, **kwargs)
    bad = report.mismatches()
    if bad:
        detail = "; ".join(f"{b.site_id}: {b.reason}" for b in bad)
        raise ServiceBindingError(f"BLOCKED_SERVICE_BINDING — {detail}")
    return report
