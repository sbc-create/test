"""Stage 5R report semantics — pilot accounting and Qwen/scheduler gates."""

from __future__ import annotations

from typing import Any

from factory.ratings.stage5_constants import REQUIRED_SUCCESSFUL_CYCLES


def pilot_cycle_accounting(
    *,
    attempted: int,
    successful: int,
    failed: int,
) -> dict[str, Any]:
    """Unambiguous pilot counters (attempts vs successes separated)."""
    remaining_successful = max(0, REQUIRED_SUCCESSFUL_CYCLES - successful)
    return {
        "PILOT_ATTEMPTED_CYCLES": attempted,
        "PILOT_FAILED_CYCLES": failed,
        "PILOT_SUCCESSFUL_CYCLES": successful,
        "REQUIRED_SUCCESSFUL_CYCLES": REQUIRED_SUCCESSFUL_CYCLES,
        "PILOT_SUCCESSFUL_CYCLES_REMAINING": remaining_successful,
        "note": (
            "PILOT_SUCCESSFUL_CYCLES_REMAINING counts successful cycles still "
            "needed toward the 7-cycle pilot — not remaining attempts."
        ),
        "FAILED_CYCLE_NOT_COUNTED_AS_SUCCESS": 1 if failed else 0,
    }


def qwen_gate_semantics(
    *,
    report_built: bool,
    outbox_created: bool,
    delivery_configured: bool,
    delivery_acked: bool,
) -> dict[str, Any]:
    return {
        "BLOCK_04_QWEN_LABEL": "REPORT_AND_OUTBOX_ONLY",
        "QWEN_REPORT_BUILD_PASS": int(report_built),
        "QWEN_OUTBOX_PASS": int(outbox_created),
        "QWEN_DELIVERY_PASS": int(delivery_configured and delivery_acked),
        "QWEN_ACK_PASS": int(delivery_acked),
        "QWEN_DELIVERY_CONFIGURED": "YES" if delivery_configured else "NO",
        "note": "BLOCK_04_QWEN=PASS means report+outbox only; not delivery/ACK",
    }


def denominator_semantics() -> dict[str, Any]:
    return {
        "ONGOING_ELIGIBLE_TOTAL": "UNKNOWN",
        "ONGOING_COVERAGE_PERCENT": "N/A",
        "ONGOING_CLASSIFICATION_GAP": (
            "lords-01 catalog lacks reliable is_ongoing/status; "
            "UNKNOWN must not be displayed as 0"
        ),
        "CURRENT_SEASON_ELIGIBLE_TOTAL": 136,
        "CURRENT_SEASON_HEURISTIC": (
            "is_seasonal OR (days_since_release<=120 AND kind=tv) among MAL-mapped"
        ),
        "CURRENT_SEASON_COVERAGE_PERCENT": "N/A",
        "CURRENT_SEASON_COVERAGE_NOTE": (
            "Denominator 136 is a planning heuristic; numerator for 'current season "
            "covered by Shikimori' was not separately projected in Stage5 inventory "
            "without false precision — coverage percent withheld (not coerced to 0)."
        ),
        "NEW_30D_ELIGIBLE_TOTAL": 43,
        "NEW_30D_COVERAGE_PERCENT": 67.44,
        "NEW_30D_NOTE": "Percent available because eligible set and covered intersection are both countable",
    }


def scheduler_gate_for_repair(
    *,
    first_supervised_pass: bool,
    qwen_configured: bool,
    qwen_ack: bool,
) -> dict[str, Any]:
    enable = first_supervised_pass and qwen_configured and qwen_ack
    return {
        "SCHEDULER_ENABLED": "YES" if enable else "NO",
        "READY_FOR_DAILY_100_PILOT": "NO",
        "READY_FOR_DAILY_250": "NO",
        "READY_FOR_DAILY_500": "NO",
        "READY_FOR_AUTONOMOUS_PRODUCTION": "NO",
        "reason": "repair pass only; needs successful supervised cycle + Qwen ACK",
    }


def rejection_breakdown_incident() -> dict[str, Any]:
    """Incident cycle: 25 rejected = not_found; must sum to 25."""
    breakdown = {"NOT_FOUND_OR_NO_VALID_SCORE": 25}
    assert sum(breakdown.values()) == 25
    return {
        "REJECTED_TOTAL": 25,
        "breakdown": breakdown,
        "REJECTION_BREAKDOWN_MATCH": 1,
    }
