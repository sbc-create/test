# Daily SLA

```text
DAILY_NEW_COVERAGE_TARGET=500
DAILY_UNIQUE_CANDIDATE_CAP=750
schema=ratings_daily_v1
```

- Denominator snapshot fixed at day start
- `effective_daily_target = min(500, uncovered_actionable_start)`
- Full coverage → target 0, MODE=FULL_COVERAGE
- Actionable saturated with gross <100% → ACTIONABLE_SATURATED (not FULL_COVERAGE)
- `newly_covered` requires mapping+observation+current+snapshot+gateway visibility
- Local votes / refresh / second source do not count as newly_covered
- Reason arithmetic must close

Module: `factory/ratings/daily.py`
