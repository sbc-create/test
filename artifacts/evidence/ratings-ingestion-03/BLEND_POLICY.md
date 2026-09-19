# Blend policy — Stage 3

## Version retained

```text
BLEND_POLICY_VERSION=animedia_blend_v1
```

Stage 2 formula is versioned and covered by unit tests (`test_formula_examples`).
Stage 3 **keeps** it; does not introduce a parallel `site_rating_blend_v1`.

## Formula

```text
AMD_BASELINE_PRIOR_CAP=100
MISSING_VOTE_COUNT_PRIOR_WEIGHT=25
MIN_PUBLIC_LOCAL_VOTES_WITHOUT_BASELINE=5

baseline_weight = min(amd_vote_count, 100)   # vote_count > 0
baseline_weight = 25                         # score present, vote_count null

combined_raw = (amd_score * baseline_weight + local_sum)
             / (baseline_weight + local_count)
```

Properties:

- `local_count=0` → combined equals AMD score
- Shikimori never enters the formula
- Missing rating → `null` UI `Нет оценки` (never `0`)
- AMD score remains separately readable in gateway `ratingSources`
- Provenance stores `formula_version` + inputs on `rating_combined_projection`

## Rotation

```text
animedia_rotation_v1
```

Deterministic sort by combined score + `canonical_title_id` tie-break.
Does not reshuffle randomly on page refresh.
