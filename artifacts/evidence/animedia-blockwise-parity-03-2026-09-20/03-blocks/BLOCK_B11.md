# BLOCK_B11 — Catalog

- stage: ANIMEDIA-BLOCKWISE-PARITY-03
- block_id: B11
- status: PASS_LOCAL_PENDING_LIVE
- CONTRACT_SHA256: `5f2112e25ef974333c388bad405abfae3c3d460a713b028afa3c0e549b8eaeb3`
- CONTRACT_MUTATED: 0

## Repair

1. Catalog grid forced to 2/4/6 (not home 7/10).
2. `/catalog/{facet}/` resolves year|type|genre.
3. Dedupe by canonical_title_id/slug in `отбор`.
4. Compact filters: closed max 112px; open panels not clipped.
5. data-b11 markers for H1/count/empty.

## AFTER_LOCAL

pytest tests/unit/test_animedia_parity03_b11.py — 9 passed.

## Next

B12 search + /new/
