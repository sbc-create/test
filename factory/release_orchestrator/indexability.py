"""Indexability guards: Core exact-domain policy only."""

from __future__ import annotations

from typing import Any

from factory.release_orchestrator.registry import SiteReleaseRecord

OPEN_TO_CLOSED_DENY = "OPEN_TO_CLOSED_REQUIRES_APPROVAL"
CLOSED_TO_OPEN_DENY = "CLOSED_TO_OPEN_REQUIRES_APPROVAL"
INDEXABILITY_MISMATCH = "INDEXABILITY_HARD_FAILURE"


class IndexabilityError(ValueError):
    def __init__(self, code: str, detail: str = ""):
        self.code = code
        super().__init__(code if not detail else f"{code}: {detail}")


def as_state(value: str | bool) -> str:
    if isinstance(value, bool):
        return "OPEN" if value else "CLOSED"
    text = str(value).upper()
    if text in {"OPEN", "CLOSED"}:
        return text
    if text in {"TRUE", "1", "YES"}:
        return "OPEN"
    return "CLOSED"


def assert_transition_allowed(
    *,
    before: str,
    after: str,
    mutations_allowed: bool,
    site_id: str,
) -> None:
    before_s = as_state(before)
    after_s = as_state(after)
    if before_s == after_s:
        return
    if before_s == "OPEN" and after_s == "CLOSED" and not mutations_allowed:
        raise IndexabilityError(OPEN_TO_CLOSED_DENY, site_id)
    if before_s == "CLOSED" and after_s == "OPEN" and not mutations_allowed:
        raise IndexabilityError(CLOSED_TO_OPEN_DENY, site_id)


def assert_matches_registry(record: SiteReleaseRecord, live_state: str) -> None:
    expected = as_state(record.expected_indexability)
    actual = as_state(live_state)
    if expected != actual:
        raise IndexabilityError(
            INDEXABILITY_MISMATCH,
            f"{record.site_id}: expected={expected} live={actual}",
        )


def evaluate_site_row(row: dict[str, Any], *, mutations_allowed: bool) -> None:
    assert_transition_allowed(
        before=row["expected_indexability_before"],
        after=row["expected_indexability_after"],
        mutations_allowed=mutations_allowed,
        site_id=row["site_id"],
    )
