"""Coverage-aware daily SLA and ratings_daily_v1 report builder."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from factory.ratings.formula import FORMULA_VERSION
from factory.ratings.rotation import ROTATION_ALGORITHM_VERSION

DAILY_SCHEMA = "ratings_daily_v1"
DAILY_NEW_COVERAGE_TARGET = 500
DAILY_UNIQUE_CANDIDATE_CAP = 750
TZ_NAME = "Europe/Moscow"

PRIMARY_REASONS = {
    "NO_PROVIDER_CANDIDATE",
    "PROVIDER_TITLE_NOT_FOUND",
    "PROVIDER_RATING_NULL",
    "PROVIDER_VOTE_COUNT_ZERO",
    "AMBIGUOUS_MAPPING",
    "LOW_CONFIDENCE_MAPPING",
    "IDENTITY_CONFLICT",
    "LOCAL_METADATA_INSUFFICIENT",
    "SOURCE_NOT_APPROVED",
    "SOURCE_POLICY_BLOCK",
    "SOURCE_TIMEOUT",
    "SOURCE_RATE_LIMITED",
    "SOURCE_HTTP_ERROR",
    "SOURCE_GRAPHQL_ERROR",
    "SOURCE_SCHEMA_DRIFT",
    "VALIDATION_FAILED",
    "DB_WRITE_FAILED",
    "SNAPSHOT_BUILD_FAILED",
    "GATEWAY_PUBLISH_FAILED",
    "CAP_EXHAUSTED",
    "DEFERRED_AFTER_CUTOFF",
    "ALREADY_COVERED_PLANNER_DEFECT",
}


@dataclass
class CoverageSnapshot:
    source_applicable_total_start: int
    covered_valid_start: int
    covered_fresh_start: int = 0
    covered_stale_start: int = 0
    uncovered_actionable_start: int = 0
    unmapped_start: int = 0
    ambiguous_start: int = 0
    confirmed_absent_start: int = 0
    policy_excluded_start: int = 0
    catalog_digest: str = ""

    def as_dict(self) -> dict[str, Any]:
        gross = (
            self.covered_valid_start / self.source_applicable_total_start
            if self.source_applicable_total_start
            else None
        )
        eligible_den = (
            self.source_applicable_total_start
            - self.confirmed_absent_start
            - self.policy_excluded_start
        )
        eligible = (
            self.covered_valid_start / eligible_den if eligible_den > 0 else None
        )
        effective = min(DAILY_NEW_COVERAGE_TARGET, self.uncovered_actionable_start)
        full = (
            self.source_applicable_total_start > 0
            and self.covered_valid_start == self.source_applicable_total_start
        )
        actionable_saturated = (
            self.uncovered_actionable_start == 0 and not full
        )
        return {
            "source_applicable_total_start": self.source_applicable_total_start,
            "covered_valid_start": self.covered_valid_start,
            "covered_fresh_start": self.covered_fresh_start,
            "covered_stale_start": self.covered_stale_start,
            "uncovered_actionable_start": self.uncovered_actionable_start,
            "unmapped_start": self.unmapped_start,
            "ambiguous_start": self.ambiguous_start,
            "confirmed_absent_start": self.confirmed_absent_start,
            "policy_excluded_start": self.policy_excluded_start,
            "gross_coverage_pct": None if gross is None else float(Decimal(str(gross * 100)).quantize(Decimal("0.01"))),
            "eligible_coverage_pct": None if eligible is None else float(Decimal(str(eligible * 100)).quantize(Decimal("0.01"))),
            "effective_daily_target": 0 if full else effective,
            "full_coverage_mode": full,
            "actionable_saturated": actionable_saturated and not full,
            "catalog_digest": self.catalog_digest,
        }


def effective_daily_target(uncovered_actionable: int, *, full_coverage: bool = False) -> int:
    if full_coverage:
        return 0
    return min(DAILY_NEW_COVERAGE_TARGET, max(0, uncovered_actionable))


def verify_reason_arithmetic(*, attempted_unique: int, newly_covered: int, reason_counts: dict[str, int]) -> bool:
    not_added = attempted_unique - newly_covered
    return sum(reason_counts.values()) == not_added and not_added >= 0


def compute_status(
    *,
    attainment_pct: float | None,
    full_coverage: bool,
    quality_pass: bool,
    arithmetic_ok: bool,
) -> str:
    if not quality_pass or not arithmetic_ok:
        return "RED"
    if full_coverage:
        return "GREEN"
    if attainment_pct is None:
        return "RED"
    if attainment_pct >= 100.0 and quality_pass:
        return "GREEN"
    if attainment_pct >= 90.0:
        return "YELLOW"
    return "RED"


def estimate_eta(
    *,
    uncovered_actionable_end: int,
    full_coverage: bool,
    blocked: bool,
    rolling_7d_median: float | None,
) -> dict[str, Any]:
    if full_coverage:
        return {"eta": "FULL_COVERAGE", "nominal_eta_days": 0, "rolling_eta_days": None}
    if blocked:
        return {"eta": "BLOCKED", "nominal_eta_days": None, "rolling_eta_days": None}
    import math

    nominal = math.ceil(uncovered_actionable_end / DAILY_NEW_COVERAGE_TARGET) if uncovered_actionable_end else 0
    if rolling_7d_median is None or rolling_7d_median <= 0:
        return {
            "eta": None,
            "nominal_eta_days": nominal,
            "rolling_eta_days": None,
            "ROLLING_ETA": "INSUFFICIENT_HISTORY",
        }
    rolling = math.ceil(uncovered_actionable_end / rolling_7d_median)
    eta_date = (datetime.now(timezone.utc) + timedelta(days=rolling)).strftime("%Y-%m-%d")
    return {"eta": eta_date, "nominal_eta_days": nominal, "rolling_eta_days": rolling}


def build_qwen_message(report: dict[str, Any]) -> str:
    cat = report.get("catalog") or {}
    sla = report.get("sla") or {}
    amd = report.get("amd_online") or {}
    uv = report.get("user_votes") or {}
    return (
        f"Ratings {report.get('report_date')}: "
        f"STATUS={report.get('status')}; "
        f"MODE={report.get('mode')}; "
        f"coverage={cat.get('covered_valid')}/{cat.get('source_applicable')} ({cat.get('gross_coverage_pct')}%); "
        f"eligible_coverage={cat.get('eligible_coverage_pct')}%; "
        f"target={sla.get('effective_target')}; "
        f"added={sla.get('newly_covered')}; "
        f"not_added={(report.get('outcomes') or {}).get('not_added')}; "
        f"new_overdue_24h={(report.get('new_titles') or {}).get('overdue_24h')}; "
        f"refresh_changed={(report.get('refresh') or {}).get('refresh_changed')}; "
        f"Shikimori={(report.get('sources') or {}).get('shikimori', {}).get('added', 0)}; "
        f"AMD={amd.get('accepted', 0)}; "
        f"AMD_permission={amd.get('permission_status')}; "
        f"user_votes={uv.get('accepted', 0)}; "
        f"ranking_changed={uv.get('ranking_positions_changed', 0)}; "
        f"backlog={cat.get('uncovered_actionable')}; "
        f"ETA={report.get('eta')}; "
        f"report={report.get('report_path')}."
    )


def write_daily_report(
    report: dict[str, Any],
    root: Path,
    *,
    outcomes: list[dict[str, Any]] | None = None,
    not_added: list[dict[str, Any]] | None = None,
    quality_sample: list[dict[str, Any]] | None = None,
) -> dict[str, str]:
    date = report["report_date"]
    day_dir = Path(root) / "reports" / "ratings" / "daily" / date
    day_dir.mkdir(parents=True, exist_ok=True)
    report = dict(report)
    report["schema_version"] = DAILY_SCHEMA
    report.setdefault("formula_version", FORMULA_VERSION)
    report.setdefault("rotation_algorithm_version", ROTATION_ALGORITHM_VERSION)
    report["report_path"] = str(day_dir / "report.json")

    msg = build_qwen_message(report)
    report["qwen_message"] = msg

    json_path = day_dir / "report.json"
    tmp = json_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(json_path)

    md = [
        f"# Ratings daily {date}",
        "",
        f"STATUS: **{report.get('status')}**  MODE: `{report.get('mode')}`",
        "",
        "```",
        msg,
        "```",
        "",
        f"schema: `{DAILY_SCHEMA}`",
    ]
    (day_dir / "REPORT.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (day_dir / "QWEN_MESSAGE.txt").write_text(msg + "\n", encoding="utf-8")

    def _csv(path: Path, rows: list[dict[str, Any]]):
        if not rows:
            path.write_text("", encoding="utf-8")
            return
        with path.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    _csv(day_dir / "outcomes.csv", outcomes or [])
    _csv(day_dir / "not-added.csv", not_added or [])
    _csv(day_dir / "quality-sample.csv", quality_sample or [])

    latest = Path(root) / "reports" / "ratings" / "daily" / "latest.json"
    latest_tmp = latest.with_suffix(".json.tmp")
    latest_tmp.write_text(json.dumps({"report_date": date, "path": str(json_path), "status": report.get("status")}, indent=2), encoding="utf-8")
    latest_tmp.replace(latest)

    return {
        "report_json": str(json_path),
        "report_md": str(day_dir / "REPORT.md"),
        "qwen_message": str(day_dir / "QWEN_MESSAGE.txt"),
        "latest": str(latest),
    }


@dataclass
class QwenDelivery:
    """Delivery interface. Stage 2: fake/dry-run only; never invent endpoint."""

    configured: bool = False
    destination: str = ""

    def deliver(self, message: str, *, dry_run: bool = True) -> dict[str, Any]:
        if not self.configured:
            return {
                "REPORT_READY_FOR_QWEN": True,
                "QWEN_DELIVERY": "NOT_CONFIGURED",
                "DELIVERED": False,
                "dry_run": dry_run,
                "message_len": len(message),
            }
        if dry_run:
            return {
                "REPORT_READY_FOR_QWEN": True,
                "QWEN_DELIVERY": "DRY_RUN",
                "DELIVERED": False,
                "destination": self.destination,
            }
        # Real send would go here in Stage 3 after explicit config+probe.
        return {
            "REPORT_READY_FOR_QWEN": True,
            "QWEN_DELIVERY": "ATTEMPTED",
            "DELIVERED": False,
            "reason": "Stage 2 forbids live external delivery",
        }
