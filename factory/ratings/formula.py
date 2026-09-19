"""animedia_blend_v1 — AMD baseline + accepted local votes.

Uses Decimal. Stored combined_raw is full precision; UI rounds to 2 places.
Shikimori never participates in this formula.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

FORMULA_VERSION = "animedia_blend_v1"
AMD_BASELINE_PRIOR_CAP = 100
MISSING_VOTE_COUNT_PRIOR_WEIGHT = 25
MIN_PUBLIC_LOCAL_VOTES_WITHOUT_BASELINE = 5


@dataclass(frozen=True)
class CombinedResult:
    combined_raw: Decimal | None
    combined_ui: str | None
    baseline_weight: int
    amd_score: Decimal | None
    amd_vote_count: int | None
    local_vote_count: int
    local_vote_sum: int
    state: str
    formula_version: str = FORMULA_VERSION
    quality_flags: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "combined_raw": None if self.combined_raw is None else str(self.combined_raw),
            "combined_ui": self.combined_ui,
            "baseline_weight": self.baseline_weight,
            "amd_score": None if self.amd_score is None else str(self.amd_score),
            "amd_vote_count": self.amd_vote_count,
            "local_vote_count": self.local_vote_count,
            "local_vote_sum": self.local_vote_sum,
            "state": self.state,
            "formula_version": self.formula_version,
            "quality_flags": list(self.quality_flags),
        }


def _ui(value: Decimal) -> str:
    quantized = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{quantized:.2f}"


def baseline_weight_for(amd_score: Decimal | None, amd_vote_count: int | None) -> tuple[int, list[str]]:
    flags: list[str] = []
    if amd_score is None:
        return 0, flags
    if amd_vote_count is not None and amd_vote_count > 0:
        return min(int(amd_vote_count), AMD_BASELINE_PRIOR_CAP), flags
    # score present, vote count missing
    flags.append("VOTE_COUNT_MISSING")
    return MISSING_VOTE_COUNT_PRIOR_WEIGHT, flags


def combine_amd_local(
    *,
    amd_score: Decimal | float | str | None,
    amd_vote_count: int | None,
    accepted_local_vote_sum: int,
    accepted_local_vote_count: int,
) -> CombinedResult:
    score = None if amd_score is None else Decimal(str(amd_score))
    local_count = int(accepted_local_vote_count)
    local_sum = int(accepted_local_vote_sum)
    if local_count < 0 or local_sum < 0:
        raise ValueError("local aggregates cannot be negative")
    if local_count and local_sum < local_count:
        raise ValueError("local_sum < local_count")
    if local_sum > local_count * 10:
        raise ValueError("local_sum exceeds max")

    weight, flags = baseline_weight_for(score, amd_vote_count)

    if score is None:
        if local_count < MIN_PUBLIC_LOCAL_VOTES_WITHOUT_BASELINE:
            return CombinedResult(
                combined_raw=None,
                combined_ui=None,
                baseline_weight=0,
                amd_score=None,
                amd_vote_count=amd_vote_count,
                local_vote_count=local_count,
                local_vote_sum=local_sum,
                state="INSUFFICIENT_LOCAL",
                quality_flags=tuple(flags),
            )
        avg = (Decimal(local_sum) / Decimal(local_count)) if local_count else None
        return CombinedResult(
            combined_raw=avg,
            combined_ui=_ui(avg) if avg is not None else None,
            baseline_weight=0,
            amd_score=None,
            amd_vote_count=amd_vote_count,
            local_vote_count=local_count,
            local_vote_sum=local_sum,
            state="LOCAL_ONLY",
            quality_flags=tuple(flags),
        )

    if local_count == 0:
        return CombinedResult(
            combined_raw=score,
            combined_ui=_ui(score),
            baseline_weight=weight,
            amd_score=score,
            amd_vote_count=amd_vote_count,
            local_vote_count=0,
            local_vote_sum=0,
            state="AMD_ONLY",
            quality_flags=tuple(flags),
        )

    numerator = score * Decimal(weight) + Decimal(local_sum)
    denominator = Decimal(weight) + Decimal(local_count)
    raw = numerator / denominator
    return CombinedResult(
        combined_raw=raw,
        combined_ui=_ui(raw),
        baseline_weight=weight,
        amd_score=score,
        amd_vote_count=amd_vote_count,
        local_vote_count=local_count,
        local_vote_sum=local_sum,
        state="AMD_PLUS_LOCAL",
        quality_flags=tuple(flags),
    )
