# Zona PASS3 — 2026-09-19

## Verdict (honest)

Previous `ZONA_PASS2_CAN_BE_CLOSED=YES` is **cancelled**.

Player P0 (false UNAVAILABLE overlay over playing video) is fixed and proven
live. Template density/layout gates pass visually. Footer legal/contact config
is still missing (`FOOTER_GATE=FAIL`). SEO description coverage remains 75.13%.

```
VERDICT=NEEDS_REPAIR
ZONA_PLAYER_CAN_BE_CLOSED=YES
ZONA_TEMPLATE_CAN_BE_CLOSED=NO
ZONA_SEO_CONTENT_CAN_BE_CLOSED=NO
ZONA_OVERALL_CAN_BE_CLOSED=NO
```

## 0. Preflight

| Field | Value |
| --- | --- |
| pwd | `/home/claude/wt-zona-finalization-01` |
| branch | `claude/zona-template-finalization-01` |
| START_HEAD | `f521f2189a43b8de61a00e9a63a224b281fe7592` |
| FINAL_HEAD | `ac925674fb47aa9124ae7ef2a727e7af6d13e0f7` |
| live before | `20260919T160708Z-06a8250d-nova` (PASS2) |
| live after | `20260919T172526Z-ac925674-nova` |

## 1. P0 root cause (false overlay)

On live before PASS3 (`before-chasha-overlay.json`):

* `data-state=playing`, label `воспроизведение`, `__zonaPlayerPlaying.pos≈6.6`
* overlay node had `hidden=true` **but** computed `display:grid` / `visibility:visible`
* text still showed «Видео временно недоступно»

Cause: `.zpl__s { display:grid }` beat the HTML `hidden` attribute.

### Fix

1. CSS: `.zpl__s[hidden], .zpl__f [data-player-state][hidden] { display:none !important; … }`
2. Client state machine with `generation` + `attempt`, `hideOverlay()` sets
   `display:none !important`, mutual exclusion PLAYING vs ERROR/UNAVAILABLE,
   provider `message` checks `origin` + `event.source` + generation/attempt,
   destroy + sequential fallback, 35s timeout ignored once `playing`.

## 2. Live golden (chasha-vesny)

| Check | Result |
| --- | --- |
| golden ×10 (`golden-chasha-10x.json`) | **10/10 PASS** |
| final 35s observe (`golden-final-live.json`) | PASS |
| ACTUAL_PROGRESS | 1 |
| VISIBLE_UNAVAILABLE_OVERLAY | 0 |
| PLAYING_AND_ERROR_SIMULTANEOUS | 0 |
| ACTIVE_PLAYER_COUNT | 1 |
| stHidden / stDisplay | true / `none` |
| label while playing | `воспроизведение` |

## 3. Home density

* Removed per-genre mega-shelves; one compact «Смотреть по жанрам» chip row
  (западный контент, дорама, драма, комедия, триллер, боевик).
* Shelves: новинки фильмов, сериалы, недавно фильмы, новые серии, анимация,
  недавно в каталоге, жанры, подборки, SEO, футер.
* Home height @2048: **4331px** (was ~7145).
* Native shelf scrollbars hidden; page `overflowX=0`.
* Card counts (cqw + wrap 1680@1920): 7/6/4/2 at 2048/1440/768/390, peek=0,
  within-shelf height delta=0 (`visual-gates.json`).

## 4. Title / episodes / related

* Compact hero: poster | main | facts; title height 390px @1440; gap to
  «Смотреть» 18px.
* Pluralization: `1 сезон, 30 серий, доступно 6`, `6 голосов`.
* Episodes: number chip grid 12/8/4 cols; eps 7–30 `aria-disabled` + tooltip.
* Related: 12 unique cards, no empty slots.

## 5. Collections / SEO / footer

* Public cards: human labels only (no `53524 записей`).
* SEO block: real H2 + 3 paragraphs + contextual links; snapshot jargon removed.
* Footer: 4 columns; legal/help links only from `footer-zona-01.json`.
* `CONTACT_CONFIG_MISSING=1` → `FOOTER_GATE=FAIL` (example config shipped empty).
* Published footer section links all HTTP 200 (`footer-links.json`).
* Marker: `Zona · 1.2.0 · ac925674`.

## 6. SEO content gate (unchanged catalog)

From PASS2 full scan (still valid; no invented backfill):

