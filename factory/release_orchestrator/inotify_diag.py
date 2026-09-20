"""Read-only diagnostics for 'Too many open files' / inotify exhaustion.

Does not raise sysctl blindly. Orchestrator treats restart stderr as warning only.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class InotifyReport:
    max_user_instances: int | None = None
    max_user_watches: int | None = None
    max_queued_events: int | None = None
    observed_instances: int | None = None
    top_processes: list[dict[str, Any]] = field(default_factory=list)
    fd_soft_limit: int | None = None
    fd_hard_limit: int | None = None
    likely_cause: str = "unmeasured"
    remediation_applied: bool = False
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "max_user_instances": self.max_user_instances,
            "max_user_watches": self.max_user_watches,
            "max_queued_events": self.max_queued_events,
            "observed_instances": self.observed_instances,
            "top_processes": self.top_processes,
            "fd_soft_limit": self.fd_soft_limit,
            "fd_hard_limit": self.fd_hard_limit,
            "likely_cause": self.likely_cause,
            "remediation_applied": self.remediation_applied,
            "notes": self.notes,
        }


def _read_sysctl(name: str) -> int | None:
    path = Path("/proc/sys") / name.replace(".", "/")
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _count_inotify_instances() -> tuple[int | None, list[dict[str, Any]]]:
    proc = Path("/proc")
    if not proc.exists():
        return None, []
    counts: dict[int, int] = {}
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        fd_dir = entry / "fd"
        if not fd_dir.exists():
            continue
        n = 0
        try:
            for fd in fd_dir.iterdir():
                try:
                    target = os.readlink(fd)
                except OSError:
                    continue
                if "anon_inode:inotify" in target:
                    n += 1
        except OSError:
            continue
        if n:
            counts[int(entry.name)] = n
    total = sum(counts.values())
    top = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:10]
    rows = []
    for pid, n in top:
        comm = ""
        try:
            comm = (proc / str(pid) / "comm").read_text(encoding="utf-8").strip()
        except OSError:
            pass
        rows.append({"pid": pid, "inotify_instances": n, "comm": comm})
    return total, rows


def diagnose(apply_remediation: bool = False) -> InotifyReport:
    report = InotifyReport(
        max_user_instances=_read_sysctl("fs.inotify.max_user_instances"),
        max_user_watches=_read_sysctl("fs.inotify.max_user_watches"),
        max_queued_events=_read_sysctl("fs.inotify.max_queued_events"),
    )
    try:
        import resource

        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        report.fd_soft_limit = soft
        report.fd_hard_limit = hard
    except Exception:  # noqa: BLE001
        report.notes.append("RLIMIT_NOFILE unreadable")

    total, top = _count_inotify_instances()
    report.observed_instances = total
    report.top_processes = top

    if report.max_user_instances and total is not None:
        if total >= report.max_user_instances:
            report.likely_cause = "inotify_max_user_instances_exhausted"
            report.notes.append(
                "Observed inotify instances at or above fs.inotify.max_user_instances. "
                "Prefer closing leaking watchers (IDE/agent) before raising sysctl."
            )
        elif report.max_user_instances <= 128 and total > report.max_user_instances * 0.8:
            report.likely_cause = "inotify_instances_near_ceiling"
        else:
            report.likely_cause = "inotify_headroom_ok"

    # Cursor/agent leak heuristic
    for row in top:
        if "cursor" in row.get("comm", "").lower() or "node" in row.get("comm", "").lower():
            report.notes.append(
                f"process pid={row['pid']} comm={row['comm']} holds {row['inotify_instances']} inotify instances"
            )

    if apply_remediation:
        report.notes.append(
            "apply_remediation requested but refused in-library: owner must set persistent sysctl "
            "with old/new justification; orchestrator never raises limits silently."
        )
        report.remediation_applied = False

    return report
