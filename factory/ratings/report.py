"""Отчёты прогона: JSON + Markdown. Секреты не пишутся."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from factory.ratings.ingestion import RunMetrics


def estimate_backlog_completion(
    *,
    backlog: int,
    matched_per_day: float,
    success_target: int = 500,
) -> str | None:
    """ETA из реального backlog и фактической скорости успешного сопоставления."""
    speed = matched_per_day if matched_per_day > 0 else 0.0
    if speed <= 0:
        return None
    # Daily success is capped by success_target
    daily = min(speed, float(success_target))
    if daily <= 0:
        return None
    days = backlog / daily
    eta = datetime.now(timezone.utc) + timedelta(days=days)
    return eta.strftime("%Y-%m-%d")


def write_run_report(
    metrics: RunMetrics | dict[str, Any],
    evidence_dir: Path,
    *,
    extra: dict[str, Any] | None = None,
) -> dict[str, str]:
    evidence_dir = Path(evidence_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    data = metrics.as_dict() if isinstance(metrics, RunMetrics) else dict(metrics)
    if extra:
        data.update(extra)
    # Redaction guard
    for banned in ("authorization", "token", "password", "secret", "cookie"):
        for key in list(data.keys()):
            if banned in key.lower():
                data[key] = "***REDACTED***"

    run_id = data.get("run_id") or "unknown"
    json_path = evidence_dir / f"run-{run_id}.json"
    md_path = evidence_dir / f"run-{run_id}.md"
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_markdown(data), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def _markdown(data: dict[str, Any]) -> str:
    lines = [
        f"# Ratings run `{data.get('run_id')}`",
        "",
        f"- source: `{data.get('source')}`",
        f"- dry_run: `{data.get('dry_run')}`",
        f"- started: {data.get('started_at')}",
        f"- finished: {data.get('finished_at')}",
        f"- duration_sec: {data.get('duration_sec')}",
        "",
        "## Counters",
        "",
        f"| metric | value |",
        f"| --- | --- |",
    ]
    for key in (
        "queue_size",
        "planned_candidates",
        "attempted",
        "fetched",
        "matched",
        "inserted",
        "unchanged",
        "refreshed",
        "not_found",
        "conflicts",
        "review_queued",
        "retried",
        "rate_limited",
        "failed",
        "dead_letter",
        "request_count",
        "last_good_preserved",
    ):
        lines.append(f"| {key} | {data.get(key)} |")
    if data.get("estimated_backlog_completion"):
        lines.extend(["", f"ETA backlog: **{data['estimated_backlog_completion']}**"])
    if data.get("candidate_snapshot_digest"):
        lines.extend(["", f"Candidate snapshot digest: `{data['candidate_snapshot_digest']}`"])
    lines.append("")
    return "\n".join(lines)


ALERT_RULES = [
    {
        "id": "job_missed_26h",
        "when": "last_successful_run_age_hours > 26",
        "severity": "critical",
    },
    {
        "id": "queue_nonzero_inserted_zero",
        "when": "queue_size > 0 and inserted == 0 and attempted > 0",
        "severity": "warning",
    },
    {
        "id": "error_rate_above_5pct",
        "when": "failed / max(attempted,1) > 0.05",
        "severity": "warning",
    },
    {"id": "schema_drift", "when": "circuit_reason == SCHEMA_DRIFT", "severity": "critical"},
    {"id": "auth_rejected", "when": "circuit_reason in (401,403,AUTH_REJECTED)", "severity": "critical"},
    {"id": "rate_limit_storm", "when": "rate_limited > 10 in one run", "severity": "warning"},
    {"id": "coverage_decrease", "when": "coverage_delta < 0", "severity": "warning"},
    {"id": "stale_snapshot", "when": "snapshot_age_hours > 36", "severity": "warning"},
    {"id": "snapshot_manifest_mismatch", "when": "digest mismatch", "severity": "critical"},
    {"id": "mass_score_anomaly", "when": "score_delta_abs > 2.0 for > 5% titles", "severity": "warning"},
]
