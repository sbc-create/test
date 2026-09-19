# Git provenance — Stage 3 preflight

## Worktree

```text
WORKTREE=/home/claude/wt-ratings-ingestion-01
BRANCH=cursor/ratings-ingestion-01
```

## Heads (do not rewrite history)

| Role | Commit | Meaning |
| --- | --- | --- |
| `FEATURE_HEAD` | `c199300828c72f0b91b546e3248346cdb7c8729e` | Stage 2 feature: AMD closed canary ingestion |
| `REPORT_HEAD` | `9b3957d6c7145b70a9496502ba846887126717c4` | Docs commit that first wrote FINAL_HEAD into REPORT/SUMMARY |
| `FINAL_WORKTREE_HEAD` (pre-Stage-3 tip) | `942497b0afbd5b18b50601d101d1c3ef29a7a98e` | Docs commit that set SUMMARY FINAL_HEAD field |

## Discrepancy explained

1. Stage 2 closeout produced **three** commits, not one tip equal to the feature hash:
   - `c199300` — implementation + evidence (41 files)
   - `9b3957d` — recorded FINAL_HEAD/COMMIT into REPORT.md / STAGE2_SUMMARY.json
   - `942497b` — corrected SUMMARY `FINAL_HEAD` tip pointer again
2. Operator note `REPORTED_FINAL_HEAD=942497b0afbd5b1b…` matches tip **prefix** `942497b` but has a typo in the middle (`…5b1b85…` vs actual `…5b18b5…`). Actual tip at Stage 3 start: `942497b0afbd5b18b50601d101d1c3ef29a7a98e`.
3. `OBSERVED_REPORT_COMMIT_PREFIX=9b3957d` is the **middle** docs commit (`REPORT_HEAD`), not the tip.
4. History was **not** rewritten to force a single hash.

## Ancestor check

`c199300` is an ancestor of current HEAD (`git merge-base --is-ancestor` → ok).

## Untracked `.prev` snapshots (Stage 2)

```text
artifacts/evidence/ratings-ingestion-02/closed-noindex/animedia.icu/ratings_snapshot_v1.candidate.json.prev
artifacts/evidence/ratings-ingestion-02/closed-noindex/animedia.space/ratings_snapshot_v1.candidate.json.prev
```

Origin: `atomic_publish_candidate` renamed the pre-backfill candidate aside when component backfill republished. Intentionally **not** committed in Stage 2 (intermediate). Left untracked; not deleted; not required for Stage 3.

## Canonical ratings DB (authoritative)

Resolved from systemd unit `automation/host/systemd/ratings-ingestion.service` → `ReadWritePaths=/srv/site-factory/repo/var/ratings`:

```text
CANONICAL_RATINGS_DB=/srv/site-factory/repo/var/ratings/ratings.sqlite
```

Host path `/srv/site-factory/repo/var/ratings` is writable by this operator. Live HTML trees under `/srv/lords/animedia-0{1,2}` are owned by `lords` and are **not** mutated for layout; closed snapshots publish under `var/ratings/snapshots/{domain}/` + evidence.
