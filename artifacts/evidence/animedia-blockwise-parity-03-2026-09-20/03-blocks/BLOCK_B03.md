# BLOCK_B03 — True episode feed / compact empty

- stage: ANIMEDIA-BLOCKWISE-PARITY-03
- block_id: B03
- status: PASS_LOCAL_PENDING_LIVE
- CONTRACT_SHA256: `5f2112e25ef974333c388bad405abfae3c3d460a713b028afa3c0e549b8eaeb3`
- CONTRACT_MUTATED: 0
- TRUE_PROVIDER_PLAYABLE_EVENT_COUNT: 0
- EPISODE_EVENT_FALLBACK_TO_CATALOG_COUNT: 0

## Intent

Home «Новые серии аниме» from `provider_became_playable` only. With no ledger:
heading + empty panel ≤96 px; catalog must not backfill the feed.

## Ownership

core_data (ledger) + template (empty contract)

## Source provenance

- Display: `_provider_playable_events()` ← `ANIMEDIA_PROVIDER_PLAYABLE_EVENTS`
- Inventory: `TRUE_PROVIDER_PLAYABLE_EVENT_COUNT=0`, ledger null
- Legacy `_эпизод_события()` remains catalog_publish for `/new/` until B12;
  home B03 never calls it

## Empty contract (measured AFTER_LOCAL)

| viewport | block height |
| --- | --- |
| d1440 | 67 px |
| t768 | 67 px |
| m390 | 84 px |

All ≤96. Oracle failures: 0. Copy:
«Лента новых серий пока недоступна: источник событий ещё не подключён»

## Tests

58 related unit tests passed (b00–b03 + regressions).

## Remaining data gap

- Provider playable event ledger required for populated B03
- HOME_CONTENT_PARITY_PASS remains NO

## Next

B04 schedule / honest empty
