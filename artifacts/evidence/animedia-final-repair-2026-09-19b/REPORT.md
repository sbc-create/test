# Animedia final repair report — 2026-09-19b

## Verdict

Root cause of live «Плеер не поднялся / Провайдер не отдал источник» over a live iframe: CSS `display:grid` on `[data-player-state]` overrode the HTML `hidden` attribute, so the error overlay stayed painted. Fixed with `[hidden]{display:none !important}`, explicit `style.display` in JS, empty SSR overlay, and no undocumented provider `error` listener. Homepage density (1280 / hero 154px), icu≠space SEO, Shikimori snapshot ratings, healthz digests, and Playwright golden gates are green on both domains.

## Git

| Field | Value |
| --- | --- |
| START_HEAD | `87eaae17dbc0ab648d4af1692afc94f92d5f0e8b` |
| FINAL_HEAD | `a995dba` / runtime tip `6b251d02dda96545341bf2daad7fb44e46d94484` |
| Branch | `claude/animedia-template-finalization-01` |
| Worktree | `/home/claude/wt-animedia-finalization-01` |

### Key commits

- `ff4bb0f` false-failure client + density + domain SEO + healthz digests
- `7531d83` honor `hidden` over `display:grid` on player overlay
- `6b251d0` empty SSR overlay until real failure
- evidence + golden/visual gates commits

## Deploy

| Field | Value |
| --- | --- |
| Live build | `20260919T180543Z` family → final apply `deploy-final.log` with source/runtime `6b251d02dda9` |
| Rollback | `/srv/lords/.frontend/.rollback/pre-closed-update-20260919T170618Z` (+ later pre-closed dirs from re-applies) |
| Scope | animedia.icu + animedia.space only |
| Path | `APPLY_SITES=animedia-01,animedia-02` → `apply-nova-closed-update.py` |

## Digests (`/healthz` process-truth)

runtime/assets SHA match artifact; catalog/details/provider/ratings digests present; `runtime_digest_match=true`; catalog_revision == details_revision.

## Golden browser gate

Chromium/Playwright. Evidence: provider playlist/video resource timing + shell `active` + **computed** overlay not painted. Cross-origin `currentTime` not readable.

| Metric | Value |
| --- | --- |
| GOLDEN_PLAY_TOTAL | 10 |
| GOLDEN_PLAY_PASS | 10 |
| Unavailable | 2/2 |
| PRIMARY_TO_FALLBACK_PLAY_PASS | 1 |
| GOLDEN_PLAY_POST_RESTART_PASS | 1 |
| GOLDEN_PLAY_PUBLIC_PASS | 1 |
| PLAYER_FALSE_READY | 0 |
| PLAYER_FALSE_FAILURE | 0 (incl. painted-overlay check) |

## Visual

50 screenshots; HOME_MAX_CONTENT_WIDTH_PX=1280; HERO_CARD_WIDTH_PX=154; HORIZONTAL_PAGE_OVERFLOW_PX=0; SAME_SEO_TEXT_BETWEEN_DOMAINS=0; SAME_FIRST_VIEWPORT_CONTENT=0.

## Ratings

Shikimori ENABLED from details snapshot. Unresolved UNVERIFIED/DISABLED: **Шикимуни**, **Nisa Media**.

## Flags

```
START_HEAD=87eaae17dbc0ab648d4af1692afc94f92d5f0e8b
FINAL_HEAD=a995dba
VERDICT=PASS
DEPLOY_PERFORMED=1
DEPLOY_SCOPE=animedia.icu+animedia.space
DNS_MUTATIONS=0
INDEXING_OPENED=0
ACCESS_OPENED=0
OTHER_DOMAINS_MUTATED=0
PAID_OPERATIONS=0
PUSH_PERFORMED=0
MERGE_PERFORMED=0
SECRETS_EXPOSED=0
RUNTIME_DIGEST_MATCH=1
CATALOG_DETAILS_MISSING=0
TITLE_ID_MISMATCH=0
PROVIDER_PROJECTION_SKEW=0
ZERO_CANDIDATES_WHERE_DETAILS_HAVE_SOURCE=0
GOLDEN_PLAY_TOTAL=10
GOLDEN_PLAY_PASS=10
GOLDEN_PLAY_POST_RESTART_PASS=1
GOLDEN_PLAY_PUBLIC_PASS=1
PRIMARY_TO_FALLBACK_PLAY_PASS=1
PLAYER_FALSE_READY=0
PLAYER_FALSE_FAILURE=0
RATINGS_SNAPSHOT_DIGEST_MATCH=1
RATINGS_PERSIST_AFTER_DEPLOY=1
INVENTED_RATINGS=0
WRONG_ID_MATCHES=0
EXACT_DUPLICATE_SHELVES=0
FULL_DESCRIPTIONS_ON_HOME_CARDS=0
SAME_SEO_TEXT_BETWEEN_DOMAINS=0
HORIZONTAL_PAGE_OVERFLOW_PX=0
SCREENSHOTS_CAPTURED=1
ANIMEDIA_FOLLOWUP_CAN_BE_CLOSED=YES
```

Unresolved rating source names: Шикимуни; Nisa Media.

Full artifacts: `artifacts/evidence/animedia-final-repair-2026-09-19b/`, `artifacts/evidence/animedia-playback-gate-2026-09-19/`.
