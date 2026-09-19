# EPISODE_EVENT_SEMANTICS

## Finding

| Field | Value |
| --- | --- |
| EPISODE_EVENT_DATA_GAP | 1 |
| TRUE_EPISODE_EVENT_COUNT | 0 |
| CATALOG_PUBLISH_EVENT_COUNT | 5495 |
| SOURCE_EVENT_COUNT | 5495 |
| TIMESTAMP_FIELD | catalog.items[].published_at |
| TIMESTAMP_SEMANTICS | title/catalog publish ISO datetime; **not** episodic air time |
| EPISODE_NUMBER_SOURCE | details.seasons[].avail (latest season with avail≥1) |
| EPISODE_ID | `{title_id}:s{season}e{episode}` synthetic from avail |
| LINK | `/title/{slug}/season-{n}/episode-{ep}/` via `адрес_эпизода` |

## UI honesty

- Section title: **Недавно добавленные** (not «Новые серии» as air claim)
- Row meta: **Добавлено · {formatted catalog time}**
- Gap flag: `АНИМЕДИА_EPISODE_EVENT_DATA_GAP=1`

Episode air feed cannot be fabricated from this snapshot.
