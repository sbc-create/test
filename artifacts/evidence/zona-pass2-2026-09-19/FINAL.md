# Zona LIVE PASS 2 — 2026-09-19

## Verdict

`VERDICT=PASS`

`ZONA_PASS2_CAN_BE_CLOSED=YES`

Real PLAYING is proven by CDNVideoHub provider `postMessage`
(`statechange=playing` / `timeupdate` with progress) plus media bytes — not by
HTTP 200 on `/sv/video/`. Live golden **12/12** play, player stage **1200×675
(ratio 1.778)**, phrase search places Star Wars titles first, same-page
synopsis is not duplicated, footer is four-zone, neighbors untouched.

## 1. Starting state

| Field | Value |
| --- | --- |
| pwd | `/home/claude/wt-zona-finalization-01` |
| branch | `claude/zona-template-finalization-01` |
| START_HEAD | `060cb2c00eb5eaf72e982a1c1c54ccf908ee4269` |
| FINAL_HEAD | `06a8250daf0230d8f69245a6bc73695303009141` |
| live before | `20260919T151916Z-5906cde3-nova` |
| shared runtime before | Animedia tip `3fb63ad` / artifact `42299302…` |

## 2. Proven root causes

### Playback (v-lovushke / voy-2 / aida)

1. Provider **does** return valid playlist + HLS/DASH (`/sv/playlist` + `/sv/video/` 200 with real `sources.hlsUrl`).
2. SDK mounts a **cross-origin iframe** (`player.cdnvideohub.com/.../frame/`). There is **no** `<video>` in the light DOM / open shadow for the host page to observe.
3. Previous client looked for `shadowRoot video` / treated HTTP 200 as success, then after 15s set `slow` → CSS collapsed the stage to ~157px while the provider had already emitted `statechange=playing`.
4. Host/`video-player` stayed ~150px tall inside a 16:9 frame (content not filling stage) → “banner in empty shell”.
5. IMDb IDs were still in playback candidates (PC-2 violation) as useless fallbacks.

**Fix:** listen for `message` from `https://player.cdnvideohub.com` (`ready` → READY; `timeupdate`/`playing`+progress → PLAYING); timeout/noData/error → limited candidate fallback; `is-show-banner=false`; absolute fill CSS; keep 16:9 on provider/error (no 150px trap); strip IMDb from playback aggregators.

### Search (`звездные войны`)

NFKD split `й` → token `вои`+`ны`, so `вой` matched as an exact token of `войны`. **Fix:** NFKC normalize + phrase-first tiers + significant-token AND. Popularity cannot beat phrase tiers.

### Description (voy-2)

Hero used truncated full synopsis while «О чём это» repeated it. **Fix:** hero only for distinct `short_description`; full synopsis once at `#synopsis`.

## 3. Golden playback

| Stage | Playable pass | Unavailable honest | False READY | Stage ratio |
| --- | --- | --- | --- | --- |
| candidate `:19120` | 11/12 (bad slug `spektrometr`) then `007-spektr` OK | 1/1 | 0 | 1.778 |
| live after | **12/12** | **1/1** | **0** | **1.778** |

Includes `/title/v-lovushke/`, `/title/voy-2/`, `aida`. Evidence:
`golden-playback-candidate.json`, `golden-playback-after.json`.

`PLAYER_HTTP_200_ONLY_NOT_COUNTED=1`

## 4. Search

Live top results for `звездные войны` are all Star Wars titles; `Вой` not in top-10.
Heading: `Результаты поиска: «звездные войны»`.

`SEARCH_EXACT_TOP1=1` (phrase / prefix tier)
`SEARCH_FULL_PHRASE_BEFORE_PARTIAL=1`
`SEARCH_SINGLE_TOKEN_FALSE_POSITIVES=0`

## 5. Description quality

| Metric | Value |
| --- | --- |
| titles_total | 53524 |
| with_description | 40210 |
| missing_description | 13314 |
| DESCRIPTION_COVERAGE_PERCENT | 75.13 |
| exact_cross_title_duplicate_groups | 39 |
| near_duplicate_description_groups | 3 |
| backfilled | 0 (no invented text) |

