"""Coverage-aware daily targets and Stage 3 / final gates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

FINAL_DAILY_ACCEPTED_TARGET = 500
FINAL_DAILY_CANDIDATE_CAP = 750
STAGE3_ACCEPTED_TARGET = 100
STAGE3_CANDIDATE_CAP = 150
ZERO_SCORE_RETRY_DAYS = 7


@dataclass(frozen=True)
class CoverageTarget:
    eligible_total: int
    covered_valid: int
    eligible_uncovered: int
    daily_accepted_target: int
    daily_candidate_cap: int
    full_coverage: bool
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        pct = (
            round(100.0 * self.covered_valid / self.eligible_total, 2)
            if self.eligible_total
            else None
        )
        return {
            "eligible_total": self.eligible_total,
            "covered_valid": self.covered_valid,
            "eligible_uncovered": self.eligible_uncovered,
            "coverage_percent": pct,
            "daily_accepted_target": self.daily_accepted_target,
            "daily_candidate_cap": self.daily_candidate_cap,
            "full_coverage": self.full_coverage,
            "note": self.note,
        }


def compute_daily_target(
    *,
    eligible_total: int,
    covered_valid: int,
    accepted_cap: int = FINAL_DAILY_ACCEPTED_TARGET,
    candidate_cap: int = FINAL_DAILY_CANDIDATE_CAP,
) -> CoverageTarget:
    """required_today = min(accepted_cap, eligible_uncovered); 0 is OK at 100%."""
    eligible_total = max(0, int(eligible_total))
    covered_valid = max(0, min(int(covered_valid), eligible_total))
    uncovered = max(0, eligible_total - covered_valid)
    full = eligible_total > 0 and uncovered == 0
    if full:
        target = 0
        note = "100% coverage: zero new accepted is normal; still refresh ongoing"
    elif uncovered >= accepted_cap:
        target = accepted_cap
        note = f"require {accepted_cap} newly covered"
    else:
        target = uncovered
        note = f"require remaining uncovered={uncovered}"
    return CoverageTarget(
        eligible_total=eligible_total,
        covered_valid=covered_valid,
        eligible_uncovered=uncovered,
        daily_accepted_target=target,
        daily_candidate_cap=candidate_cap,
        full_coverage=full,
        note=note,
    )


def stage3_gates() -> dict[str, int]:
    return {
        "STAGE3_ACCEPTED_TARGET": STAGE3_ACCEPTED_TARGET,
        "STAGE3_CANDIDATE_CAP": STAGE3_CANDIDATE_CAP,
        "FINAL_DAILY_ACCEPTED_TARGET": FINAL_DAILY_ACCEPTED_TARGET,
        "FINAL_DAILY_CANDIDATE_CAP": FINAL_DAILY_CANDIDATE_CAP,
    }


def zero_score_retry_after(observed_at: str | None = None) -> str:
    base = datetime.now(timezone.utc)
    if observed_at:
        try:
            base = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        except ValueError:
            pass
    return (base + timedelta(days=ZERO_SCORE_RETRY_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_covered_row(*, score, vote_count, mapping_state: str = "VERIFIED") -> bool:
    """Unmapped and zero-score absences are NOT covered."""
    if mapping_state not in ("VERIFIED", "CONFIRMED", "EXACT"):
        return False
    if score is None:
        return False
    try:
        if float(score) == 0.0:
            return False
    except (TypeError, ValueError):
        return False
    return True
