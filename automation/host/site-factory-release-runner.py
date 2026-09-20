#!/usr/bin/env python3
"""Root-owned release runner entry (installed by one-time owner bootstrap).

Accepts ONLY:
  --release-id
  --manifest
  --manifest-digest
  --approval

Service names, artifact paths, and handlers are loaded from the Core registry.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure repo import path when installed as /usr/local/libexec/...
REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from factory.release_orchestrator.privilege import PrivilegeError, load_trusted_context, parse_runner_argv
from factory.release_orchestrator.runner import run_batch
from factory.release_orchestrator.reports import write_final_reports
from factory.paths import PATHS


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        request = parse_runner_argv(argv)
        ctx = load_trusted_context(request)
    except (PrivilegeError, Exception) as exc:  # noqa: BLE001
        print(json.dumps({"status": "FAIL_PRIVILEGE_BOUNDARY", "error": str(exc)}), file=sys.stderr)
        return 2

    report_dir = PATHS.root / "reports" / "releases" / request.release_id
    work_root = PATHS.var / "release-orchestrator" / request.release_id
    # Live mutate only when running as root runner; still requires approval.
    result = run_batch(
        release_id=request.release_id,
        manifest_path=request.manifest_path,
        manifest_digest=request.manifest_digest,
        approval_path=request.approval_path,
        report_dir=report_dir,
        work_root=work_root,
        mutate=True,
        shadow=False,
    )
    write_final_reports(report_dir, verdict=result.verdict, extra={"plan_sites": len(ctx["plan"])})
    print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
    return 0 if result.global_state == "BATCH_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
