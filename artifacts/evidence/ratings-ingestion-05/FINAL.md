# Ratings Stage 5 — FINAL

## VERDICT

`NEEDS_REPAIR`

supervised cycle inserted 125 observations; Stage5 cap is 100. Excess rows retained (valid Shikimori observations); claim limit fixed to ACCEPTED_TARGET for future cycles. No second live cycle.

## Summary

- Supervised Shikimori cycle ran once (`LIVE_CYCLES_ATTEMPTED=1`).
- Attempted 150 / inserted **125** (cap violation: max 100).
- AMD unchanged at 100; user votes unchanged at 0.
- Snapshot + gateway sample PASS; Qwen BLOCKED_NO_CONFIG; scheduler DISABLED.
- Claim limit repaired to `ACCEPTED_TARGET=100` in code; **no second live cycle**.

## Caps

| gate | value |
| --- | --- |
| ACCEPTED_TARGET | 100 |
| ACCEPTED_ACTUAL | 125 |
| CANDIDATE_CAP | 150 |
| ATTEMPTED | 150 |
| RATE_LIMIT_RPS | 0.1 |
| CONCURRENCY | 1 |
| AMD_NETWORK_CALLS | 0 |

## Blocks

| block | status |
| --- | --- |
| 00 | PASS |
| 01 | PASS |
| 02 | PASS |
| 03 | PASS |
| 04 | PASS (QWEN blocked no config) |
| 05 | PASS |
| 06 | NEEDS_REPAIR (accepted>100) |
| 07 | PASS (integrity ok; 125 rows retained) |
| 08 | PASS |
| 09 | PASS |
| 10 | PASS |
| 11 | PASS |
| 12 | PASS (timer OFF) |
| 13 | PASS |

## Evidence directory

`artifacts/evidence/ratings-ingestion-05/`
