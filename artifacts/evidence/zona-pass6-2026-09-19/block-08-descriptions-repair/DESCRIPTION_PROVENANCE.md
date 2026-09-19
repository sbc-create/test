# Block 08 — Description repair

## Finding
Independent Block 07 oracle proved:

- `SOURCE_AVAILABLE_NOT_RENDERED=0`
- `SOURCE_AVAILABLE_NOT_PROJECTED=0`
- Join perfect (53524/53524)
- Coverage 75.13% (40210/53524)
- Remaining **13314** are `TRULY_MISSING` in the authorized details snapshot

## Automatic repairs performed
None required. No join/projection/normalization bug remaining.

Forbidden actions avoided: no invented plots, no external scrape, no LLM fill, no generic SEO template.

## After metrics
| Metric | Before | After |
| --- | ---: | ---: |
| DESCRIPTION_COVERAGE | 75.13 | 75.13 |
| SOURCE_AVAILABLE_NOT_RENDERED | 0 | 0 |
| INVENTED_DESCRIPTIONS | 0 | 0 |
| WRONG_TITLE_DESCRIPTION_COUNT | 0 | 0 |
| UNEXPLAINED_EXACT_DUPLICATE_GROUPS | 0 | 0 |

## Backlog
`DESCRIPTION_BACKLOG.csv` — 13314 titles for a separate content pipeline.

Buckets: {'new_titles': 2521, 'titles_with_playback': 10683, 'high_rating_titles': 12, 'ongoing': 7, 'remaining_tail': 91}

```text
DESCRIPTION_PIPELINE_PASS=YES
DESCRIPTION_SOURCE_DATA_GAP=YES
ZONA_SEO_CONTENT_CAN_BE_CLOSED=NO
SOURCE_CONTENT_BACKLOG_REQUIRED=YES
```