| Metric | Value |
| --- | --- |
| DESCRIPTION_COVERAGE_PERCENT | 75.13 |
| MISSING_DESCRIPTION_COUNT | 13314 |
| EXACT_DUPLICATE_GROUPS | 39 |
| NEAR_DUPLICATE_GROUPS | 3 |

→ `ZONA_SEO_CONTENT_CAN_BE_CLOSED=NO`.

## 7. Tests

```
pytest tests/lords/test_zona_pass3.py \
       tests/lords/test_zona_pass2.py \
       tests/lords/test_zona_followup_playback.py \
       tests/lords/test_zona_final_repair.py \
       tests/lords/test_nova_frontend_families.py
→ 124 passed
```

## 8. Deploy

| Field | Value |
| --- | --- |
| DEPLOY_PERFORMED | 1 |
| DEPLOY_SCOPE | zona-01-only |
| method | flock + atomic artifact + zona manifest + nsenter restart |
| build_id | `20260919T172526Z-ac925674-nova` |
| artifact_sha256 | `8ebfdca925fcece60a3c321c305cb97142dff595ebb08f6e47bb504c2a6c6e63` |
| rollback | `/srv/lords/.frontend/.rollback/20260919T172526Z-zona-01-pass3` |
| systemctl is-active nova-zona-01 | active |
| nginx -t | successful (pre-existing yummy name warnings only) |
| X-Robots-Tag | `noindex, nofollow` |
| robots.txt | `User-agent: *` / `Disallow: /` |
| neighbors_unchanged | true |
| DNS_MUTATIONS | 0 |
| INDEXING_OPENED | 0 |
| OTHER_DOMAINS_MUTATED | 0 |
| PUSH_PERFORMED | 0 |
| MERGE_PERFORMED | 0 |

## 9. Commits

1. `1b17926` — overlay CSS + state machine, home/title/episodes/footer/SEO PASS3
2. `c3b8195` — equal card body height / peek safety
3. `ac92567` — cqw shelf sizing + wrap 1680@1920 (**live**)
4. evidence commit (this tree)

## 10. Screenshots

Under `artifacts/evidence/zona-pass3-2026-09-19/screenshots/`:

`home`, `title-summary`, `player-before-play`, `player-playing-after-35s`,
`episodes`, `related`, `seo-block`, `footer`, `collections`
× widths `2048`, `1440`, `768`, `390` (player pair at 1440/390).

Visually checked: 7 cards @2048 no peek; playing frame without UNAVAILABLE;
episode chips; SEO copy; footer four columns with config placeholders.

## 11. Remaining blockers

1. `FOOTER_GATE=FAIL` — populate `footer-zona-01.json` with real routes/email
   (no invented contacts; no `admin@zona.plus`).
2. SEO descriptions 75.13% / 13314 missing / duplicate groups — editorial only.
3. Until both are closed: `ZONA_OVERALL_CAN_BE_CLOSED=NO`.

## 12. Final flags

```
VERDICT=NEEDS_REPAIR
ZONA_PLAYER_CAN_BE_CLOSED=YES
ZONA_TEMPLATE_CAN_BE_CLOSED=NO
ZONA_SEO_CONTENT_CAN_BE_CLOSED=NO
ZONA_OVERALL_CAN_BE_CLOSED=NO

ACTUAL_PROGRESS=1
VISIBLE_UNAVAILABLE_OVERLAY=0
PLAYING_AND_ERROR_SIMULTANEOUS=0
ACTIVE_PLAYER_COUNT=1

DESCRIPTION_COVERAGE_PERCENT=75.13
MISSING_DESCRIPTION_COUNT=13314
EXACT_DUPLICATE_GROUPS=39
NEAR_DUPLICATE_GROUPS=3

DEPLOY_PERFORMED=1
DEPLOY_SCOPE=zona-01-only
DNS_MUTATIONS=0
INDEXING_OPENED=0
OTHER_DOMAINS_MUTATED=0
PUSH_PERFORMED=0
MERGE_PERFORMED=0

CONTACT_CONFIG_MISSING=1
FOOTER_GATE=FAIL
CLIPPED_CARD_COUNT=0
NATIVE_SCROLLBAR_VISIBLE=0
HORIZONTAL_OVERFLOW_PX=0
CARD_ROW_MAX_HEIGHT_DELTA_PX=0
ZONA_PASS2_CAN_BE_CLOSED=NO
```