Pipeline: `automation/host/zona_description_quality.py` (full 53k scan finished).
Missing → editorial queue / `MISSING_DESCRIPTION`, not SEO-ready claim.

`SAME_PAGE_FULL_DESCRIPTION_DUPLICATES=0` on voy-2 (synopsis once).

## 6. Layout

| Metric | Value |
| --- | --- |
| PLAYER_STAGE_RATIO | 1.778 |
| PLAYER_CHILD_COVERAGE | 100% |
| STICKY_HEADER_OVERLAP_PX | 0 |
| METADATA_LABEL_VALUE_OVERLAPS | 0 |
| CARD_ROW_MAX_HEIGHT_DELTA_PX | 0 |
| HORIZONTAL_OVERFLOW_PX | 0 |
| Footer | 4 zones + `Zona · v1.2.0 · 06a8250d` |

Screenshots under `screenshots/` (1440/768/390 × home/search/titles/catalog).

## 7. Tests

```
pytest tests/lords/test_zona_pass2.py \
       tests/lords/test_zona_followup_playback.py \
       tests/lords/test_nova_frontend_families.py \
       tests/lords/test_zona_final_repair.py
→ 111 passed
```

## 8. Deploy

| Field | Value |
| --- | --- |
| DEPLOY_PERFORMED | 1 |
| DEPLOY_SCOPE | zona-01-only |
| method | flock `.deploy.lock` + atomic artifact + zona manifest + nsenter `systemctl restart nova-zona-01` |
| candidate | `127.0.0.1:19120` pre-switch golden |
| rollback | `/srv/lords/.frontend/.rollback/20260919T160721Z-zona-01-pass2` |
| live build | `20260919T160708Z-06a8250d-nova` |
| artifact | `42d247622f4d492da382820c23b7231e9ee0df44504ac15291fb726f6797cd9a` |
| source/runtime | `06a8250daf0230d8f69245a6bc73695303009141` |
| shared runtime | PASS2 ported onto Animedia live tip (АНИМЕДИА_СТИЛЬ unchanged; `ОФОРМЛЕНИЕ_1_2_1` kept) |
| X-Robots-Tag | `noindex, nofollow` |
| neighbors | unchanged (`neighbors_unchanged=true`) |

## 9. Commits

1. `a0e67dd` — postMessage PLAYING, phrase search, layout/desc/footer (pre-port)
2. `1dde57e` — PASS2 regression tests
3. `06a8250` — reapply PASS2 onto live Animedia shared runtime (**live**)
4. evidence commit (this tree)

## 10. Flags

```
VERDICT=PASS
DEPLOY_PERFORMED=1
DEPLOY_SCOPE=zona-01-only
PLAYER_HTTP_200_ONLY_NOT_COUNTED=1
PLAYER_FALSE_READY=0
PLAYER_ACTUAL_PLAYING_PASS=12/12
PLAYER_STAGE_RATIO=1.778
SEARCH_EXACT_TOP1=1
SEARCH_SINGLE_TOKEN_FALSE_POSITIVES=0
SAME_PAGE_FULL_DESCRIPTION_DUPLICATES=0
DESCRIPTION_COVERAGE_PERCENT=75.13
STICKY_HEADER_OVERLAP_PX=0
METADATA_LABEL_VALUE_OVERLAPS=0
CARD_ROW_MAX_HEIGHT_DELTA_PX=0
HORIZONTAL_OVERFLOW_PX=0
DNS_MUTATIONS=0
INDEXING_OPENED=0
ACCESS_OPENED=0
OTHER_DOMAINS_MUTATED=0
PAID_OPERATIONS=0
PUSH_PERFORMED=0
MERGE_PERFORMED=0
SECRETS_EXPOSED=0
```

## Remaining blockers (non-closing)

- 13314 titles still `MISSING_DESCRIPTION` — need approved content pipeline backfill (not invented).
- 39 exact cross-title description duplicate groups — editorial cleanup.
- 3 near-duplicate description groups (Jaccard ≥ 0.92) — editorial cleanup.

ZONA_PASS2_CAN_BE_CLOSED=YES
