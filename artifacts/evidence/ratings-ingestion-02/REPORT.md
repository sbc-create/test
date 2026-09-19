# Ratings Ingestion Stage 2 Report

## Heads

- START_HEAD: `174f03f50b00889dbe740a12d11527c9aa97e315`
- BRANCH: `cursor/ratings-ingestion-01`
- WORKTREE: `/home/claude/wt-ratings-ingestion-01`

## Implementation

Extended `factory/ratings/` (no parallel module):

- AMD.online adapter + centralized selectors + sanitized fixtures
- Local votes (CRUD, idempotency, quarantine, aggregates)
- `animedia_blend_v1` combined formula + `animedia_rotation_v1`
- Gateway contract with separate `ratingSources` / `localRating` / `combinedRating`
- Daily SLA + Qwen message builder (`ratings_daily_v1`)
- Migration `0003` (isolated only)

## Shikimori isolated canary

| metric | Stage1 dry-run | Stage2 apply |
| --- | --- | --- |
| attempted | 100 | 100 |
| matched | 92 | 93 |
| inserted | 0 | 93 |
| replay inserted | — | 0 |

Delta +1 matched: different queue slice / upstream score availability on re-run;
manual sample of 25 stored scores re-checked live — **0 wrong**.

## AMD

- Permission: **NOT_PROVIDED**
- Live canary: **BLOCKED_PERMISSION**
- Contract probe: 3 GET (robots, home, 1 detail) — selectors confirmed
- Fixtures + parser tests: PASS
- Auto-stop on 403: tested

## Local / formula / rotation / daily

All acceptance examples automated. Qwen delivery **NOT_CONFIGURED** (report ready).

## Production guards

No production DB migration, scheduler enable, frontend deploy, push, or merge.
