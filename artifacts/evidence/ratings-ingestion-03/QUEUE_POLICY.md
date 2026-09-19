# Queue policy — Stage 3 / final daily

## Priority order (stable)

1. Updated ongoing (new episode)
2. New ongoing without rating
3. New catalog titles (≤30 days)
4. Titles without rating with real AMD mapping
5. Stale ratings refresh
6. Old backlog (with aging so it does not starve)

## Mechanics

- Canonical-ID dedupe
- Stable tie-breaker: `canonical_title_id` ascending
- One HTTP request per canonical title (not per domain)
- Fuzzy mapping → review queue only (never auto-publish)
- Ambiguous mapping quarantined

## Caps

```text
FINAL_DAILY_ACCEPTED_TARGET=500
FINAL_DAILY_CANDIDATE_CAP=750
STAGE3_ACCEPTED_TARGET=100
STAGE3_CANDIDATE_CAP=150
```

Target is **accepted**, not HTTP attempts.

## Coverage-aware daily target

```text
required_today = min(500, eligible_uncovered)
```

- If `eligible_uncovered >= 500` → require 500 newly covered
- If `1..499` → process the remainder
- If `0` → zero new accepted is normal; still check ongoing refresh
- Unmapped and zero-score absences are **not** covered
- Refresh of existing score does not count as newly covered

## Zero-score / no-vote

Store in `rating_source_absence` as `ZERO_SCORE_NO_VOTE` (never display as 0).
Retry not before 7 days (`retry_after`) unless source record changes.

Implemented in `factory/ratings/coverage_policy.py` + Stage 3 canary absence writes.
