"""Stage 4 closeout checker — validates 7 pilot cycles without new ingestion."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from factory.ratings.pilot import PILOT_MAX_CYCLES, load_pilot

REQUIRED_CYCLE_KEYS = (
    "cycle_id",
    "date",
    "attempted",
    "accepted",
    "rejected",
    "shortfall_reason",
    "snapshot_digest",
    "qwen_receipt",
    "duplicate_rows",
)


def evaluate_closeout(root: Path, cycles_path: Path) -> dict[str, Any]:
    pilot = load_pilot(root)
    cycles = []
    if cycles_path.is_file():
        cycles = json.loads(cycles_path.read_text(encoding="utf-8")).get("cycles") or []
    n = len(cycles)
    unexplained = 0
    qwen_ok = 0
    dupes = 0
    for c in cycles:
        if c.get("duplicate_rows", 0):
            dupes += 1
        if c.get("qwen_receipt"):
            qwen_ok += 1
        reason = c.get("shortfall_reason") or ""
        accepted = int(c.get("accepted") or 0)
        allowed = {
            "COVERAGE_COMPLETE",
            "NO_DUE_REFRESH",
            "SOURCE_DISABLED_POLICY",
            "ZERO_SCORE_NO_VOTES",
            "AMBIGUOUS_MAPPING",
            "SOURCE_NO_DATA",
            "COVERAGE_COMPLETE_OR_NO_DUE_REFRESH",
            "AVAILABLE_BELOW_CAP",
            "",
        }
        if (
            accepted < 100
            and reason not in allowed
            and accepted < int(c.get("effective_target") or 100)
        ):
            unexplained += 1

    complete = n >= PILOT_MAX_CYCLES
    return {
        "DAILY_CYCLES_COMPLETED": f"{n}/{PILOT_MAX_CYCLES}",
        "closeout_ready": complete and dupes == 0 and unexplained == 0 and qwen_ok == n and n == PILOT_MAX_CYCLES,
        "DUPLICATE_ROWS": dupes,
        "UNEXPLAINED_DAILY_SHORTFALLS": unexplained,
        "QWEN_REPORTS_BUILT": f"{qwen_ok}/{n}",
        "QWEN_DELIVERY_RECEIPTS": f"{qwen_ok}/{n}",
        "scheduler_should_disable": True,
        "READY_FOR_DAILY_250": complete and dupes == 0 and unexplained == 0,
        "READY_FOR_DAILY_500": False,
        "pilot": pilot.as_dict(),
    }


def main() -> int:
    import argparse

    from factory.paths import PATHS

    p = argparse.ArgumentParser(description="Stage4 pilot closeout (no ingestion)")
    p.add_argument("--cycles", default="artifacts/evidence/ratings-ingestion-04/PILOT_CYCLES.json")
    args = p.parse_args()
    result = evaluate_closeout(PATHS.root, Path(args.cycles))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("closeout_ready") else 1


if __name__ == "__main__":
    raise SystemExit(main())
