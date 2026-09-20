"""Persistent run ledger formulas and serialization for Stage 5R."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class RunLedger:
    """Authoritative cycle counters. Formulas enforced in ``validate``."""

    run_id: str
    source: str
    quota_window: str
    cycle_status: str = "OPEN"
    lease_idempotency_key: str = ""

    planned: int = 0
    claimed: int = 0
    attempted: int = 0
    accepted: int = 0
    newly_covered: int = 0
    refreshed: int = 0
    rejected: int = 0
    deferred_capacity: int = 0
    unprocessed: int = 0
    reserved: int = 0
    committed: int = 0
    failed: int = 0
    shortfall: int = 0
    overage: int = 0

    candidate_attempt_cap: int = 150
    accepted_hard_cap: int = 100
    accepted_target: int = 100

    rejection_breakdown: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def recompute(self) -> None:
        self.accepted = int(self.newly_covered) + int(self.refreshed)
        self.shortfall = max(0, int(self.accepted_target) - self.accepted)
        self.overage = max(0, self.accepted - int(self.accepted_hard_cap))
        # attempted identity: accepted + rejected + deferred + unprocessed
        # (failed counted inside rejected or separately — keep failed distinct)
        deferred_or_unprocessed = int(self.deferred_capacity) + int(self.unprocessed)
        expected_attempted = self.accepted + int(self.rejected) + deferred_or_unprocessed
        if self.attempted == 0 and expected_attempted:
            self.attempted = expected_attempted
        self.committed = self.accepted  # DB_DELTA = COMMITTED_ACCEPTED

    def validate(self) -> list[str]:
        self.recompute()
        errors: list[str] = []
        if self.accepted != self.newly_covered + self.refreshed:
            errors.append("ACCEPTED!=NEWLY_COVERED+REFRESHED")
        if self.accepted > self.accepted_hard_cap:
            errors.append(f"ACCEPTED>{self.accepted_hard_cap}")
        if self.shortfall != max(0, self.accepted_target - self.accepted):
            errors.append("SHORTFALL_MISMATCH")
        if self.overage != max(0, self.accepted - self.accepted_hard_cap):
            errors.append("OVERAGE_MISMATCH")
        deferred_or_unprocessed = self.deferred_capacity + self.unprocessed
        if self.attempted != self.accepted + self.rejected + deferred_or_unprocessed:
            errors.append(
                "ATTEMPTED!=ACCEPTED+REJECTED+DEFERRED_OR_UNPROCESSED "
                f"({self.attempted}!={self.accepted}+{self.rejected}+{deferred_or_unprocessed})"
            )
        if self.committed != self.accepted:
            errors.append("DB_DELTA!=COMMITTED_ACCEPTED")
        if self.rejection_breakdown and sum(self.rejection_breakdown.values()) != self.rejected:
            errors.append("REJECTION_BREAKDOWN_SUM_MISMATCH")
        if self.planned > self.candidate_attempt_cap:
            errors.append("PLANNED>CANDIDATE_ATTEMPT_CAP")
        return errors

    def as_dict(self) -> dict[str, Any]:
        self.recompute()
        d = asdict(self)
        d["formulas"] = {
            "ACCEPTED": "NEWLY_COVERED+REFRESHED",
            "ACCEPTED_CAP": "ACCEPTED<=ACCEPTED_HARD_CAP",
            "SHORTFALL": "max(0,TARGET-ACCEPTED)",
            "OVERAGE": "max(0,ACCEPTED-TARGET_HARD_CAP)",
            "ATTEMPTED": "ACCEPTED+REJECTED+DEFERRED_OR_UNPROCESSED",
            "DB_DELTA": "COMMITTED_ACCEPTED",
        }
        d["validation_errors"] = self.validate()
        return d
