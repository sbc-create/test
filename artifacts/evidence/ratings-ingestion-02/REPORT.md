# Ratings Ingestion Stage 2 Report

## Heads

- START_HEAD (Stage 1): `174f03f50b00889dbe740a12d11527c9aa97e315`
- PREV_IMPL_HEAD: `ada31202581984c2de16e8365355ce982fd1ed86`
- FINAL_HEAD: `c199300828c72f0b91b546e3248346cdb7c8729e`
- COMMIT: `c199300 feat(ratings): complete AMD closed canary ingestion stage`
- BRANCH: `cursor/ratings-ingestion-01`
- WORKTREE: `/home/claude/wt-ratings-ingestion-01`

## Verdict

```text
IMPLEMENTATION_VERDICT=PASS
AMD_CLOSED_CANARY_VERDICT=PASS
OVERALL_VERDICT=PASS_CLOSED_CANARY
READY_FOR_STAGE_3=YES
```

## AMD permission modes

```text
AMD_PERMISSION_STATUS=NOT_PROVIDED
AMD_CLOSED_CANARY_INGESTION=ALLOWED
AMD_CLOSED_NOINDEX_PUBLICATION=ALLOWED
AMD_PUBLIC_INDEXED_PUBLICATION=BLOCKED_PENDING_SEPARATE_APPROVAL
```

Written permission is **not** required for closed technical canary. It remains
the gate only before mass public indexed publication.

## First CLI attempt (failed, superseded)

Task `902556` / `AMD_CANARY_FIRST_CLI_FAILURE.json`:

- `exit_code=2` in 266ms
- cause: stale argparse without `--urls-file` (no AMD detail GETs)
- superseded by successful attempt 2 → `AMD_CLOSED_CANARY_REPORT.json`

## AMD closed canary (live attempt 2)

| metric | value |
| --- | --- |
| attempted | 100 |
| accepted | 90 |
| rejected | 10 |
| reject class | ZERO_SCORE_NO_VOTE (`0.0` / `(0)`), see `AMD_CLOSED_CANARY_REJECTIONS.json` |
| network / challenge / parser failures | 0 / 0 / 0 |
| auto-stop | NO |
| rate | ≤0.1 rps, concurrency=1 |
| components | 90/90 after backfill |
| replay duplicate prevented | 1 |

Raw proof of reject class: `raw/amd_detail_5723_oor.html` → score `0.0`, votes `(0)`.

Closed noindex candidate snapshots:

- `closed-noindex/animedia.icu/ratings_snapshot_v1.candidate.json`
- `closed-noindex/animedia.space/ratings_snapshot_v1.candidate.json`

Display verified: AMD score, vote count, story/characters/art/voice,
`Источник: AMD.online`, canonical source URL. Blend + rotation:
`BLEND_LOCAL_SMOKE.json`, `rotation_before_after.json`.

## CAPTCHA detection

`dle_captcha_type` alone is **not** a challenge. Real ddos-guard / Cloudflare /
`g-recaptcha` / `hcaptcha` / `captcha-box` (tiny non-detail pages) still trip
auto-stop. Covered by unit tests.

## Shikimori isolated canary (unchanged)

attempted 100 / matched 93 / inserted 93; replay 0.

## Production guards

No production DB migration, scheduler enable, frontend deploy, push, merge,
public indexing, DNS/nginx changes. Stage 3 **not started**.
