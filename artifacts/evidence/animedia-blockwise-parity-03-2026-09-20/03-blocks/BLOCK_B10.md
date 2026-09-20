# BLOCK_B10 — Recommendations

- stage: ANIMEDIA-BLOCKWISE-PARITY-03
- block_id: B10
- status: PASS_LOCAL_PENDING_LIVE
- CONTRACT_SHA256: `5f2112e25ef974333c388bad405abfae3c3d460a713b028afa3c0e549b8eaeb3`
- CONTRACT_MUTATED: 0
- OWNER_DECISION_ID: ANIMEDIA-B10-B16-20260920-01

## Intent

Related shelf from approved RecommendationSnapshot only; else DETERMINISTIC_METADATA_RELATED_V1; else 0px.

## Repair

1. Title fixed to «Похожее аниме» (not personalization / Top-100 / Смотрите также).
2. Approved snapshot loader (`config/animedia-recommendations.json`).
3. Deterministic metadata fallback: same type, ≥1 shared genre, canonical route, prefer playable; sort playable/shared/year/slug.
4. Hide shelf when &lt;4 valid candidates (`data-rec-state=empty`, 0px CSS).
5. Grid 2/4/6; provenance attrs digest/algorithm/source.

## AFTER_LOCAL

`pytest tests/unit/test_animedia_parity03_b10.py` — 8 passed.

## Declared data gaps

RECOMMENDATIONS_DATA_GAP=1 (no approved RecommendationSnapshot file).

## Next

B11 catalog routes/cards/pagination/filters
