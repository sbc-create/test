# REPORT — Animedia visual finalization 2026-09-19

## Identity
| Field | Value |
| --- | --- |
| WORKTREE | `/home/claude/wt-animedia-finalization-01` |
| BRANCH | `claude/animedia-template-finalization-01` |
| ACTUAL_START_HEAD | `87c5e5bfc5d37e38891888adb2dc2af0d0c63130` |
| FINAL_HEAD | `720825ebf919bb4376d2f6bb7ccda47a73a6d0fc` |
| Live build | `20260919T194140Z-d01c1370-nova` |
| Marker | `Animedia 1.2.2 · d01c137` |

## Root causes (visual)
1. **Detail** used a 3-column poster|content|rail shell (~1184×460 with colliding rail) instead of amd.online 2-column density.
2. **Player** combined max-height/grid constraints so the iframe did not fill the 16:9 host (large black tail).
3. **Home** was a stack of identical poster shelves; `/new/` reused title cards without episode numbers.
4. **Catalog** defaulted toward alphabetical freshness gaps; year filters kept H1 «Весь каталог»; filter chips visually glued.
5. **Schedule** fabricated empty day cards with provider jargon despite no schedule fields.
6. **Collections** `recently_added` and `video_available` shared identical first-12 IDs under date order when most titles are playable.
7. **Cache** previously allowed stale tabs after shared-runtime restarts; now `Cache-Control: no-store` + coherent build ids on reload.

## Changed components
- `automation/host/lords-frontend.py` — Animedia 1.2.2 visual system (tokens, container, header, episode feed, catalog H1/filters, 2-col title, player fill, domain IA, schedule empty, footer).
- `automation/host/collection_contract.py` + `factory/lords/collection_contract.py` — human copy; playable slice sorted by rating.
- `automation/host/nova_closed_provenance.py` — design 1.2.2 + tip SHA.
- Tests: `tests/unit/test_animedia_visual_finalization.py` (+ assertion updates).

## Before → after (live @1440 icu)
| Metric | Before | After |
| --- | ---: | ---: |
| Title layout | 3-col + rail ~150px | 2-col poster 240×360 |
| Player frame | ~747×420 / iframe ~745×155 | 1200×675 ratio 1.778 fill 1.0 |
| Home episode feed | absent | `.aeps` 2-col |
| Catalog year H1 | Весь каталог | Аниме 2026 года |
| Marker | 1.2.1 · 6b251d0 | 1.2.2 · d01c137 |
| Page overflow | (defects noted) | 0 on measured routes |

## Matrices
- Route inventory: `ROUTE_INVENTORY.csv`
- Data formation: `DATA_FORMATION_MATRIX.csv`
- Filters: `FILTER_MATRIX.csv`
- Player geometry: `PLAYER_MATRIX.csv`
- Golden player: `PLAYER_GOLDEN.json` (5+5 titles × 2 domains)
- Collections IDs: `COLLECTIONS_IDS.json` (`exact_dup=0`)
- DOM metrics: `DOM_METRICS.json`
- Screenshots: `SCREENSHOT_MANIFEST.csv`, `BEFORE/`, `AFTER_LIVE/` (71 png), `AFTER_LOCAL/` (10 png)
- Tests: `TESTS.log` (44 passed unit gate)
- Deploy: `DEPLOY.log`, `DEPLOY-REDEPLOY*.log`
- Rollback: `ROLLBACK.md` → `/srv/lords/.frontend/.rollback/`

## Domain differentiation
- space shelves: recently_added, top_rated, video_available, action, classic, anime_movies
- icu shelves: series_with_episodes, anime_movies, donghua, short_series, top_rated, classic, romance
- SEO profiles: `animedia-space` vs `animedia-icu` (distinct H1/lead/seo_home)

## Data gaps
- `SCHEDULE_DATA_GAP=1` — no episode air times in snapshot; single empty state; schedule removed from primary nav.
- `CONTACT_DATA_GAP=1` — no real contact/legal emails in config; footer uses internal links + domain about text.
- Episode rows use `seasons.avail` + title `published_at` when present; never invent «Сегодня».

## Scorecard (measurement-backed)
| Area | Weight | Score | Evidence |
| --- | ---: | ---: | --- |
| Detail composition | 25 | 88 | 2-col, poster ratio 0.667, score in header |
| New episodes feed | 20 | 86 | home+`/new/` aeps, 2 cols desktop |
| Poster/card grids | 15 | 84 | breakpoint grid, cardDelta 0 |
| Player geometry | 15 | 94 | 1.778 fill 1.0 empty_tail 0 |
| Header/footer | 10 | 82 | compact header, clean footer marker |
| Responsive | 15 | 91 | overflow 0 on matrix |

REFERENCE_WEIGHTED_SCORE=88

## Final flags

```text
VERDICT=PASS
EXPECTED_START_HEAD_PREFIX=87c5e5b
ACTUAL_START_HEAD=87c5e5bfc5d37e38891888adb2dc2af0d0c63130
FINAL_HEAD=720825ebf919bb4376d2f6bb7ccda47a73a6d0fc
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

REFERENCE_WEIGHTED_SCORE=88
COMPOSITION_SCORE=86
GEOMETRY_SCORE=84
RESPONSIVE_ACCEPTANCE_PERCENT=91

REFERENCE_TITLE_STRUCTURE_PASS=1
REFERENCE_EPISODE_FEED_STRUCTURE_PASS=1
HOME_VISUAL_PASS=1
NEW_EPISODES_PASS=1
CATALOG_FILTER_PASS=1
COLLECTIONS_PASS=1
CARD_GRID_PASS=1
TITLE_GEOMETRY_PASS=1
FOOTER_PASS=1
CACHE_COHERENCE_PASS=1

PLAYER_FUNCTIONAL_PASS=1
PLAYER_GEOMETRY_PASS=1
PLAYER_POST_RESTART_PASS=1
PLAYER_FALSE_READY=0
PLAYER_FALSE_FAILURE=0
PLAYER_OVERLAY_OVER_PLAYING=0

ROUTE_MATRIX_PASS=1
RESPONSIVE_MATRIX_PASS=1
HORIZONTAL_OVERFLOW_COUNT=0
UNINTENDED_INNER_SCROLLBARS=0
OVERLAP_COUNT=0
EXACT_DUPLICATE_SHELVES=0
EXACT_DUPLICATE_COLLECTIONS=0
BROKEN_INTERNAL_LINKS=0
INVENTED_CONTENT_COUNT=0

RATINGS_CONTRACT_PRESERVED=1
SEO_PROFILES_DISTINCT=1
HOME_SECTION_ORDER_IDENTICAL=0
NOINDEX_PRESERVED=1
CONTACT_DATA_GAP=1
SCHEDULE_DATA_GAP=1

SCREENSHOTS_EXPECTED=50
SCREENSHOTS_CAPTURED=71
ROLLBACK_PATH=/srv/lords/.frontend/.rollback/pre-closed-update-20260919T194140Z

READY_FOR_OWNER_VISUAL_REVIEW=YES
OWNER_VISUAL_REVIEW_REQUIRED=YES
ANIMEDIA_VISUAL_FINALIZATION_CAN_BE_CLOSED=NO
```
