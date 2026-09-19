"""RatingsRunReport v1 — read-only Qwen-facing daily/run report."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPORT_VERSION = "ratings_run_report_v1"
QWEN_PERMISSIONS = {
    "may_read_report": True,
    "may_analyze": True,
    "may_propose_changeset": True,
    "may_write_db": False,
    "may_start_ingestion": False,
    "may_change_limits": False,
    "may_enable_scheduler": False,
    "may_publish_snapshot": False,
    "may_deploy": False,
    "may_delete_data": False,
    "may_open_indexing": False,
}


def sanitize_report(data: dict[str, Any]) -> dict[str, Any]:
    banned = ("authorization", "token", "password", "secret", "cookie", "raw_html", "email", "ip_address")
    out = {}
    for k, v in data.items():
        lk = k.lower()
        if any(b in lk for b in banned):
            out[k] = "***REDACTED***"
        elif isinstance(v, dict):
            out[k] = sanitize_report(v)
        else:
            out[k] = v
    # never embed HTML
    out.pop("raw_html", None)
    return out


def write_qwen_report(run_report: dict[str, Any], evidence_dir: Path) -> dict[str, str]:
    evidence_dir = Path(evidence_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    clean = sanitize_report(dict(run_report))
    clean["report_version"] = REPORT_VERSION
    clean["qwen_permissions"] = QWEN_PERMISSIONS
    clean["QWEN_WRITE_PERMISSIONS"] = 0
    delivery = {
        "REPORT_READY_FOR_QWEN": True,
        "QWEN_DELIVERY": "BLOCKED_NO_CONFIG",
        "reason": "No configured read-only Qwen delivery channel in this environment",
        "integration_contract": {
            "input": "QWEN_REPORT.json + QWEN_REPORT.md",
            "mode": "read_only",
            "forbidden": [k for k, v in QWEN_PERMISSIONS.items() if v is False],
        },
    }
    clean["delivery"] = delivery

    json_path = evidence_dir / "QWEN_REPORT.json"
    md_path = evidence_dir / "QWEN_REPORT.md"
    json_path.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_md(clean), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path), "delivery": delivery["QWEN_DELIVERY"]}


def _md(data: dict[str, Any]) -> str:
    lines = [
        f"# RatingsRunReport `{data.get('run_id')}`",
        "",
        f"- report_version: `{data.get('report_version')}`",
        f"- started: {data.get('run_started_at')}",
        f"- finished: {data.get('run_finished_at')}",
        f"- attempted/accepted/rejected: {data.get('attempted')}/{data.get('accepted')}/{data.get('rejected')}",
        f"- newly_covered: {data.get('newly_covered')}",
        f"- shortfall: {data.get('shortfall')}",
        f"- snapshot_digest_after: `{data.get('snapshot_digest_after')}`",
        f"- QWEN_DELIVERY: `{data.get('delivery', {}).get('QWEN_DELIVERY')}`",
        "",
        "## Qwen permissions (proposal-only)",
        "",
    ]
    for k, v in (data.get("qwen_permissions") or {}).items():
        lines.append(f"- `{k}`: `{v}`")
    lines += ["", "## Coverage", ""]
    lines.append(f"- eligible_total: {data.get('eligible_total')}")
    lines.append(f"- covered_total: {data.get('covered_total')}")
    lines.append(f"- eligible_uncovered_before/after: {data.get('eligible_uncovered_before')}/{data.get('eligible_uncovered_after')}")
    lines.append("")
    lines.append("No secrets, raw HTML, cookies, or PII are included.")
    return "\n".join(lines) + "\n"
