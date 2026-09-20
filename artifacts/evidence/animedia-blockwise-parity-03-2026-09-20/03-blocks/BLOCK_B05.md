# BLOCK_B05 — Catalog additions truth + home shelf

- stage: ANIMEDIA-BLOCKWISE-PARITY-03
- block_id: B05
- status: PASS_LOCAL_PENDING_LIVE
- CONTRACT_SHA256: `5f2112e25ef974333c388bad405abfae3c3d460a713b028afa3c0e549b8eaeb3`
- CONTRACT_MUTATED: 0

## Intent

«Новое в каталоге» is a separate catalog-addition shelf, not an episode feed.
Only a verified domain `catalog_added_at` ledger may populate it. Ambiguous
`catalog.items[].published_at` is never treated as add time. Available episode
totals are labeled `Доступно N серий`, never `N серия`.

## Ownership

core_data (ledger). Template renders approved events or honest 0 px / empty.

## Passport

| Field | Value |
| --- | --- |
| routes | `/` (home shelf), `/new/` |
| source | `ANIMEDIA_CATALOG_ADDED_LEDGER` → `catalog_added_at` |
| forbidden clocks | `published_at`, `imported_at`, `ingested_at`, build/mtime, `updated_at` |
| card | poster · title · type · year · `Добавлено …` · `Доступно N серий` |
| grid | 8 / 6 / 5 / 4 / 2 (≥1600 / 1280 / 1024 / 768 / mobile) |
| gap home | 0 px + `CATALOG_FRESHNESS_DATA_GAP=1` |
| gap `/new/` | compact honest panel |

## AFTER_LOCAL

| mode | page | viewport | h | cards | episode rows |
| --- | --- | --- | --- | --- | --- |
| gap | home | d1440/t768/m390 | 0 (hidden) | 0 | 0 |
| gap | /new/ | d1440 | 140 | 0 | 0 |
| gap | /new/ | t768 | 133 | 0 | 0 |
| gap | /new/ | m390 | 160 | 0 | 0 |
| populated | home | d1440 | 365 | 3 | 0 |
| populated | home | m390 | 697 | 3 | 0 |
| populated | /new/ | d1440 | 401 | 3 | 0 |

Oracle failures: 0. Screenshots: light+dark × 1440/768/390 for gap and populated.

## Tests

- `tests/unit/test_animedia_parity03_b05.py`
- updated `test_animedia_home_pagination.py`, `test_animedia_parity02_block05_events.py`,
  `test_animedia_visual_finalization.py`, `test_animedia_block_04_home_shelves.py`

## Remaining gap

- production `catalog_added` ledger absent → `CATALOG_FRESHNESS_DATA_GAP=1`
- `HOME_CONTENT_PARITY_PASS=NO` until ledger exists
- owner: `core_data` → `BLOCKED_DEPENDENCY(owner=core_data)` for live parity

## Next

B06 remaining home blocks (filters, Top-100 shelf, collections, SEO order)
