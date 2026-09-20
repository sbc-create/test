# VISUAL_FINDINGS

Audit stage: `LORDS-THREE-DISTINCT-TEMPLATES-DEEP-AUDIT-01`  
Evidence root: `artifacts/evidence/lords-three-distinct-deep-audit-2026-09-20/`  
Mode: read-only adversarial live audit (resume from checkpoint; no redeploy).

## Summary counts

| Severity | Count |
| --- | --- |
| P0 | 0 |
| P1 | 2 |
| P2 | 8 |
| P3 | 5 |

`READY_FOR_OWNER_VISUAL_REVIEW=NO` — open P1/P2 remain.

---

## P1

### F-P1-01 LOAD_INDUCED_502_BURST
- **domains:** lordserial33.biz, 1lordserials1.online
- **category:** reliability / capacity
- **actual:** During sequential ~320 internal-link crawl, HTTP matrix recorded 291×502 (lords-02) and 254×502 (lords-03). lords-01 stayed at 0×5xx. Later spot checks recovered to HTTP 200.
- **expected:** Stable 200 under moderate read-only crawl; no tenant-local collapse.
- **evidence:** `HTTP_MATRIX.json`, `14-http/lords-02-links.json`, `14-http/lords-03-links.json`, `17-perf/PERFORMANCE_MATRIX.json`
- **reproducibility:** Load-correlated; not permanent outage at resume time.
- **repair:** Profile/process timeouts, backlog limits, worker concurrency; add soak test before declare production-hard.
- **acceptance:** 300 sequential GETs across home/catalog/title with HTTP_5XX_COUNT=0 on each Lords unit.

### F-P1-02 TEMPLATE_DISTINCTNESS_INSUFFICIENT
- **domains:** all three
- **category:** product / IA
- **actual:** Block titles differ and card modifiers exist (`c--poster` / `c--episode` / `c--editorial`), but chrome is shared: same nav labels, same H1 «Фильмы и сериалы онлайн», same intro, shared collection tiles (incl. anime copy on cinema). Passports still defer mosaic/stronger episode card.
- **expected:** Role-obvious difference in IA, cards, and scenarios — not only accent/token/`data-design`.
- **evidence:** home ATF screenshots ×3 @1440; `THREE_SITE_DISTINCTNESS_MATRIX.*`; passports in `01-reference/`
- **repair:** Role-specific H1/intro/nav emphasis; unique collection sets; finish passport card types.
- **acceptance:** Blind screenshot test: reviewer names profile from home ATF without reading domain; ≥2/3 correct.

---

## P2

### F-P2-01 DUPLICATE_SHELF_PREMIERES_VS_NOVINKI
- **domain:** lordfilm47.space
- **actual:** «Премьеры недели» and «Новинки» share 9/10 titles (freshness matrix).
- **expected:** Distinct selection rules; no near-identical adjacent shelves.
- **evidence:** `09-freshness/FRESHNESS_MATRIX.json`; screenshots `lordfilm47.space__home__block0|block2__*`
- **repair:** Enforce disjoint slug sets across adjacent home rails; different ranking keys.

### F-P2-02 ANIME_COPY_ON_CINEMA_COLLECTIONS
- **domain:** lordfilm47.space (also present on others)
- **actual:** Collection tile «Недавно добавленные» body: «Свежие поступления в каталог аниме.»
- **expected:** Cinema role must not advertise anime catalog; curated/series copy must be profile-aware.
- **evidence:** `lordfilm47.space__home__block4__*`; curated block1 screenshot
- **data_gap_or_template:** template/copy binding bug (shared collection descriptors)

### F-P2-03 INCOMPLETE_VISUAL_ROWS_ON_KEY_RAILS
- **domains:** all
- **actual:** Title rails with blankSlots: cinema Popular 10/6→2 blanks; series Popular 11→1; series Films 8→4; curated Editor’s choice 10→2; curated New 8→4.
- **expected:** Full visual rows or intentional asymmetric layout with design treatment (not sparse empty slots).
- **evidence:** `BLOCK_INVENTORY.json`, `04-blocks/*`, home ATF screenshots
- **note:** Last incomplete row is not auto-fail; these look underfilled for hero rails.

### F-P2-04 BROKEN_POSTERS_ON_CINEMA_SERIES_RAIL
- **domain:** lordfilm47.space
- **actual:** 6 cards with `imgNaturalW=0` on «Сериалы» rail (occupancy).
- **expected:** Poster loads or honest designed fallback without broken image state.
- **evidence:** `CARD_OCCUPANCY.csv`, `CARD_GEOMETRY.json`, `lords-01-home-blocks-1440.json` section «Сериалы»

### F-P2-05 TITLE_OVERFLOW_HIGH
- **domains:** all
- **actual:** 50/131 sampled home cards with titleOverflow=true.
- **expected:** Stable clamp without visual overflow/cutoff artifacts.
- **evidence:** `CARD_OCCUPANCY.csv`

### F-P2-06 SHARED_COLLECTION_SET_ACROSS_PROFILES
- **domains:** all
- **actual:** Same five collection tiles (Recently added / New films / High ratings / This year / With video) on cinema, series, curated homes.
- **expected:** Profile-specific editorial sets.
- **evidence:** block screenshots Подборки / Тематические подборки

### F-P2-07 PLAYER_INSTANCE_NOT_PROVEN_FROM_SSR
- **domains:** all
- **actual:** HTML audit counted inflated `data-player` markers (~22) with 0 iframes; client player not proven in this pass.
- **expected:** Live playing state with instance max=1, 16:9 fill, autoplay=0.
- **evidence:** `PLAYER_MATRIX.json`, `11-player/PLAYER_INTERPRETATION.json`, title/episode screenshots
- **severity:** Browser evaluate on playing provider titles (next stage)

### F-P2-08 SERIES_FILM_RAIL_USES_TRUNCATED_HORIZONTAL_CARDS
- **domain:** lordserial33.biz
- **actual:** «Фильмы в каталоге» horizontal cards truncate titles («Правда или…», «Резня в Норто…»).
- **expected:** Readable titles or explicit tooltip/expand; series site film rail should not look like damaged episode cards.
- **evidence:** `lordserial33.biz__home__block4__*`

---

## P3

### F-P3-01 FALLBACK_LETTER_NODE_ALWAYS_IN_DOM
- **actual:** `c__none` present on every card even when image loaded.
- **expected:** Fallback only when image missing/errors.
- **evidence:** occupancy `fallbackLetter=true` with imgNaturalW>0

### F-P3-02 ZOOM200_KEYBOARD_MATRIX_NOT_RUN
- coverage gap for B15 zoom/keyboard — not claimed PASS.

### F-P3-03 PERF_LAB_NOT_RUN
- no LCP/CLS lab; only crawl resilience note.

### F-P3-04 A11Y_SURFACE_ONLY
- home lang/alt seed only; not full WCAG claim.

### F-P3-05 CONTACT_SHEET_MOSAIC_NOT_GENERATED
- 94 individual PNGs indexed; no single mosaic PNG sheet.

---

## Non-findings (pass-like)

- Live build/artifact/design match expected release (`PREFLIGHT.json`).
- Indexability remains `noindex, nofollow` on all three.
- Search nonsense queries did not flood full catalog (`SEARCH_MATRIX.json`).
- Invalid pagination `/catalog/?page=999999` → HTTP 404.
- Popular week digest stable across two requests; digests differ between lords-01 and lords-02.
- No soft-404 on sampled HTTP 200 title pages in crawl.
- Card modifiers are not identical strings across profiles (partial distinctness credit).
