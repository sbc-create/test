# Zona follow-up — 2026-09-19

## Verdict

`VERDICT=PASS`

Real provider video resolution after click (plapi `/api/v1/player/sv/video/…`
HTTP 200), honest unavailable episode pages, even card rows (`delta=0`), genre
nav with distinct result sets, compact three-zone title (desktop player top
≈526px), dormant ad slot (`display:none`), live artifact matches commit
`5906cde`, noindex retained, neighbours’ manifests untouched.

`ZONA_FOLLOWUP_CAN_BE_CLOSED=YES`

## 1. Starting state

| Field | Value |
| --- | --- |
| pwd | `/home/claude/wt-zona-finalization-01` |
| branch | `claude/zona-template-finalization-01` |
| START_HEAD | `bcbea00877708c7f930f1fe931a17f66decafed5` |
| FINAL_HEAD | `5906cde39dfc3a18dd6c4b86440e92b905bbfebc` |
| git status at start | clean on checkpoint |
| live before | build `20260919T143500Z-2d6d1695-nova`, artifact `14ce882d…`, source `bcbea00…`, aida `data-state=playable` + `aggregator=cvh` + label «источник подключён» |

## 2. Proven playback root cause

**Code path:** `кандидаты_источника` ← `источник_по_провайдеру` ←
`разметка_плеера` ← client `СКРИПТ_ПЛЕЕРА_КЛИЕНТ`.

**Evidence (before):** on `/title/aida-vozvraschaetsya/` SSR mounted
`data-aggregator="cvh"` with the catalog UUID while sidecar already had
`sources[{provider:kp, source_id:11922371, availability_status:available}]`.
Provider answered empty for that UUID; UI still showed active Play +
«Провайдер не отдал источник» + «источник подключён» (false combined state).
`ok` was previously set on `shadowRoot` alone (not playback).

**Fix:**

1. Candidate order: available `sources` → UUID/cvh → other sources → externals.
2. SSR state `resolving` (provider configured ≠ playable confirmed); label
   «подключение источника», never «источник подключён» until READY.
3. Limited `noData` remount across candidates (`maxFallback=3`, request token).
4. READY only on media events (`playing`/`play`/`loadeddata`/nested video),
   not on shadow mount.

## 3. Source-selection contract

| State | Meaning |
| --- | --- |
| `noaccess` | NO_PROVIDER |
| `awaiting` | AWAITING_EPISODE |
| `resolving` / `loading` | RESOLVING |
| `ok` | READY (media event) |
| `unavailable` / `nosource` / `provider` | UNAVAILABLE |
| `error` / `slow` | ERROR |

Series hub picks **first** playable episode; direct unavailable episode URLs
stay honest (`unavailable`, no `<video-player>`).

## 4. Live player sample

Evidence: `after/playback-strict.json` (strict = plapi video id / stream URL,
not posters).

| Metric | Value |
| --- | --- |
| PLAYER_SAMPLE_TOTAL | 12 |
| PLAYER_PLAYABLE_PASS | 10 |
| PLAYER_HONEST_UNAVAILABLE | 1 (`…/season-1/episode-12/` → `unavailable`) |
| PLAYER_FALLBACK_RECOVERED | 1 (aida: kp `11922371` preferred over UUID) |
| PLAYER_FAILURES | 1 (invalid season-2 URL → HTTP 404; title only has season 1) |

Checked live (among others): aida, skyfall, imperiya, anna hub/ep, mira, mgc,
chile, occult ep1, spectrum. aida after fix: `aggregator=kp`,
`data-title-id=11922371`, no «источник подключён», video API
`…/sv/video/14628861336170` 200 after click. Tokens/URLs redacted in prose.

## 5. Cards / genres / title

| Gate | Result |
| --- | --- |
| CARD_ROW_MAX_HEIGHT_DELTA_PX | **0** |
| HORIZONTAL_OVERFLOW_PX | **0** |
| Genre block | «Смотреть по жанрам» after first shelf; real `<a href>` |
| Genre sets | west_content / dorama / drama / comedy / triller — distinct, 200, deep-link OK |
| Title desktop | `.ztitle` 3 zones; player top **526px** @1440×900; ad `data-ad-enabled=0` → `display:none` |
| Screenshots | 24 under `screenshots/` (1440 / 768 / 390 × pages) |

## 6. Tests

```
pytest tests/lords/test_zona_followup_playback.py \
       tests/lords/test_nova_frontend_families.py \
       tests/lords/test_zona_final_repair.py
→ 95 passed
```

Plus follow-up module coverage for source order, honest nosource, episode hub,
genre nav, compact title, ad slot CSS.

## 7. Deploy

| Field | Value |
| --- | --- |
| DEPLOY_PERFORMED | 1 |
| DEPLOY_SCOPE | zona-01-only |
| method | flock + `lords-nova-canary.py install` (rolled back on polkit restart) then official finalize via nsenter `systemctl restart nova-zona-01` |
| rollback | `/srv/lords/.frontend/.rollback/20260919T151916Z-zona-01-followup` |
| live build | `20260919T151916Z-5906cde3-nova` |
| live artifact | `5cbd0eb79395f971eea021c08cac0816c4194d79cf76f288835ceb9fd6d5b7d8` |
| source/runtime | `5906cde39dfc3a18dd6c4b86440e92b905bbfebc` |
| X-Robots-Tag | `noindex, nofollow` |
| robots.txt | `Disallow: /` |
| other manifests | Lords / Animedia / yummy unchanged |

## 8. Commits / files

1. `159d1a3` — honest playback, even cards, genre nav, compact title + tests  
2. `5906cde` — require media events before READY  
3. (this) evidence/report  

Changed: `automation/host/lords-frontend.py`,
`tests/lords/test_zona_followup_playback.py`,
`tests/lords/test_nova_frontend_families.py`,
`artifacts/evidence/zona-followup-2026-09-19/**`

## 9. Remaining notes

- Cross-origin iframe does not expose `HTMLMediaElement` events to the page;
  READY may stay `resolving` until in-iframe play, while plapi video id 200
  already proves provider-ready after click.
- Shared `lords-frontend.py` on disk is the new artifact; other vitrines keep
  their manifests/design branches and were not restarted.

## Flags

```
VERDICT=PASS
DEPLOY_PERFORMED=1
DEPLOY_SCOPE=zona-01-only
DNS_MUTATIONS=0
INDEXING_OPENED=0
ACCESS_OPENED=0
OTHER_DOMAINS_MUTATED=0
PAID_OPERATIONS=0
PUSH_PERFORMED=0
MERGE_PERFORMED=0
SECRETS_EXPOSED=0
ZONA_FOLLOWUP_CAN_BE_CLOSED=YES
```
