# BLOCK_B07 — Title passport

- stage: ANIMEDIA-BLOCKWISE-PARITY-03
- block_id: B07
- status: PASS_LOCAL_PENDING_LIVE
- CONTRACT_SHA256: `5f2112e25ef974333c388bad405abfae3c3d460a713b028afa3c0e549b8eaeb3`
- CONTRACT_MUTATED: 0

## Intent

Title hero: poster 240×360, text column, ratings column 150–180 px, padding
28–32. Verified description in SSR; true gap = one compact line. Independent
source ratings (Shikimori/KP/IMDb); missing ≠ 0. Player status beside player
heading. Hero→player gap ≤24 px.

## AFTER_LOCAL

| mode | viewport | gap h | desc | rail | status near |
| --- | --- | --- | --- | --- | --- |
| desc-full | d1440 | 20 | present | yes | yes |
| desc-full | t768/m390 | 16 | present | no (stacked) | yes |
| desc-gap | d1440 | 20 | gap | yes | yes |

Oracle failures: 0.

## Next

B08 player shell geometry + episode list
