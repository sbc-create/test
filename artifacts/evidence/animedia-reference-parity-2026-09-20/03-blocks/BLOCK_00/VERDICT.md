# BLOCK_00 — acceptance contract freeze

## VERDICT

`BLOCK_00_CONTRACT=FROZEN`

```text
ACCEPTANCE_CONTRACT_SHA256=e6aad06dc3f0d633e22bda18eac6b700a321c84e5742e7efffdaedab160ae94c
CONTRACT_MUTATED_AFTER_BASELINE=0
```

## Files

- `REFERENCE_CONTRACT.json`
- `ROUTE_MATRIX.json`
- `REQUIRED_SECTION_GRAPH.json`
- `VISUAL_THRESHOLDS.json`
- `SCREENSHOT_MANIFEST.expected.json`

## Notes

- Problem routes locked for both domains.
- 20 control titles selected via HMAC(seed=`ANIMEDIA-REFERENCE-PARITY-02`, catalog_digest:slug) before any template edits.
- Self-reported visual scores forbidden; oracle thresholds frozen.
- Post-baseline mutation of matrix/thresholds → `NEEDS_REPAIR` / `READY_FOR_OWNER_VISUAL_REVIEW=NO`.
