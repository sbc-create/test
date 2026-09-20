"""Gate for legacy host scripts that bypass the Release Orchestrator.

When RELEASE_ORCHESTRATOR_REQUIRED=1, direct deploy/restart scripts must exit.
Administrative root remains documented; it is not supported unattended automation.
"""

from __future__ import annotations

import os
import sys


ENFORCE_ENV = "RELEASE_ORCHESTRATOR_REQUIRED"


def refuse_if_enforced(script_name: str) -> None:
    if os.environ.get(ENFORCE_ENV, "0") not in {"1", "true", "TRUE", "yes"}:
        return
    print(
        f"[RELEASE_ORCHESTRATOR_REQUIRED] {script_name} is no longer a supported "
        "automation path. Use: bin/site-factory-release run --release-id … "
        "(root runner after one-time bootstrap).",
        file=sys.stderr,
    )
    raise SystemExit(78)


def notice_deprecated(script_name: str) -> None:
    if os.environ.get("RELEASE_ORCHESTRATOR_SILENCE_DEPRECATION") == "1":
        return
    print(
        f"[deprecated] {script_name}: prefer site-factory-release orchestrator. "
        f"Set {ENFORCE_ENV}=1 to refuse this bypass path.",
        file=sys.stderr,
    )
