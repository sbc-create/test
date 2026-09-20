# BLOCK_B08 — Player shell

- stage: ANIMEDIA-BLOCKWISE-PARITY-03
- block_id: B08
- status: PASS_LOCAL_PENDING_LIVE
- CONTRACT_SHA256: `5f2112e25ef974333c388bad405abfae3c3d460a713b028afa3c0e549b8eaeb3`
- CONTRACT_MUTATED: 0

## Intent

Full-width 16:9 player shell, status beside heading, hero→player within
120/96/80 px, heading→shell 16–24 px, single instance, autoplay=0.

## AFTER_LOCAL

| viewport | hero→player | heading→shell | aspect | instances |
| --- | --- | --- | --- | --- |
| d1440 | 88 | 20 | 1.778 | 1 |
| t768 | 80 | 16 | 1.778 | 1 |
| m390 | 80 | 16 | 1.778 | 1 |

Oracle failures: 0.

## Ownership gap

`DEFAULT_EPISODE_POLICY_DATA_GAP=1` — versioned default-episode policy file
absent → `BLOCKED_DEPENDENCY(owner=player)`. Template does not invent a new
selection policy; legacy hub helper retained and flagged
`data-default-episode-policy="absent"`.

## Next

B09 exact episode page
