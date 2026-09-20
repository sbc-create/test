# Cadence recommendations — Zona Pass7 (Popular WEEKLY correction)

## Found authoritative schedules
- `nova-daily-refresh.timer` — Zona catalog/details (daily ~03:30 UTC). Drives **new films / recently added / new series (catalog)**.
- `nova-catalog-refresh` — skips zona-01.
- **No** approved Popular weekly timer on host (`timer_enabled=false`).

## Popular (owner correction)
```
POPULAR_REFRESH_MODE=WEEKLY_SNAPSHOT
POPULAR_RECOMPUTE_CADENCE=7d
POPULAR_REQUEST_TIME_RECOMPUTES=0
POPULAR_MAX_PUBLICATIONS_PER_WEEK=1
POPULAR_MEMBERSHIP_STABLE_WITHIN_WEEK=YES
POPULAR_RANDOM_ROTATION=NO
```

Removed obsolete criterion: `POPULAR_SCORING_RECOMPUTE<=24h`.

Stability of Popular membership **inside one ISO week is expected**, not a defect.

Proposed owner schedule (not enabled): Monday 04:10 UTC — see
`automation/host/popular-weekly.zona-01.example.json`.

## Other shelves (unchanged by this correction)
| Section | Cadence |
|---|---|
| Recently added films/series | Catalog publish (daily today) |
| /new/ premiere | Details premiere_date changes |
| Related | Input change only |
| True new episodes | Blocked until episode timestamps exist |

## Owner targets still proposed (not norms)
```
NEW_MOVIE_SOURCE_TO_LIVE_TARGET_P95<=24h
NEW_EPISODE_SOURCE_TO_LIVE_TARGET_P95<=8h
CATALOG_TO_LIVE_TARGET_P95<=30m
CACHE_VISIBILITY_TARGET_P95<=15m
NEW_SHELF_RECOMPUTE<=24h   # recently-added / new routes only
POPULAR_RECOMPUTE_CADENCE=7d
```
