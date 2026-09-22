#!/usr/bin/env python3
"""Run the registry allocator against the live fleet and print the result.

Read-only. It writes nothing and changes nothing: it reads the four registries
plus the kernel's listening sockets and prints the allocation with the evidence
that produced it, so the numbers in the report can be re-derived rather than
trusted.

    python3 automation/host/zonafilm-cc-allocate.py --family zona --domain zonafilm.cc
"""

from __future__ import annotations

import argparse
import json
import socket
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from factory.release_orchestrator.allocator import AllocationError, allocate  # noqa: E402

LIVE_RUNTIME_REGISTRY = Path("/srv/lords/.frontend/lords-runtime-registry.json")
LIVE_UNIT_DIR = Path("/etc/systemd/system")


def listening_ports() -> set[int]:
    """Ports in LISTEN state, read from the kernel rather than from a tool.

    `ss` and `netstat` are not in this environment's command profile, and a
    missing tool must not silently become "no ports are in use" — that is the
    one failure mode that turns an allocation into a collision.
    """
    ports: set[int] = set()
    seen_any = False
    for path in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            lines = Path(path).read_text(encoding="utf-8").splitlines()[1:]
        except OSError:
            continue
        seen_any = True
        for line in lines:
            fields = line.split()
            if len(fields) < 4 or fields[3] != "0A":  # 0A = TCP_LISTEN
                continue
            ports.add(int(fields[1].split(":")[1], 16))
    if not seen_any:
        raise SystemExit("/proc/net/tcp is unreadable: the set of busy ports is unknown, "
                         "and allocating against an unknown set is not allocation")
    return ports


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family", required=True)
    parser.add_argument("--domain", default=None)
    parser.add_argument("--repo", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--profiles-dir", default=None,
                        help="default: <repo>/config/site-profiles")
    parser.add_argument("--registry", default=None,
                        help="default: <repo>/config/release-registry.json")
    parser.add_argument("--runtime-registry", default=str(LIVE_RUNTIME_REGISTRY))
    parser.add_argument("--unit-dir", default=str(LIVE_UNIT_DIR))
    parser.add_argument("--service-name-source", default=None,
                        help="which source binds the unit name when sources drift "
                             "(release_registry | runtime_registry)")
    args = parser.parse_args()

    repo = Path(args.repo)
    try:
        allocation = allocate(
            args.family,
            profiles_dir=Path(args.profiles_dir or repo / "config" / "site-profiles"),
            registry_path=Path(args.registry or repo / "config" / "release-registry.json"),
            runtime_registry_path=Path(args.runtime_registry),
            unit_dir=Path(args.unit_dir),
            listening_ports=listening_ports(),
            domain=args.domain,
            service_name_source=args.service_name_source,
        )
    except AllocationError as exc:
        print(json.dumps({"status": "REFUSED", "reason": str(exc)}, ensure_ascii=False, indent=2))
        return 2

    print(json.dumps(
        {
            "status": "ALLOCATED",
            "site_id": allocation.site_id,
            "family": allocation.family,
            "service_name": allocation.service_name,
            "port": allocation.port,
            "domain": allocation.domain,
            "evidence": allocation.evidence,
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
