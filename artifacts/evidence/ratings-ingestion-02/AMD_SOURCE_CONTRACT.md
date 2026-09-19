# AMD.online source contract

**source_key:** `amd_online`  
**canonical origin:** `https://amd.online/`  
**parser_version:** `amd_online_html/1.0.0`

## Allowed pages

Only public detail URLs:

```text
https://amd.online/{numeric-id}-{slug}.html
```

## Confirmed selectors (probe 2026-09-19)

| Field | Selector / rule |
| --- | --- |
| source_id | URL numeric id AND `data-id` on multirating block (must match) |
| title_ru | `h1` |
| title_original | `.amd-sub` |
| score | `.multirating-itog-rateval` (published value; not recomputed) |
| vote_count | `.multirating-itog-votes` (digits only; `(186)` → 186) |
| story | `data-area="story"` |
| characters | `data-area="actors"` |
| art | `data-area="graph"` |
| voice | `data-area="sound"` |

## Validation

- `1 <= score <= 10` else reject
- `vote_count >= 0` or null
- URL id must equal `data-id`
- missing score → `score=null` (never 0)
- no proven `rating_updated_at` → store `fetched_at_utc` + digest only
- sitemap lastmod = advisory only

## Auto-stop

403, 429, CAPTCHA/DDOS challenge, unexpected redirect, robots digest change,
parser drift → circuit open. No proxy rotation / IP bypass.

## Permission

See `AMD_PERMISSION_STATUS.md`. Bulk ingestion blocked until GRANTED.
