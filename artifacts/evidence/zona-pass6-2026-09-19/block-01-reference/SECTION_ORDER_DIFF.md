# Block 01 — Section order diff (reference vs live)

References used (existing, not newly chosen):

- `artifacts/evidence/templates-zona-animedia-visual-parity-006/screenshots/reference/zona-reference-home-{1440x900,768x1024,390x844}.png`
- `artifacts/evidence/templates-zona-animedia-owner-review-007/owner-package/pairs/zona-*.png`
- Pass5 live baselines: `artifacts/evidence/zona-pass5-2026-09-19/screenshots/*`
- Pass6 live before: `block-01-reference/screenshots/*`

## Home

| # | Reference (legacy Zona family) | Live Pass5/6 | Match | Notes |
| --- | --- | --- | --- | --- |
| 0 | Header: logo + ФИЛЬМЫ/СЕРИАЛЫ + search | Header: logo + 7 nav links + search | structural diverge | Factory nav richer; keep unless owner demands legacy pair |
| 1 | Популярные новинки фильмов | Популярные новинки фильмов | YES | |
| 2 | Популярные сериалы | Популярные сериалы | YES | |
| 3 | Добавленные недавно фильмы | Добавленные недавно фильмы | YES | |
| 4 | Новые серии | Новые серии | YES | |
| 5 | Новые трейлеры | Популярная анимация | intentional | Trailer shelf not in current product; animation shelf is Zona contract |
| 6 | — | Недавно в каталоге → `/new/` | extra | Risk of overlap with «добавленные недавно» |
| 7 | — | Жанры pills | extra | OK if not sticky side rail |
| 8 | Social/footer contacts | Подборки tiles + SEO prose + footer | diverge | Contacts OWNER_DATA_BLOCKER |

## Catalog / kind / year

Reference owner pairs show dense poster grids. Live Pass5 locked `8/7/4/2` with card≈175px@1440 — **baseline, do not densify further**.

## Title detail

| Region | Reference family | Live | Severity |
| --- | --- | --- | --- |
| Poster left | present | present (~260×390) | OK |
| H1 + original title | present | present | OK |
| Ratings with source | star+number | IMDb badge + text | P2 dual presentation |
| Facts | compact | `ztitle__facts` grid | OK |
| Right rail | minimal | «СЕРИИ» status panel | P1 structural |
| Description once | yes | clamp + Развернуть | OK |
| CTA Смотреть | yes | yes | OK |
| Player below | yes | yes (locked) | do not touch SM |

## Collections

Live `/collections/` and home «Подборки» are text tiles, not poster cards. Related grid uses shared `title-card`. Audit for duplicate sets / broken links deferred to Block 05 with matrix.

## Footer

| Viewport | Reference | Live | Severity |
| --- | --- | --- | --- |
| Desktop | brand + contacts | brand + Разделы + Каталог (3 cols, no empty help/docs) | visual OK; data gap |
| Mobile | compact | 3 stacked cols; links not forced to 2-col brand+links layout | P2 visual |
| Contacts/legal | admin@… on legacy ref | absent (`data-contact-config-missing=1`) | OWNER_DATA_BLOCKER |

## Player

Locked Pass5 golden 10/10 — inventory only; no mutation in Blocks 01–06 unless regression.
