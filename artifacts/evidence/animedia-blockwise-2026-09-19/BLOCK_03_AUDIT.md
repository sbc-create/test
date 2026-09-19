# BLOCK_03 — episode feed / `/new/`

## Status

`BLOCK_03_PASS` (technical + honest labeling)

Residual data: `EPISODE_EVENT_DATA_GAP=1` (no episode-air timestamps in snapshot).

## Semantics audit

| Question | Answer |
| --- | --- |
| True episode air event? | **No** — 0 rows with episode-level `published_at` in details |
| Episode number source | `details.seasons[].avail` (last season with avail≥1) |
| Timestamp source | `catalog.items[].published_at` |
| Episode ID | synthetic `{title_id}:s{n}e{avail}` |
| Link | `адрес_эпизода` → `/title/{slug}/season-{n}/episode-{ep}/` |
| Time meaning | title/catalog publish — **not** series air clock |

Evidence: `EPISODE_EVENT_SEMANTICS.md`, `raw/PAGINATION_AUDIT.json`.

## Repair

1. Rename UI to **Недавно добавленные**
2. Meta prefix **Добавлено · {time}**
3. Home CTA → `/new/?page=1`
4. `event_kind=catalog_publish` + `АНИМЕДИА_EPISODE_EVENT_DATA_GAP=1`
5. Geometry: 2-col desktop / 1-col mobile; row 76px; thumb 60/56; title ≤2 lines; gap 14px

## Gates (local)

All true — `raw/BLOCK_03_AFTER_LOCAL_GEOMETRY.json`.

```text
EPISODE_FEED_SCORE=96
SOURCE_EVENT_COUNT=5495
TRUE_EPISODE_EVENT_COUNT=0
CATALOG_PUBLISH_EVENT_COUNT=5495
EPISODE_EVENT_DATA_GAP=1
INVENTED_TIMESTAMPS=0
PAGINATION_DUPLICATES=0
PAGINATION_MISSING_ITEMS=0
PAGINATION_SORT_VIOLATIONS=0
LATEST50_REACHABLE_COUNT=50
BEYOND_LAST_HTTP=404
```

Score rationale: geometry + pagination + honesty gates green; −4 for unavoidable data gap (cannot show true episode air feed).
