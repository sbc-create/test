# Stage 5 accepted-cap repair — FINAL addendum

## Repair verdict

`ACCEPTED_HARD_CAP_REPAIR_PASS`

Live cycle was **not** re-run. Prior overshoot remains reconciled in place.

## Deliverables

| item | evidence |
| --- | --- |
| Atomic accepted hard cap ≤100 | `insert_observation_capped` + `accepted_target` on ingest; `ACCEPTED_CAP_PROOF.json` |
| Reconcile 125 rows | `ACCEPTED_CAP_RECONCILIATION.json` — 100 within-cap, 25 overshoot **retained** (0 deleted) |
| Safe supervised retry prep | `SUPERVISED_RETRY_PLAN.md` — no second live cycle; offline proof only |

## Gates

```text
ACCEPTED_CAP_PROOF_OK=1
DAILY_ACCEPTED_ABOVE_100_IN_PROOF=0
LIVE_NETWORK_THIS_REPAIR=0
SECOND_LIVE_CYCLE_ATTEMPT=0
OVERSHOOT_DELETED=0
AMD_ROWS_UNCHANGED=1
USER_VOTE_ROWS_UNCHANGED=1
```

## Policy on the 25 overshoot rows

Valid Shikimori observations (`id` 201–225 for run
`stage5-supervised-20260919T224456Z-9bc222`) are retained. Blind DELETE is
forbidden. Future cycles use the atomic cap so this cannot recur.
