# CATALOG_COUNT_RECONCILIATION — Zona Pass 5

## Snapshot

| Layer | Count |
| --- | ---: |
| L0 catalog items | 53524 |
| Declared catalog.count | 53524 |
| Unique slugs | 53524 |
| Duplicate slugs | 0 |
| Details map size | 53524 |
| Missing details | 0 |
| Orphan details | 0 |
| Valid year | 50782 |
| Missing year | 2742 |
| Invalid year | 0 |

Equation `valid+missing+invalid == applicable`: **True**
(`50782+2742+0=53524`)

## Baseline delta

EXPECTED_PREVIOUS_CATALOG_COUNT=53524
CURRENT=53524
DELTA=0
CATALOG_COUNT_RECONCILED=YES

## Suspicious years (catalog.year oracle)

| Year | Total | Films | Series | Animation |
| --- | ---: | ---: | ---: | ---: |
| 2003 | 468 | 333 | 86 | 49 |
| 2010 | 1089 | 784 | 229 | 76 |
| 2013 | 1521 | 1090 | 307 | 124 |
| 2018 | 2098 | 1126 | 759 | 213 |
| 2019 | 2144 | 1100 | 825 | 219 |
| 2026 | 2187 | 1067 | 1030 | 90 |

Live route totals (from before_state) already show hundreds of titles for these
years on `/catalog/?year=` — owner report of ~7 for 2019 is **not** matching the
authoritative catalog. Likely UI facet truncation or looking at a narrow filter.
Pass 5 must prove facet counts equal oracle totals.
