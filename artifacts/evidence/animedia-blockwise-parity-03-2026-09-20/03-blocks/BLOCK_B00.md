# BLOCK_B00 — Acceptance / provenance freeze

- stage: ANIMEDIA-BLOCKWISE-PARITY-03
- block_id: B00
- status: PASS_LOCAL_PENDING_LIVE
- frozen_at: 2026-09-20T11:22:04Z
- branch: `claude/animedia-template-finalization-01`
- start_head: `242a834f580ded6dca42972c36c3e1454836c852`
- CONTRACT_SHA256: `5f2112e25ef974333c388bad405abfae3c3d460a713b028afa3c0e549b8eaeb3`
- CONTRACT_MUTATED: 0
- REFERENCE_BASELINE_DIGEST: `84132b93f8fa8f61b5e60ab87b82044e30209b4d7db3e505b00d70cb117f5632`
- REFERENCE_BASELINE_VALID: 1
- PASSPORT_MANIFEST_VALID: 1
- DISPLAY_POLICIES_FROZEN: 1
- REFERENCE_ACCESS_FAILURES: 0
- LOCAL_EXPECTED_CASE_COUNT: 114
- LIVE_EXPECTED_CASE_COUNT: 84
- ROUTE_FAMILIES_DISCOVERED: 9
- ROUTE_FAMILIES_MAPPED: 9
- UNMAPPED_ROUTE_FAMILIES: 0

## Intent

Freeze ANIMEDIA_BLOCK_SPEC_V1 as immutable acceptance contract. No template layout
changes in this block.

## Ownership

control/gate — template must not mutate freeze after digest without owner-approved revision.

## Source provenance (summary)

From `00-contract/DATA_PROVENANCE_INVENTORY.json`:
- catalog_count=7425
- published_at_semantic=AMBIGUOUS
- TRUE_PROVIDER_PLAYABLE_EVENT_COUNT=0
- TRUE_EPISODE_RELEASE_EVENT_COUNT=0
- CATALOG_ADDED_EVENT_COUNT=0
- weekly_popular_snapshot / recommendation_snapshot / top100_snapshot / episode_air_feed = null

## Reference baseline

9/9 captures ok (home/collections/title × 1440/768/390) under `01-reference-baseline/`.

## Manifests

- LOCAL cases: 114
- LIVE cases: 84
- Expected counts frozen in SCREENSHOT_MANIFEST.expected.json — not assigned from later captures.

## Geometry tolerances (locked)

See `00-contract/GEOMETRY_TOLERANCES.json`. Expanding after BEFORE forbidden.

## Independent gates

```
REFERENCE_BASELINE_VALID=1
PASSPORT_MANIFEST_VALID=1
DISPLAY_POLICIES_FROZEN=1
```

## Remaining data gaps

- B03: TRUE_PROVIDER_PLAYABLE_EVENT_COUNT=0 → compact empty ≤96px
- B04/B13: episode_air_feed missing
- B05/B12: catalog_added ledger missing → CATALOG_FRESHNESS_DATA_GAP
- B02/B06.1/B10: snapshots missing → 0px + gap flags
- published_at must not be labeled as Добавлено / Вышла серия

## Next

B01 shared shell — only while CONTRACT_SHA256 remains `5f2112e25ef974333c388bad405abfae3c3d460a713b028afa3c0e549b8eaeb3`.
