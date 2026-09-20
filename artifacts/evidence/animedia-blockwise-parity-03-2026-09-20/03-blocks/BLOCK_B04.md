# BLOCK_B04 — Schedule / honest empty

- stage: ANIMEDIA-BLOCKWISE-PARITY-03
- block_id: B04
- status: PASS_LOCAL_PENDING_LIVE
- CONTRACT_SHA256: `5f2112e25ef974333c388bad405abfae3c3d460a713b028afa3c0e549b8eaeb3`
- CONTRACT_MUTATED: 0

## Intent

No invented schedule on home (0 px). `/schedule/` shows honest empty ≤260 px
until `episode_air_feed` exists.

## Ownership

core_data

## AFTER_LOCAL

| page | viewport | panel h |
| --- | --- | --- |
| home | d1440/m390 | absent |
| /schedule/ | d1440 | 116 px |
| /schedule/ | m390 | 155 px |

Oracle failures: 0. invented schedule days: 0.

## Remaining gap

- episode_air_feed missing

## Next

B05 catalog additions truth + home catalog shelf
