# BLOCK_B08 — Player shell

- stage: ANIMEDIA-BLOCKWISE-PARITY-03
- block_id: B08
- status: PASS_LOCAL_PENDING_LIVE
- B08_OWNER_DEPENDENCY: RESOLVED
- GENERIC_DEFAULT_EPISODE_POLICY: FIRST_PLAYABLE_DETERMINISTIC
- OWNER_DECISION_ID: ANIMEDIA-B10-B16-20260920-01
- CONTRACT_SHA256: `5f2112e25ef974333c388bad405abfae3c3d460a713b028afa3c0e549b8eaeb3`
- CONTRACT_MUTATED: 0

## Intent

Full-width 16:9 player shell, status beside heading, hero→player within
120/96/80 px, heading→shell 16–24 px, single instance, autoplay=0.

## Owner resolution

See `B08/OWNER_RESOLUTION.md`.

- Generic hub: first playable after `(season ASC, episode ASC)`
- Exact episode: preserved
- `DEFAULT_EPISODE_POLICY_DATA_GAP=0`
- Policy file: `config/animedia-default-episode-policy.json`

## AFTER_LOCAL

| viewport | hero→player | heading→shell | aspect | instances |
| --- | --- | --- | --- | --- |
| d1440 | 88 | 20 | 1.778 | 1 |
| t768 | 80 | 16 | 1.778 | 1 |
| m390 | 80 | 16 | 1.778 | 1 |

Oracle failures: 0.

## Next

B10 recommendations
