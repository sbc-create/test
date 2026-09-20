# Cadence recommendations (NOT existing SLA unless noted)

## Found authoritative SLAs
- `lords-content-refresh.timer` documents 15-minute freshness for **Lords static** sites — does **not** drive Zona.
- `nova-daily-refresh.timer` OnCalendar 03:30 UTC — **actual** Zona catalog/details publish cadence.
- `nova-catalog-refresh` 5 min — explicitly skips zona-01.

## Proposed owner targets (not current norms)
```
NEW_MOVIE_SOURCE_TO_LIVE_TARGET_P95<=24h
NEW_EPISODE_SOURCE_TO_LIVE_TARGET_P95<=8h   # blocked until episode timestamps exist
CATALOG_TO_LIVE_TARGET_P95<=30m            # requires more frequent canonical publish OR accept daily
CACHE_VISIBILITY_TARGET_P95<=15m           # met for HTML (no-store); process reload now mtime-based
NEW_SHELF_RECOMPUTE<=24h                   # matches daily today
POPULAR_SCORING_RECOMPUTE<=24h             # rating shelves; rename already applied
```

## What should change when
| Section | Cadence |
|---|---|
| Recently added films/series | On catalog membership change (today: daily) |
| /new/ premiere novelty | On premiere_date changes in details |
| High-rating-among-recent | On ratings or recent pool change |
| Related | Only when title metadata/neighbors change |
| Collections (genre/year filters) | On snapshot revision |
| True «new episodes» | **Blocked** until episode timestamps in authorized details |
