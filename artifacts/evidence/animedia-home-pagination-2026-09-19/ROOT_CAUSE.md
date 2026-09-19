# ROOT_CAUSE — truncated home episode feed

## Preflight
- WORKTREE `/home/claude/wt-animedia-finalization-01`
- BRANCH `claude/animedia-template-finalization-01`
- START_HEAD `f7b40e046a7d659f4b8c3131ca919307442cf7d2` (exact match)

## Where the feed is built
`ВидАнимедиа._эпизод_ряды` in `automation/host/lords-frontend.py`.

Home calls `_эпизод_ряды(предел=12)`. `/new/` calls `_эпизод_ряды(предел=240)` with `per=24`.

## Snapshot facts (animedia-01)
| Metric | Value |
| --- | ---: |
| Catalog titles | 7425 |
| Titles with seasons | 5504 |
| Titles with avail≥1 (current last-ep model) | 5483 |
| Sum of all avail slots (if expanded 1..N) | 118610 |
| Per-episode air timestamps in sidecar | **0** (seasons only have `n/eps/avail`) |

## Pre-fix counters
```text
SOURCE_EVENT_COUNT=5483
ELIGIBLE_EVENT_COUNT=5483
CURRENTLY_RENDERED_COUNT=12   # home
CURRENTLY_UNREACHABLE_COUNT=5471  # home
CURRENT_LIMIT_SOURCE=_эпизод_ряды(предел=12) on home; предел=240 + page_size=24 on /new/
TIMESTAMP_FIELD_CURRENTLY_USED=catalog.items[].published_at
TIMESTAMP_SEMANTICS=title/catalog publish time in snapshot (ISO datetime). NOT episode air time. No episode-level available_at/published_at exists in details.seasons.
```

## Why remaining events were unreachable
Hard slice on home (12) and artificial cap on `/new/` (240) with no pagination UI on home linking into the archive.

## Honest event model chosen
One announcement per title = latest available episode `(season.n, season.avail)` from the last season with `avail≥1`.
Dedupe key `(title_id, season, episode, source_episode_id)`.
Sort `published_at DESC, source_episode_id DESC, event_id DESC`.
Do **not** expand `1..avail` as separate historical events — that would invent distinct release times.
