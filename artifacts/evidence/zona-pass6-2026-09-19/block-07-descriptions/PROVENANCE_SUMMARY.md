# Block 07 — Description provenance summary

Authorized snapshot:
- catalog: `/srv/lords/.frontend/zona-01-catalog.json` count=53524
- details: `/srv/lords/.frontend/zona-01-details.json` details_total=53524

## Counts

| Metric | Value |
| --- | ---: |
| TOTAL_TITLES | 53524 |
| DESCRIPTION_PRESENT_RAW | 0 |
| DESCRIPTION_PRESENT_DETAILS | 40210 |
| DESCRIPTION_PRESENT_AFTER_JOIN | 40210 |
| DESCRIPTION_RENDERED | 40210 |
| COVERAGE % | 75.13 |
| SOURCE_AVAILABLE_NOT_PROJECTED | 0 |
| SOURCE_AVAILABLE_NOT_RENDERED | 0 |
| TRULY_MISSING | 13314 |
| MALFORMED | 0 |
| EXACT_DUPLICATE_GROUPS | 39 |
| NEAR_DUPLICATE_GROUPS | 12 |

## Gate

`SOURCE_AVAILABLE_NOT_RENDERED` (incl. not projected) = **0**

Join remains perfect (Pass5 JOIN_AUDIT). Remaining gaps are empty description fields in the authorized details map → `TRULY_MISSING`, not join/projection bugs — unless `SOURCE_AVAILABLE_NOT_PROJECTED` > 0.

## Reason histogram

```json
{
  "SOURCE_AVAILABLE_PROJECTED": 40210,
  "TRULY_MISSING": 13314
}
```
