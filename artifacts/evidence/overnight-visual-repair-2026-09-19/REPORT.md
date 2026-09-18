# Overnight visual repair — REPORT — 2026-09-19

## Scope

Closed storefronts only. Local commits in `cursor/lords-integration-canary-01`.
**No** push, merge, DNS, nginx/systemd, production deploy, indexing open.

| Domain | Site | Live profile | Live source / runtime (audit start) |
| --- | --- | --- | --- |
| lordserial33.biz | lords-02 | lords-new | `479f7d2` / `479f7d2` |
| animedia.space | animedia-02 | animedia-general | `b023bd50` / — |
| animedia.icu | animedia-01 | animedia-general | `b023bd50` / — |
| zonafilm.space | zona-01 | zona-general | `a10e68b2` / `99ec7829` |

Starting HEAD: `b1522a5201dfd7e9168009c87b3ec5ff62242679`  
Fix commit: `3c4a9d348e0645c58d664ffed3d5cd3e8a795fc4`  
Tip HEAD: `6f0b2c3505b4a12e9a27055b1c60ebb67af1ea44`

## Root causes addressed (code)

1. **Search latin/slug/mixed empty (P1)** — runtime `Данные.искать` only matched Cyrillic title forms; slug and translit were absent; mixed tokens were concatenated into one impossible core.
2. **Unencoded `kind=` / `genre=` in href (P2)** — `запрос_строкой` wrote raw UTF-8 query values; non-browser clients break.
3. **Lords empty «КП — / IMDb —» (P2)** — card renderer drew dash placeholders when ratings were absent.
4. **Permanently empty shelves (P2/P3)** — Zona «Новые трейлеры» and Animedia «Онгоинги» / «Сегодня выйдет» have no source fields; empty `zempty` blocks hurt density vs refs.
5. **Horizontal overflow risk** — shared CSS lacked `overflow-x:clip` / flex `min-width:0` on filter strips.

## Fixes shipped in worktree (await controlled deploy)

| Change | File |
| --- | --- |
| Search: slug + translit forms, layout variant, mixed-token OR | `automation/host/lords-frontend.py` |
| Percent-encode query builders + nav/genre/kind hrefs | same |
| Lords cards: omit rating strip without numbers | same |
| Hide empty trailers / ongoing / today-schedule shelves | same |
| Animedia search placeholder → «Поиск аниме» | same |
| Global overflow-x clip + filter wrap hardening | same |
| Regression tests | `tests/unit/test_lords_overnight_visual_repair.py` |

## Live audit (pre-deploy; still on previous builds for Animedia/Zona)

Evidence: `audit/*.json`, `audit/summary.json`, `raw/playwright-overflow.json`, `screenshots/*`.

### Routes (all four)

| Path | Lords | Animedia×2 | Zona |
| --- | --- | --- | --- |
| `/` | 200 | 200 | 200 |
| `/catalog/` `/new/` `/search/` `/collections/` | 200 | 200 | 200 |
| `/genres/` `/countries/` `/years/` `/ongoing/` | 404 | 404 | 404 |
| `/schedule/` | 308 | 200 | 308 |
| `/robots.txt` | `Disallow: /` | same | same |
| `/sitemap.xml` | 200 | **404** | 200 |
| unknown URL | 404 | 404 | 404 |
| `X-Robots-Tag` / meta robots | noindex,nofollow | same | same |

### Search (live, pre-deploy code)

| Query class | Lords | Animedia | Zona |
| --- | --- | --- | --- |
| Cyrillic exact | hits | hits | hits |
| Latin / slug / mixed | **0** (live build) | **0** | **0** |
| Empty / missing | honest empty | same | same |

Post-fix unit tests prove latin/slug/mixed/layout hits on the new runtime.

### Player (Lords live — do not regress)

| URL | state | `<video-player>` |
| --- | --- | --- |
| `/title/eho-kamera/` | playable | 1 |
| `/title/troe-papash/` | awaiting | 0 |
| `/title/troe-papash/season-1/episode-1/` | playable | 1 |

### Responsive (Playwright Chromium)

Home at 1440 / 768 / 390: **no horizontal overflow** on all four closed domains.
Reference `w140.zona.plus` at 390: overflow=true (scrollWidth 600) — our Zona does not copy that defect.

Screenshots under `screenshots/`.

## Remaining blockers (not bypassed)

| ID | Blocker | Owner |
| --- | --- | --- |
| B1 | Animedia/Zona `/poster/` not served by nginx (`404`/`308`); enabling `LORDS_POSTER_SAME_ORIGIN=1` would break posters until vhost gets Lords-style poster cache. | infra / deploy-nova nginx allowlist — **forbidden this night** |
| B2 | Animedia «Онгоинги» / «Сегодня выйдет» need source fields (ongoing flag / air time). Code now hides empty shelves; data still missing. | content pipeline |
| B3 | Live Animedia still `source_commit=b023bd50`; Zona runtime `99ec7829`. Fixes above are **not live** until controlled `apply-nova-closed-update`. | operator deploy (out of scope tonight) |
| B4 | Circe font / Premium mega-menu / login chrome on amd.online are reference-only; closed stand must not invent auth or licensed fonts. | product / rights |
| B5 | Zona home reports catalog size **53493** (same order as Lords). Suspected shared snapshot vs ~3.8k cinema catalog — data ownership, not CSS. | catalog assignment |
| B6 | Latin search on **live** remains broken until B3 deploy. | deploy |
| B7 | Unrelated dirty `seo_operator/*` + prior `live-template-qa` artifacts left untouched. | other owners |

## Tests run

```
pytest tests/unit/test_lords_overnight_visual_repair.py \
       tests/unit/test_lords_player_catalog_details_skew.py \
       tests/unit/test_lords_player_states.py \
       tests/unit/test_lords_search_token_aware.py \
       tests/unit/test_lords_header_search.py
→ 43 passed
git diff --check → clean
```

Heavy suite **not** run: lock present at `/home/claude/run-locks/site-factory-heavy-build.lock`.

## Not done (explicit)

- `DEPLOY_PERFORMED=0` (forbidden)
- `DNS_MUTATIONS=0`
- `INDEXING_OPENED=0`
- no push / merge / reset / stash
- no nginx / systemd
- no reference-pack / visual-scoring / structure_order edits
- no fake iframes / invented posters / providers

## Ready for controlled deploy

1. Commit(s) containing `lords-frontend.py` + overnight tests.
2. Operator path: `apply-nova-closed-update.py` with `APPLY_SITES=lords-02,animedia-01,animedia-02,zona-01` and `FORCE_INSTALL_FRONTEND=1` when approved.
3. After deploy: re-run search latin/slug matrix + Animedia empty-shelf absence + Lords player contract + overflow Playwright.
4. Poster proxy for Animedia/Zona only after nginx poster cache is wired (B1).
