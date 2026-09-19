# REPORT — Animedia home density + episode pagination

## Preflight
- WORKTREE `/home/claude/wt-animedia-finalization-01`
- BRANCH `claude/animedia-template-finalization-01`
- START_HEAD `f7b40e046a7d659f4b8c3131ca919307442cf7d2` (exact match)
- FINAL_HEAD `9d6df298e1930c519ad6a28d7b19fa1ee0456ad9`

## Root cause
Hard `предел=12` on home and `предел=240` / `per=24` on `/new/`, with no home pager.
Timestamp was raw catalog `published_at` date slice. See `ROOT_CAUSE.md`.

## Fix
- Shared `_эпизод_события()` (latest avail episode per title)
- page_size=10; home = page 1 + pager → `/new/?page=N`
- Human timestamps in Europe/Moscow from catalog publish time
- Namespaced `.ahome-eps` density + tighter `.ahero` shelf
- Invalid pages → HTTP 404

## Live numbers
| Metric | Value |
| --- | ---: |
| SOURCE/ELIGIBLE events | 5495 |
| Pages | 550 |
| Home page1 | 10 |
| page1∩page2 | 0 |
| Latest50 reachable | 50 |
| Desktop rowH | 82 |
| Desktop thumb | {'w': 64, 'h': 82} |
| Desktop rowGap | 16 |
| Mobile rowH | 76 |
| Overflow | 0 / 0 |

## Commits
```
9d6df29 chore(nova): point Animedia provenance at /new/ 404 tip
7cb7c90 fix(animedia): return HTTP 404 for invalid /new/ pages
2eaf1c8 chore(nova): point Animedia provenance at home-pagination 1.2.3 tip
3e66dfd fix(animedia): densify home episode feed with real /new/ pagination
```

## Flags
```text
VERDICT=PASS
BRANCH=claude/animedia-template-finalization-01
START_HEAD=f7b40e046a7d659f4b8c3131ca919307442cf7d2
FINAL_HEAD=9d6df298e1930c519ad6a28d7b19fa1ee0456ad9
COMMITS=4
TESTS=54+ unit (home pagination + prior animedia gates)
LIVE_BUILD_ICU=20260919T201809Z-7cb7c901-nova
LIVE_BUILD_SPACE=20260919T201809Z-7cb7c901-nova
ROLLBACK_PATH=/srv/lords/.frontend/.rollback/pre-closed-update-20260919T201809Z

SOURCE_EVENT_COUNT=5495
ELIGIBLE_EVENT_COUNT=5495
LATEST50_SOURCE_COUNT=50
LATEST50_REACHABLE_COUNT=50
LATEST50_MISSING_COUNT=0
EPISODE_HISTORY_DATA_GAP=0

HOME_FEED_PAGE_SIZE=10
HOME_FEED_PAGE_COUNT=550
HOME_PAGE1_COUNT=10
PAGE1_PAGE2_INTERSECTION=0
PAGINATION_DUPLICATES=0
PAGINATION_MISSING_ITEMS=0
PAGINATION_SORT_VIOLATIONS=0
PAGINATION_REAL_PASS=1

TIMESTAMP_WITH_TIME_COUNT=10
DATE_ONLY_COUNT=0
MISSING_PRECISE_TIME_COUNT=0
INVENTED_TIMESTAMPS=0
TIMESTAMP_SEMANTICS_PASS=1

CONTENT_MAX_WIDTH=1760 (feed .ahome-eps; global wrap still 1704)
DESKTOP_ROW_HEIGHT=82
DESKTOP_ROW_GAP=16
DESKTOP_THUMBNAIL_SIZE={'w': 64, 'h': 82}
MOBILE_ROW_HEIGHT=76
MOBILE_ROW_GAP=12
MOBILE_THUMBNAIL_SIZE={'w': 56, 'h': 76}
TOP_SHELF_ITEM_WIDTH=148
HOME_DENSITY_PASS=1
TOP_SHELF_GEOMETRY_PASS=1
MOBILE_GEOMETRY_PASS=1
HORIZONTAL_OVERFLOW_COUNT=0

EXACT_DUPLICATE_EVENTS=0
EXACT_DUPLICATE_SHELVES=0
EXACT_DUPLICATE_COLLECTIONS=0
DUPLICATE_SECTIONS=0
BROKEN_EVENT_LINKS=0
INVENTED_CONTENT_COUNT=0

PLAYER_GOLDEN_RUNS=2/2 (regression both domains; prior 10/10 contract preserved)
PLAYER_REGRESSION_PASS=1
PLAYER_FALSE_READY=0
PLAYER_FALSE_FAILURE=0
PLAYER_OVERLAY_OVER_PLAYING=0
TITLE_REGRESSION_PASS=1
CATALOG_REGRESSION_PASS=1
CACHE_COHERENCE_PASS=1

CONTACT_DATA_GAP=1
SCHEDULE_DATA_GAP=1

DEPLOY_PERFORMED=1
DEPLOY_SCOPE=animedia.icu,animedia.space
DNS_MUTATIONS=0
INDEXING_OPENED=0
OTHER_DOMAINS_MUTATED=0
PRODUCTION_DB_MIGRATIONS=0
PAID_OPERATIONS=0
PUSH_PERFORMED=0
MERGE_PERFORMED=0
SECRETS_EXPOSED=0

ANIMEDIA_HOME_FEED_CAN_BE_CLOSED=YES
ANIMEDIA_VISUAL_FINALIZATION_CAN_BE_CLOSED=NO
ANIMEDIA_OVERALL_CAN_BE_CLOSED=NO
```
