# COMMUNITY-RATINGS-07 — 1% OBSERVATION — FINAL REPORT

```text
VERDICT=OBSERVATION_PENDING
STAGE=COMMUNITY-RATINGS-07-1PCT-OBSERVATION
START_HEAD=ab9dec90c2084614f9f227730be5240c4d7baefc
OBSERVATION_STARTED_AT=2026-09-20T20:39:20Z
OBSERVATION_FINISHED_AT=2026-09-21T12:11:58Z
OBSERVATION_HOURS=15.544
MIN_24H_COMPLETE=0
ELIGIBLE_PAGEVIEWS=0
EXPOSED_VISITORS=0
PUBLIC_WRITE_ROLLOUT_PERCENT=1
REAL_CAST_COUNT=0
REAL_UPDATE_COUNT=0
REAL_RETRACT_COUNT=0
NATIVE_VOTE_COUNT=0
SYNTHETIC_VOTES_REMAINING=0
FAKE_USER_VOTES_INSERTED=0
IDENTITY_BYPASSES=0
CSRF_FAILURES=0
XSS_FAILURES=0
RATE_LIMIT_VIOLATIONS=0
QUARANTINED_VOTES=0
DUPLICATE_ACTIVE_VOTES=0
PREVIEW_WRITE_MISMATCHES=0
AGGREGATE_REBUILD_MISMATCHES=0
SQLITE_INTEGRITY_CHECK=ok
FOREIGN_KEY_FAILURES=0
KILL_SWITCH_TRIGGERED=0
API_ERROR_RATE=0.0 (0/0 — no real write attempt)
LATENCY_P50_MS=UNMEASURED
LATENCY_P95_MS=UNMEASURED
LIVE_INDEXABILITY_BEFORE=OPEN
LIVE_INDEXABILITY_AFTER=OPEN
RATINGS_ROLLOUT_BEFORE=1
RATINGS_ROLLOUT_AFTER=1
ANIMEDIA_MUTATIONS=0
COMMENTS_MUTATIONS=0
INDEXABILITY_MUTATIONS=0
DNS_MUTATIONS=0
PUSH_PERFORMED=0
MERGE_PERFORMED=0
TESTS=51_unit_PASS_x2
READY_FOR_OWNER_10PCT_APPROVAL=0
READY_FOR_PUBLIC_WRITE_100PCT=NO
```

## Why OBSERVATION_PENDING and not a 10% packet

Two independent reasons, and the second one matters more than the clock.

**1. The 24h window is not closed.** 15.5h of 24h elapsed; the gate opens at
`2026-09-21T20:39:20Z`.

**2. The sample is empty, and more waiting will not fill it.** The vote widget
is not deployed on the live frontend. Four live `yummyani.site/anime/*` pages
carry no `cr-*` markup, no `community_rating.js`, and no reference to
`/api/community/ratings` anywhere in the Next.js bundle; the widget asset
returns 404 on all three expected paths. Only the nginx-proxied JSON API is
public. Over 15.5h the gateway recorded 47 widget session bootstraps and 31
minted identities, but **0 eligible (cohort) impressions and 0 exposed
visitors** — so 0 real cast/update/retract. Approving 10% from a zero-exposure
canary would not be widening a proven rollout; it would be the code's first
real run, at ten times the blast radius.

Rollback is not required: every safety gate is green and the system sits in a
fail-safe state — writes are enabled but unreachable from the UI, no real or
synthetic vote remains, and the kill-switch never fired.

## Gates that were actually exercised

| Gate | Result | Evidence |
| --- | --- | --- |
| Real votes cast / updated / retracted | 0 / 0 / 0 | `01-observation` |
| Synthetic votes remaining | 0 (1 residual row deleted) | `06-synthetic-cleanup` |
| Identity bypasses (12 negative probes) | 0 | `02-security` |
| CSRF / XSS failures | 0 / 0 | `02-security` |
| Ledger unchanged by probes | before == after | `02-security` |
| Duplicate active votes | 0 | `03-db-integrity` |
| Preview == write (73 transitions) | 0 mismatches | `03-db-integrity` |
| Aggregate rebuild + idempotency | 0 mismatches, idempotent | `03-db-integrity` |
| `integrity_check` / foreign keys | `ok` / 0 | `03-db-integrity` |
| Rate-limit violations, quarantines | 0 / 0 | `01-observation` |
| 5xx on any traffic | 0 | `01-observation` |
| Kill-switch | never fired, 63 monitor ticks, no gap > 20 min | `01-observation` |
| `yummyani.site` indexability | OPEN → OPEN | `04-live-ui` |
| Animedia | CLOSED_NOINDEX, 0 mutations, 0 vote events | `04-live-ui`, `05-isolation` |
| Comments | 0 rows, disabled | `03-db-integrity` |
| Shikimori / derived display on Yummy | 0 | `05-isolation` |
| Structured `aggregateRating` | 0 on live pages | `04-live-ui` |
| Rollout percent, flag drift | 1, no drift | `05-isolation` |
| Tests | 51 passed × 2 consecutive | `07-tests` |

## Defects found and fixed

1. **Residual synthetic vote row.** One supervised-canary row
   (`actor_id 0000…014c`, `RETRACTED`) was still in `community_votes`. It
   contributed nothing to any aggregate but broke the Stage02 production
   contract test asserting `community_votes == 0`. Deleted; the
   `community_vote_events` audit trail is deliberately kept as proof the
   canary ran and was retracted.
2. **Stage06 admin-UI regression.** Commit `c97d781` dropped the `read-only`
   markers from the read-scope admin page, breaking the Stage02 RBAC contract.
   Restored, keeping Stage06's wording.
3. **Flaky concurrency test.** `test_concurrent_linearizable` failed in 2 of 4
   loaded full-suite runs and passed in isolation. Root cause characterised over
   6 reconstructed runs: `threading.Barrier(20)` across 100 tasks ran in five
   waves; one slow wave tripped `timeout=5` and a tripped Barrier stays broken,
   so 80 of 100 workers raised `BrokenBarrierError` — with **zero sqlite, busy,
   or linearizability errors**. Replaced with a `threading.Event` start gate;
   all three assertions untouched. 12/12 under stress afterwards.

Stage06 reported `TESTS=17_unit_PASS_x2`, which was true of its own two modules.
The full `tests/unit/community` package (51 tests) never ran in that stage,
which is why all three of the above went unseen.

## Observability gap to close before 10%

`monitor_once` runs in a **separate process** from the gateway and calls
`metrics.snapshot()` on its own fresh, empty counters. The `metrics` block in
all 63 ticks is therefore structurally zero regardless of real traffic:
impressions, write attempts, 4xx/5xx and latency are **not measured by the
monitor at all**. The DB integrity, FK, aggregate-mismatch, rollout-percent and
kill-switch gates in the same ticks are genuine and did their job.

Today the only traffic view is a manual `/health` poll, and those counters are
lost on any gateway restart — one already happened at `20:44:11Z`, leaving the
first 4m51s of the window uncovered.

## Owner actions required

1. Ship the vote widget to `yummyani.site` — without it no rollout percentage
   means anything.
2. Fix monitor metric export (share gateway counters, or have the monitor poll
   `/health`) so 10% can be observed rather than assumed.
3. Then restart a 1% window and collect ≥ 24h with non-zero exposure. Only after
   that does a 10% packet carry information.

No 10% approval is requested. The percentage was left at exactly 1.
