# BLOCK_B02 — Weekly popular shelf + Telegram/ad collapse

- stage: ANIMEDIA-BLOCKWISE-PARITY-03
- block_id: B02
- status: PASS_LOCAL_PENDING_LIVE
- CONTRACT_SHA256: `5f2112e25ef974333c388bad405abfae3c3d460a713b028afa3c0e549b8eaeb3`
- CONTRACT_MUTATED: 0
- POPULAR_DATA_GAP: 1 (no approved WeeklyPopularSnapshot on disk)

## Intent

Upper poster shelf «Популярное за неделю» only from approved §5.6 snapshot;
Telegram promo only with real owner URL; empty ad slots 0 px.

## Ownership

core_data (snapshot) + template (render/collapse)

## Source provenance

- Display path: `аниме_load_approved_weekly_popular()` ← `ANIMEDIA_WEEKLY_POPULAR_SNAPSHOT`
  / `config/animedia-weekly-popular.json`
- Required envelope fields frozen in `АНИМЕДИА_WEEKLY_REQUIRED_FIELDS`
- Inventory: `weekly_popular_snapshot: null` → default render = gap
- Legacy `аниме_popular_snapshot()` rating sort kept for unit immutability only;
  `display_approved=false` — **not** used for home HTML

## States

| state | policy |
| --- | --- |
| approved ≥4 valid titles | populated shelf + digest attrs |
| missing / invalid / &lt;4 | 0 px, `data-popular-gap="1"`, POPULAR_DATA_GAP=1 |
| no telegram_url | Telegram strip absent (0 px) |
| ad disabled | `.zad-home` height 0 |

## Geometry (populated)

Exact B02 grid CSS: ≥1600 10-col / gap16; 1280–1599 8; 1024–1279 6; 768–1023 4;
&lt;768 rail 112 / gap12; poster 2:3; caption 44–52; no min-height on shelf.

## AFTER_LOCAL

`03-blocks/B02/AFTER_LOCAL/ORACLE.json` — **failures: 0**
- gap: hero absent, gap attr present, ad collapsed
- populated (fixture snapshot): hero present, digest attrs, no gap

## Tests

```
.venv/bin/python -m pytest tests/unit/test_animedia_parity03_b02.py \
  tests/unit/test_animedia_parity02_block04_home_top.py \
  tests/unit/test_animedia_parity02_block06_home_lower.py -q
# passed
```

## Remaining data gap

- **POPULAR_DATA_GAP=1** until Core publishes approved WeeklyPopularSnapshot
- HOME_CONTENT_PARITY_PASS / REFERENCE_PARITY_PASS remain NO

## Next

B03 true episode feed / compact empty ≤96px (TRUE_PROVIDER_PLAYABLE_EVENT_COUNT=0)
