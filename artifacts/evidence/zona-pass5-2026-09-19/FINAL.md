# FINAL — Zona Pass 5 (2026-09-19)

## Verdict

```text
IMPLEMENTATION_VERDICT=PASS
OVERALL_VERDICT=NEEDS_OWNER_CONFIG
STAGE=ZONA-PASS5-OVERNIGHT
```

Technical densify/data/facet gates are green on two consecutive stable live runs.
Overall close blocked by missing owner contacts/legal and SEO description backlog.

## Lineage

| Field | Value |
| --- | --- |
| START_HEAD | `3c5a14d53d27eed13f2a7db6f6db9440f1f72ef9` |
| CODE_HEAD | `0fc98e2ee6e08ae48ad56e7ac9398d5d5a0d2e7b` |
| LIVE_BUILD | `20260919T215728Z-0fc98e2e-nova` |
| Pass4 live was `c624bebc` | evidence commit `3c5a14d` did not change runtime; Pass5 redeployed `0fc98e2e` |

## Oracle vs UI (suspicious years)

| Year | Oracle | UI `/catalog/?year=` | Match |
| --- | ---: | ---: | --- |
| 2003 | 468 | 468 | YES |
| 2010 | 1089 | 1089 | YES |
| 2013 | 1521 | 1521 | YES |
| 2018 | 2098 | 2098 | YES |
| 2019 | 2144 | 2144 | YES |
| 2026 | 2187 | 2187 | YES |

Owner “~7 in 2019” is **not** present in the authoritative snapshot (`SOURCE_DATA_GAP=NO`).
Root cause for weak year UX: facet `[:24]` truncate (removed); facets now kind-scoped with counts (92 movie years).

## Densify

| Viewport | Columns | Card width |
| --- | ---: | ---: |
| 1920 | 8 | 176 |
| 1440 | 7 | 175 |
| 768 | 4 | 158 |
| 390 | 2 | 164 |

Poster height @1440 = 260px (≤270). PAGE_SIZE=28.

## Player

`PLAYER_GOLDEN_RUNS=10/10` on build `0fc98e2e`.

## Close flags

```text
ZONA_PLAYER_CAN_BE_CLOSED=YES
ZONA_DATA_FACETS_CAN_BE_CLOSED=YES
ZONA_YEAR_DATE_FILTERS_CAN_BE_CLOSED=YES
ZONA_PAGINATION_CAN_BE_CLOSED=YES
ZONA_COLLECTIONS_CAN_BE_CLOSED=YES
ZONA_VISUAL_TEMPLATE_CAN_BE_CLOSED=YES
ZONA_FOOTER_TEMPLATE_CAN_BE_CLOSED=NO
ZONA_TEMPLATE_TECHNICAL_CAN_BE_CLOSED=YES
ZONA_SEO_CONTENT_CAN_BE_CLOSED=NO
ZONA_OVERALL_CAN_BE_CLOSED=NO
OWNER_VISUAL_REVIEW_REQUIRED=YES
```
