"""Owner dashboard: Markdown + machine-readable JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from factory.release_orchestrator.state import BatchCheckpoint


def dashboard_rows(checkpoint: BatchCheckpoint, extras: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    extras = extras or {}
    rows = []
    for sid, site in checkpoint.sites.items():
        info = extras.get(sid) or {}
        rows.append(
            {
                "site": sid,
                "stage": site.stage,
                "build": info.get("build", ""),
                "artifact": info.get("artifact", ""),
                "profile": info.get("profile", ""),
                "design": info.get("design", ""),
                "indexability": info.get("indexability", ""),
                "smoke_1": info.get("smoke_1", ""),
                "smoke_2": info.get("smoke_2", ""),
                "result": site.stage,
            }
        )
    return rows


def render_markdown(checkpoint: BatchCheckpoint, extras: dict[str, dict[str, Any]] | None = None) -> str:
    rows = dashboard_rows(checkpoint, extras)
    lines = [
        f"# Release {checkpoint.release_id}",
        "",
        f"- global: `{checkpoint.global_state}`",
        f"- active_site: `{checkpoint.active_site_id}`",
        f"- updated_at: `{checkpoint.updated_at}`",
        "",
        "| Site | Stage | Build | Artifact | Profile | Design | Indexability | Smoke 1 | Smoke 2 | Result |",
        "| ---- | ----- | ----- | -------- | ------- | ------ | ------------ | ------- | ------- | ------ |",
    ]
    for r in rows:
        lines.append(
            f"| {r['site']} | {r['stage']} | {r['build']} | {r['artifact']} | {r['profile']} | "
            f"{r['design']} | {r['indexability']} | {r['smoke_1']} | {r['smoke_2']} | {r['result']} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_dashboard(report_dir: Path, checkpoint: BatchCheckpoint, extras: dict[str, dict[str, Any]] | None = None) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "release_id": checkpoint.release_id,
        "global_state": checkpoint.global_state,
        "active_site_id": checkpoint.active_site_id,
        "updated_at": checkpoint.updated_at,
        "rows": dashboard_rows(checkpoint, extras),
    }
    (report_dir / "dashboard.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (report_dir / "dashboard.md").write_text(render_markdown(checkpoint, extras), encoding="utf-8")
