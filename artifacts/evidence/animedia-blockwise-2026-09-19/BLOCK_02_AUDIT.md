# BLOCK_02 — top shelf (`.ahero`)

## Status

`BLOCK_02_PASS`

## Reference vs current (measurements)

| Metric | Reference (amd.online) | Local after | Live before (ICU/SPACE) |
| --- | --- | --- | --- |
| Poster width | ~153px | **152px** uniform | 152px (1.2.4 memory) |
| Poster height | ~214px | **214px** | 214px |
| Shelf height | compact hero band | **280.5px** (≤300) | ~280px |
| Gap | ~12–14 | **13px** | 13 |
| Title lines | ≤2 | **≤2** | ≤2 |
| Last-card stretch | none | **none** | none |
| Scrollbar | hidden | **scrollbar-width:none** | none |
| Visible @1363 | ~8 | **8** | ~8 |
| Mobile poster @390 | compact | **112×158**, shelf 220.5 | similar |

Evidence: `raw/BLOCK_02_BEFORE_GEOMETRY.json`, `raw/BLOCK_02_AFTER_LOCAL_GEOMETRY.json`, `screenshots/block-02/`.

## Defects found

1. Flex children could theoretically grow if track alignment changed — fortified with `min-width` + `.zt{width:152px;flex:0 0 auto}`.
2. Hover-only nav arrows (by design ≥1024) — verified with hover + click + native `scrollLeft`.

## Repair

Only `.ahero` CSS fortification in `lords-frontend.py` (no other blocks touched).

## Gates (local after)

All true — see `BLOCK_02_AFTER_LOCAL_GEOMETRY.json` → `gates`.

```text
TOP_SHELF_SCORE=96
```

Rationale: poster at upper bound of 140–152 (matches reference ~153); shelf 280.5 ≤300 and ≪ half viewport; uniform widths; no stretch; meta hidden; controls work. Deduct 4 for ceiling width (not mid-range 146) and residual visual density vs reference crop.

## Tests

`tests/unit/test_animedia_block_02_top_shelf.py` + visual_finalization (13 passed).

## Domains

Local uses ICU catalog snapshot. Geometry contract is shared CSS for both domains; live ICU/SPACE before shots captured in `screenshots/block-02/live_*`.
