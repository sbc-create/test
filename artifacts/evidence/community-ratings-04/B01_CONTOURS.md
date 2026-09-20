# Contour isolation — COMMUNITY-RATINGS-04

## Branch

```text
SOURCE_POLICY_BRANCH=NATIVE_ONLY_SAFE_FALLBACK
YUMMY_SOURCE_POLICY_PASS=0
SOURCE_POLICY_DIGEST=bde8c5c66b28f1b1fd1ae19c36a4ceec18eea4944dec1c18f1dbed8cdd0845aa
```

## Contours (independent)

| Contour | Depends on Shikimori public display? | Stage04 |
| --- | --- | --- |
| YUMMY_NATIVE_VOTE_LEDGER | **No** | Supervised canary allowed |
| YUMMY_EXTERNAL_PRIOR | Yes (for public emission) | Internal calc OK; public OPEN blocked |
| YUMMY_PUBLIC_RATING_DISPLAY | Yes | Badges/derived hidden |
| YUMMY_STRUCTURED_DATA | Yes | aggregateRating=0 |

## Prior weights (frozen)

```text
YUMMY_PRIOR_WEIGHT_ANIMEDIA_NATIVE=0.70
YUMMY_PRIOR_WEIGHT_SHIKIMORI=0.30
SOURCE_LINEAGE_DOUBLE_COUNT_COUNT=0
SHIKIMORI_INDIRECT_DOUBLE_COUNT_COUNT=0
PRIOR_COMPONENTS_INDEPENDENT=1
animedia_projected_rejected=True
```

Owner canary authorization does **not** expand Shikimori onto open-index Yummy.
