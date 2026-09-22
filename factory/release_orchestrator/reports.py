"""Final release reports under reports/releases/<release_id>/."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from factory.release_orchestrator.dashboard import write_dashboard
from factory.release_orchestrator.state import load_checkpoint


def write_final_reports(report_dir: Path, *, verdict: str, extra: dict[str, Any] | None = None) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = load_checkpoint(report_dir / "checkpoint.json")
    write_dashboard(report_dir, checkpoint)
    payload = {
        "verdict": verdict,
        "release_id": checkpoint.release_id,
        "global_state": checkpoint.global_state,
        "sites": {sid: sc.stage for sid, sc in checkpoint.sites.items()},
        "extra": extra or {},
    }
    (report_dir / "FINAL_REPORT.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    md = [
        f"# FINAL REPORT — {checkpoint.release_id}",
        "",
        f"VERDICT=`{verdict}`",
        f"GLOBAL=`{checkpoint.global_state}`",
        "",
        "## Sites",
    ]
    for sid, sc in checkpoint.sites.items():
        md.append(f"- `{sid}`: `{sc.stage}`")
    md.append("")
    (report_dir / "FINAL_REPORT.md").write_text("\n".join(md), encoding="utf-8")
    (report_dir / "FINAL_VERDICT.txt").write_text(verdict + "\n", encoding="utf-8")
