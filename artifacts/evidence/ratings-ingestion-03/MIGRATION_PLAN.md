# Migration plan — Stage 3

## Authoritative DB

```text
CANONICAL_RATINGS_DB=/srv/site-factory/repo/var/ratings/ratings.sqlite
```

Resolved from `automation/host/systemd/ratings-ingestion.service` →
`ReadWritePaths=/srv/site-factory/repo/var/ratings`.

Worktree fallback (if host path unavailable): `{FACTORY_ROOT}/var/ratings/ratings.sqlite`.

## Migrations

| version | purpose |
| --- | --- |
| 0002 | core ratings tables (observations append-only, current, queue, …) |
| 0003 | AMD components, local votes, combined projection, daily |
| 0004 | `rating_source_absence` for ZERO_SCORE_NO_VOTE + 7-day retry |

## Safety gates

1. Schema inventory before (`DB_BEFORE.json`)
2. Recoverable file backup under `var/ratings/backups/`
3. Backup byte digest verified
4. Dry-run: `RatingsStore` apply on isolated scratch for rollback proof
5. Apply 0002→0004 transactionally via store `ensure_schema`
6. Confirm migrations do **not** DROP catalog tables or overwrite observations
7. Rollback proof: restore backup copy to scratch (`ROLLBACK_PROOF.md`)

## Non-goals

- No production catalog mutation
- No deletion of last-known-good `rating_current` on provider failure
- No public indexed publication
