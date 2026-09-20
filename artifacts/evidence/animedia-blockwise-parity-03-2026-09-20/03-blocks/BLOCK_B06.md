# BLOCK_B06 — Remaining home modules

- stage: ANIMEDIA-BLOCKWISE-PARITY-03
- block_id: B06
- status: PASS_LOCAL_PENDING_LIVE
- CONTRACT_SHA256: `5f2112e25ef974333c388bad405abfae3c3d460a713b028afa3c0e549b8eaeb3`
- CONTRACT_MUTATED: 0

## Intent

Finish home composition after B02–B05: compact filters, Top‑100 from approved
TopSnapshot only, at most two large catalog shelves, real collections shelf,
no invented news/comments, SEO/about after functional modules.

## Ownership

- Top-100 snapshot: core_data (`TOP100_DATA_GAP` when absent)
- Filters / SEO order / shelf cap: template
- Editorial/comments: absent_from_registry → hidden

## AFTER_LOCAL

| mode | viewport | filters h | top100 | catalog shelves |
| --- | --- | --- | --- | --- |
| gap | d1440 | 40 | 0 hidden | 2 |
| gap | t768 | 56 | 0 hidden | 2 |
| gap | m390 | 48 | 0 hidden | 2 |
| populated | d1440 | 40 | 365 | 2 |

Oracle failures: 0. Editorial/comments invented: 0. SEO after filters: yes.

## Remaining gap

- production TopSnapshot absent → `TOP100_DATA_GAP=1`
- standalone `/top/` still `absent_from_registry_until_core` (B12)

## Next

B07 title passport
