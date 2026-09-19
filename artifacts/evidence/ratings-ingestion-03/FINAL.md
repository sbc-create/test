# Ratings Ingestion Stage 3 — FINAL

## Verdict

```text
VERDICT=PASS_CLOSED_PRODUCTION_CANARY
```

## Heads

| Role | Value |
| --- | --- |
| FEATURE_HEAD (Stage 2) | `c199300828c72f0b91b546e3248346cdb7c8729e` |
| REPORT_HEAD | `9b3957d6c7145b70a9496502ba846887126717c4` |
| Stage 3 start tip | `942497b0afbd5b18b50601d101d1c3ef29a7a98e` |

See `GIT_PROVENANCE.md` for hash discrepancy explanation (no history rewrite).

## Production canary

| metric | value |
| --- | --- |
| DB | `/srv/site-factory/repo/var/ratings/ratings.sqlite` |
| attempted | 110 |
| accepted | 100 |
| rejected | 10 (`ZERO_SCORE_NO_VOTE`) |
| shortfall | 0 |
| idempotency replay | `new_observations=0`, `duplicate_prevented=100` |
| auto-stop | NO |
| rate | 0.1 rps, concurrency=1 |

## Publication

Closed snapshots:

- `/srv/site-factory/repo/var/ratings/snapshots/animedia.icu/ratings_snapshot_v1.json`
- `/srv/site-factory/repo/var/ratings/snapshots/animedia.space/ratings_snapshot_v1.json`

HTTP noindex preserved on both domains (`NOINDEX_VERIFICATION.json`).
No sitemap URL additions. Public indexed publication = 0.

## Scheduler / Qwen

- Scheduler installed, **DISABLED**, daily limit 0
- `QWEN_REPORT.json` / `.md` built; `QWEN_DELIVERY=BLOCKED_NO_CONFIG`
- Qwen write permissions = 0

## Guards

No push, merge, DNS, indexing open, layout/player changes, or fake user votes.
