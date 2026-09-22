"""Identifier allocation for a new site: derived from registries, never guessed.

Creating a site needs three values that do not exist yet — a `site_id`, a
systemd `service_name` and a loopback `port`. Picking any of them by eye is how
a new site lands on a port another service already holds, or inherits a unit
name that something else restarts.

This module answers each of the three from what the fleet already declares, and
refuses when the declarations do not support an answer. Four independent
sources are unioned, because one source is not a fleet:

1. `config/site-profiles/*.json` — Core identity (site_id, domains, family);
2. `config/release-registry.json` — ops overlay (site_id, domain, service_name);
3. `lords-runtime-registry.json` — what the dispatcher binds (site_id, port, unit);
4. `/etc/systemd/system/*.service` — units actually installed, and the ports in
   their `ExecStart`;

plus the kernel's list of listening sockets, which is the only source that knows
about a port held by something that is in no registry at all.

A claim from *any* source disqualifies a candidate. That asymmetry is deliberate:
a false claim costs one identifier, a missed claim costs a collision.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

#: Loopback band the nova frontends live in. Derived from the installed units
#: (9110-9132 in use at the time of writing), widened to the enclosing hundred
#: so the band does not have to move every time a family is added. Allocation
#: never leaves it: a port outside the band would not be proxied by any vhost
#: template and would be invisible to the fleet's own conventions.
NOVA_PORT_BAND = (9110, 9199)

_PORT_RE = re.compile(r"--port[= ]\s*(\d{2,5})")
_ORDINAL_RE = re.compile(r"^(?P<family>[a-z0-9]+(?:-[a-z]+)*)-(?P<ordinal>\d{2,})$")


class AllocationError(ValueError):
    """The registries do not support an allocation, so none is made."""


@dataclass(frozen=True)
class Claims:
    """Everything the fleet already claims, unioned across sources."""

    site_ids: frozenset[str]
    service_names: frozenset[str]
    ports: frozenset[int]
    domains: frozenset[str]
    #: site_id -> family, as declared. Used to find a family's existing members.
    family_of: dict[str, str] = field(default_factory=dict)
    #: site_id -> {source: service_name}. Kept per source rather than collapsed:
    #: two sources naming different units for one site is a fact about the fleet,
    #: and collapsing it would hide the very drift that has to be reported.
    service_of: dict[str, dict[str, str]] = field(default_factory=dict)
    #: site_id -> port, for finding a family's base port.
    port_of: dict[str, int] = field(default_factory=dict)
    sources: tuple[str, ...] = ()


@dataclass(frozen=True)
class Allocation:
    site_id: str
    family: str
    service_name: str
    port: int
    domain: str | None
    evidence: dict


# ---------------------------------------------------------------------------
# Reading the sources
# ---------------------------------------------------------------------------
def _load_json(path: Path) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except ValueError as exc:  # a corrupt registry must not read as "nothing claimed"
        raise AllocationError(f"registry {path} is not valid JSON: {exc}") from exc


def collect_claims(
    *,
    profiles_dir: Path,
    registry_path: Path,
    runtime_registry_path: Path,
    unit_dir: Path,
    listening_ports: Iterable[int],
) -> Claims:
    site_ids: set[str] = set()
    service_names: set[str] = set()
    ports: set[int] = set()
    domains: set[str] = set()
    family_of: dict[str, str] = {}
    service_of: dict[str, dict[str, str]] = {}
    port_of: dict[str, int] = {}

    # 1. Core identity
    for profile_path in sorted(Path(profiles_dir).glob("*.json")):
        profile = _load_json(profile_path)
        site_id = profile.get("site_id")
        if not site_id:
            continue
        site_ids.add(site_id)
        domains.update(d.lower() for d in (profile.get("domains") or []) if d)
        family = profile.get("family") or profile.get("deployment", {}).get("template_family")
        if family:
            family_of.setdefault(site_id, family)

    # 2. Ops overlay
    for entry in (_load_json(registry_path).get("sites") or []):
        site_id = entry.get("site_id")
        if not site_id:
            continue
        site_ids.add(site_id)
        if entry.get("domain"):
            domains.add(entry["domain"].lower())
        if entry.get("site_family"):
            family_of.setdefault(site_id, entry["site_family"])
        if entry.get("service_name"):
            service_names.add(entry["service_name"])
            service_of.setdefault(site_id, {})["release_registry"] = entry["service_name"]

    # 3. Dispatcher bindings
    for site_id, entry in (_load_json(runtime_registry_path).get("sites") or {}).items():
        site_ids.add(site_id)
        if entry.get("family"):
            family_of.setdefault(site_id, entry["family"])
        if entry.get("unit"):
            service_names.add(entry["unit"])
            service_of.setdefault(site_id, {})["runtime_registry"] = entry["unit"]
        if entry.get("port"):
            ports.add(int(entry["port"]))
            port_of.setdefault(site_id, int(entry["port"]))
        if entry.get("exact_domain"):
            domains.add(str(entry["exact_domain"]).lower())

    # 4. Units on disk — including ports no registry mentions
    unit_dir = Path(unit_dir)
    if unit_dir.is_dir():
        for unit_path in sorted(unit_dir.glob("*.service")):
            service_names.add(unit_path.name)
            try:
                text = unit_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for match in _PORT_RE.finditer(text):
                ports.add(int(match.group(1)))

    # 5. The kernel
    ports.update(int(p) for p in listening_ports)

    return Claims(
        site_ids=frozenset(site_ids),
        service_names=frozenset(service_names),
        ports=frozenset(ports),
        domains=frozenset(domains),
        family_of=family_of,
        service_of=service_of,
        port_of=port_of,
        sources=(
            "site_profiles",
            "release_registry",
            "runtime_registry",
            "systemd_units",
            "listening_ports",
        ),
    )


# ---------------------------------------------------------------------------
# Deriving the three values
# ---------------------------------------------------------------------------
def _family_members(claims: Claims, family: str) -> list[str]:
    return sorted(s for s, f in claims.family_of.items() if f == family)


def _next_site_id(claims: Claims, family: str, members: list[str]) -> str:
    used = set()
    for site_id in claims.site_ids:
        match = _ORDINAL_RE.match(site_id)
        if match and match.group("family") == family:
            used.add(int(match.group("ordinal")))
    ordinal = 1
    while ordinal in used:
        ordinal += 1
    return f"{family}-{ordinal:02d}"


def _service_drift(claims: Claims, members: list[str]) -> dict[str, dict[str, str]]:
    """Family members whose sources name different units for the same site."""
    drift = {}
    for member in members:
        by_source = claims.service_of.get(member) or {}
        if len(set(by_source.values())) > 1:
            drift[member] = dict(by_source)
    return drift


def _derive_from(unit: str, member: str, site_id: str) -> str | None:
    match = _ORDINAL_RE.match(member)
    if not match:
        return None
    stem = unit[: -len(".service")] if unit.endswith(".service") else unit
    ordinal = match.group("ordinal")
    if not stem.endswith(ordinal):
        return None
    return f"{stem[: -len(ordinal)]}{_ORDINAL_RE.match(site_id).group('ordinal')}.service"


def _service_name(
    claims: Claims,
    family: str,
    members: list[str],
    site_id: str,
    source: str | None,
) -> tuple[str, dict[str, dict[str, str]]]:
    """Reuse the family's own unit naming, read off an existing member.

    `lords-01` is served by `lords-nova-01.service` while `zona-01` is served by
    `nova-zona-01.service`. Forcing one of those two shapes on the other family
    would rename a service that something else restarts, so the shape is taken
    from a member of the same family and nowhere else.

    When two sources name different units for the same member, no shape is taken
    at all. The live fleet has exactly this drift, and choosing between the two
    silently is how a new site ends up bound to a legacy unit on a stale port.
    The caller has to say which source it means, and that choice is recorded.
    """
    drift = _service_drift(claims, members)
    if drift and source is None:
        lines = "; ".join(
            f"{member}: " + ", ".join(f"{src}={name}" for src, name in sorted(by_source.items()))
            for member, by_source in sorted(drift.items())
        )
        raise AllocationError(
            f"sources disagree about the unit of family {family!r} ({lines}); "
            "pass service_name_source= to say which source binds, rather than "
            "letting the allocator pick one"
        )

    for member in members:
        by_source = claims.service_of.get(member) or {}
        if not by_source:
            continue
        if source is not None:
            unit = by_source.get(source)
            if unit is None:
                continue
        else:
            unit = next(iter(by_source.values()))
        derived = _derive_from(unit, member, site_id)
        if derived:
            return derived, drift

    if source is not None:
        raise AllocationError(
            f"source {source!r} names no unit for any member of family {family!r}; "
            "an absent source is not a naming pattern"
        )
    raise AllocationError(
        f"family {family!r} has no member whose service name ends in its ordinal; "
        "the unit naming pattern cannot be read and will not be assumed"
    )


def _next_port(claims: Claims, family: str, members: list[str]) -> int:
    bases = [claims.port_of[m] for m in members if m in claims.port_of]
    if not bases:
        raise AllocationError(
            f"family {family!r} has no member with a port in the runtime registry; "
            "a base port cannot be derived and will not be invented"
        )
    base = min(bases)
    low, high = NOVA_PORT_BAND
    if base < low:
        raise AllocationError(f"family {family!r} base port {base} is below band {NOVA_PORT_BAND}")
    for candidate in range(base, high + 1):
        if candidate not in claims.ports:
            return candidate
    raise AllocationError(
        f"no free port for family {family!r} at or above {base} inside band {NOVA_PORT_BAND}"
    )


def allocate(
    family: str,
    *,
    profiles_dir: Path,
    registry_path: Path,
    runtime_registry_path: Path,
    unit_dir: Path,
    listening_ports: Iterable[int],
    domain: str | None = None,
    service_name_source: str | None = None,
) -> Allocation:
    """Allocate `site_id`, `service_name` and `port` for a new site of `family`."""
    claims = collect_claims(
        profiles_dir=profiles_dir,
        registry_path=registry_path,
        runtime_registry_path=runtime_registry_path,
        unit_dir=unit_dir,
        listening_ports=listening_ports,
    )

    members = _family_members(claims, family)
    if not members:
        raise AllocationError(
            f"family {family!r} has no existing member in any registry; a new family is a "
            "decision about naming, ports and units that is not derivable and is not guessed"
        )

    if domain is not None:
        if domain.lower() in claims.domains:
            raise AllocationError(
                f"domain {domain!r} is already bound to a site in the registries; "
                "allocating a second identifier for it would create two owners"
            )

    site_id = _next_site_id(claims, family, members)
    service_name, drift = _service_name(claims, family, members, site_id, service_name_source)
    if service_name in claims.service_names:
        raise AllocationError(
            f"derived service name {service_name!r} already exists; the ordinal and the unit "
            "naming disagree, and overwriting an installed unit is never the answer"
        )
    port = _next_port(claims, family, members)

    return Allocation(
        site_id=site_id,
        family=family,
        service_name=service_name,
        port=port,
        domain=domain,
        evidence={
            "sources": list(claims.sources),
            "family_members": members,
            "site_id_claims": {family: [m for m in members]},
            "claimed_ports": sorted(claims.ports),
            "claimed_services": sorted(claims.service_names),
            "service_name_source": service_name_source,
            "service_name_drift": drift,
            "port_band": list(NOVA_PORT_BAND),
            "family_base_port": min(claims.port_of[m] for m in members if m in claims.port_of),
        },
    )
