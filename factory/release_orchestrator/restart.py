"""Restart with postcondition polling. Stderr alone is never failure proof."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol

RESTART_ATTEMPTS_MAX = 1
RUNTIME_WAIT_TIMEOUT_SECONDS = 120
POLL_INTERVAL_SECONDS = 2
POST_RESTART_STABILIZATION_SECONDS = 5


class SystemdAdapter(Protocol):
    def show(self, unit: str) -> dict[str, str]: ...

    def restart(self, unit: str) -> dict[str, Any]: ...


@dataclass
class RestartResult:
    effective_result: str
    restart_command_warning: int = 0
    restart_postconditions_pass: int = 0
    duplicate_restart_count: int = 0
    old: dict[str, Any] = field(default_factory=dict)
    new: dict[str, Any] = field(default_factory=dict)
    detail: str = ""


class FakeSystemd:
    """Test double for restart/postcondition simulations."""

    def __init__(self) -> None:
        self.units: dict[str, dict[str, str]] = {}
        self.restart_calls: list[str] = []
        self.restart_stderr_error = False
        self.fail_postconditions = False

    def show(self, unit: str) -> dict[str, str]:
        return dict(self.units.get(unit) or {})

    def restart(self, unit: str) -> dict[str, Any]:
        self.restart_calls.append(unit)
        cur = self.units.setdefault(
            unit,
            {
                "ActiveState": "active",
                "SubState": "running",
                "MainPID": "1000",
                "ExecMainStartTimestamp": "1000",
                "NRestarts": "0",
            },
        )
        if not self.fail_postconditions:
            pid = int(cur.get("MainPID") or "1000") + 1
            start = int(cur.get("ExecMainStartTimestamp") or "1000") + 10
            n = int(cur.get("NRestarts") or "0") + 1
            cur.update(
                {
                    "ActiveState": "active",
                    "SubState": "running",
                    "MainPID": str(pid),
                    "ExecMainStartTimestamp": str(start),
                    "NRestarts": str(n),
                }
            )
        return {
            "ok": not self.restart_stderr_error,
            "stderr": "Failed to allocate directory watch: Too many open files"
            if self.restart_stderr_error
            else "",
            "stdout": "",
        }


def _snapshot(adapter: SystemdAdapter, unit: str) -> dict[str, Any]:
    props = adapter.show(unit)
    return {
        "ActiveState": props.get("ActiveState"),
        "SubState": props.get("SubState"),
        "MainPID": props.get("MainPID"),
        "ExecMainStartTimestamp": props.get("ExecMainStartTimestamp"),
        "NRestarts": props.get("NRestarts"),
    }


def postconditions_pass(old: dict[str, Any], new: dict[str, Any]) -> bool:
    if new.get("ActiveState") != "active":
        return False
    if new.get("SubState") != "running":
        return False
    if not new.get("MainPID") or new.get("MainPID") == "0":
        return False
    # New PID or newer start timestamp required.
    if new.get("MainPID") != old.get("MainPID"):
        return True
    return str(new.get("ExecMainStartTimestamp") or "") > str(old.get("ExecMainStartTimestamp") or "")


def restart_once(
    adapter: SystemdAdapter,
    unit: str,
    *,
    timeout_seconds: int = RUNTIME_WAIT_TIMEOUT_SECONDS,
    poll_interval: float = POLL_INTERVAL_SECONDS,
    stabilize_seconds: float = POST_RESTART_STABILIZATION_SECONDS,
    sleep_fn=time.sleep,
) -> RestartResult:
    """Issue exactly one restart; judge by postconditions, not stderr."""
    old = _snapshot(adapter, unit)
    cmd = adapter.restart(unit)
    warning = 0 if cmd.get("ok", True) else 1
    sleep_fn(stabilize_seconds)
    deadline = time.monotonic() + timeout_seconds
    new = _snapshot(adapter, unit)
    while time.monotonic() < deadline:
        new = _snapshot(adapter, unit)
        if postconditions_pass(old, new):
            break
        sleep_fn(poll_interval)
    passed = postconditions_pass(old, new)
    return RestartResult(
        effective_result="PASS" if passed else "FAIL",
        restart_command_warning=warning,
        restart_postconditions_pass=1 if passed else 0,
        duplicate_restart_count=0,
        old=old,
        new=new,
        detail=str(cmd.get("stderr") or ""),
    )
