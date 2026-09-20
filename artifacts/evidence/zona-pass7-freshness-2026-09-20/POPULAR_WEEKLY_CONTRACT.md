# Popular WEEKLY_SNAPSHOT — Pass7 owner correction

## Contract now live

```text
POPULAR_REFRESH_MODE=WEEKLY_SNAPSHOT
POPULAR_REQUEST_TIME_RECOMPUTES=0
POPULAR_MAX_PUBLICATIONS_PER_WEEK=1
POPULAR_MEMBERSHIP_STABLE_WITHIN_WEEK=YES
POPULAR_RANDOM_ROTATION=NO
POPULAR_RECOMPUTE_CADENCE=7d
POPULAR_WEEK_ID=2026-W38
POPULAR_WEEKLY_SNAPSHOT_DIGEST=0d16b8a841810a9bef268710223ef576d3c14b685144ecfad1021dae9bad32dd
POPULAR_LAST_WEEKLY_BUILD_AT=2026-09-20T09:21:17Z
POPULAR_NEXT_WEEKLY_BUILD_AT=OWNER_GATE (proposed Mon 04:10 UTC)
POPULAR_WEEKLY_PUBLICATION_COUNT=1
POPULAR_MEMBERSHIP_CHANGES_WITHIN_WEEK=0 (20 live requests → 1 unique order)
POPULAR_EMERGENCY_REPAIR=0
```

## Implementation
- `automation/host/popular_weekly.py` — build / atomic publish / emergency repair / lock
- Frontend reads `/srv/lords/.frontend/zona-01-popular-weekly.json` only
- Headers: `X-Popular-Week-Id`, `X-Popular-Weekly-Digest`; ETag includes both
- No systemd timer enabled; owner example: `popular-weekly.zona-01.example.json`
- New-films / new-eps remain request-time on catalog `published_at`

## Verdict for history gate

```text
VERDICT=PASS_CONTRACT_NEEDS_TWO_WEEKLY_CYCLES
LONGER_OBSERVATION_REQUIRED=YES
```

Only one seeded ISO week observed. Need ≥2 routine weekly publications before closing Popular cadence.
