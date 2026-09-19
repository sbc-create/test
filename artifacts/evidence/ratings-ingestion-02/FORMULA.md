# Formula animedia_blend_v1

```text
AMD_BASELINE_PRIOR_CAP=100
MISSING_VOTE_COUNT_PRIOR_WEIGHT=25
MIN_PUBLIC_LOCAL_VOTES_WITHOUT_BASELINE=5
```

```text
baseline_weight = min(amd_vote_count, 100)   # if vote_count > 0
baseline_weight = 25                         # if score present, vote_count null (flag VOTE_COUNT_MISSING)

combined_raw = (amd_score * baseline_weight + local_sum)
             / (baseline_weight + local_count)
```

- Decimal math; UI rounds half-up to 2 places
- Shikimori never enters this formula
- Components story/art/characters/voice do not enter combined_score
- Original amd_vote_count stored/shown separately from baseline_weight

Acceptance examples covered by `tests/unit/ratings/test_ratings_stage2.py::test_formula_examples`.
