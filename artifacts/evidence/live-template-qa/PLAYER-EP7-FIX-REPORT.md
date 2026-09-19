# Lords player ep7/ep3 — live fix report

**Date:** 2026-09-19  
**Site:** lords-02 / https://lordserial33.biz  
**Title slug (live):** `sudmedekspert-stavshaya-domohozyaykoy`  
(note: user URL typo `…domokhozyaykoy…` → 404; live slug is `…domohozyaykoy…`)

## Root cause (episode 7 vs «Эпизод 3»)

Details sidecar for this title: `avail=3`, `eps=9`. Provider playlist returns **exactly 3 items** (Серия 1–3).

Episode URL `/season-1/episode-7/` mounted `<video-player episode="7">` while the episode list already marked 4–9 as `data-off`. CDNVideoHub has no item 7; the control UI showed the last available episode («Эпизод 3»). The 15s client timer (`СКРИПТ_ПЛЕЕРА_КЛИЕНТ`) then fired «Плеер не поднялся» because the SDK never reached a stable ready for the requested missing episode.

Not an off-by-one in URL parsing: URL, SSR text, and list highlight correctly said 7. The bug was **mounting the SDK with an episode number beyond `avail`**.

## Fix

Systemic gate in `разметка_плеера`: if `эпизод > avail` → state `unavailable`, **no** `<video-player>`, **no** provider script. Same identity as list `data-off`. Helper `серия_с_дорожкой`.

Commits:

- `a67bf79` — `fix(lords): gate player mount on avail, not eps alone`
- `4ac8183` — `chore(nova): point closed runtime at player avail-gate tip`

## Tests

```text
tests/unit/test_lords_player_episode_avail.py  (new)
+ test_lords_player_catalog_details_skew / player_states / playability /
  player_reaches_the_visitor / series_without_seasons / ongoing_episodes /
  shelf_unknown_playback
→ 71 passed (player-related cluster); episode_avail alone 5 passed
git diff --check on touched source: clean (unrelated QA HTML still has trailing space)
```

## Deploy

| Field | Value |
| --- | --- |
| DEPLOY_PERFORMED | **yes** — lords-02 only |
| Command | `APPLY_SITES=lords-02 FORCE_INSTALL_FRONTEND=1 FACTORY_OWNER_ROOT_MANDATE=SITE_FACTORY_ROOT_20260909 python3 automation/host/apply-nova-closed-update.py` |
| runtime_commit | `a67bf79d64eb30480e224a9a30c4bbe6288221b7` |
| artifact_sha256 | `7491029692f528cb810a63b35b9b2f92b4942ca2f0364c2f6d35f13400c9a067` |
| build_id | `20260919T074636Z-a67bf79d-nova` |
| rollback | `/srv/lords/.frontend/.rollback/pre-closed-update-20260919T074636Z` |
| DNS_MUTATIONS | **none** |
| INDEXING_OPENED | **no** — `X-Robots-Tag: noindex, nofollow` still on episode pages |

## Live acceptance

Exact URL: https://lordserial33.biz/title/sudmedekspert-stavshaya-domohozyaykoy/season-1/episode-7/

| Case | Result |
| --- | --- |
| ep7 | `data-state=unavailable`, 0×`video-player`, copy «Дорожки этой серии ещё нет», list `aria-current=7` |
| ep1 | provider `episode="1"`; after click: `readyState=4`, `currentTime≈3`, `paused=false`, okcdn 2xx |
| ep3 | provider `episode="3"`; playlist items 1..3 only; `readyState=4`, playing, segments 2xx |
| hub | `data-state=awaiting`, no SDK |
| ep9 | `unavailable` (same gate) |

Evidence:

- `artifacts/evidence/live-template-qa/raw/player-ep7-verify.json`
- `artifacts/evidence/live-template-qa/raw/player-acceptance.json`
- `artifacts/evidence/live-template-qa/raw/player-real-playback.json`
- `artifacts/evidence/live-template-qa/raw/player-playlist-items.json`
- screenshots under `artifacts/evidence/live-template-qa/screenshots/deep-pass/lords-ep*`

## Why the 15s timeout fired (before fix)

Client marks `ok` when shadow/children appear, but for a missing episode the provider never delivered a playable track for the requested number; after 15s without `поднялся` staying true in a playable sense / or unstable mount, UI showed «Плеер не поднялся». After fix, ep7 never starts that timer (no SDK).

## Lords closed?

**Yes** for this bug: unavailable is honest on ep>avail; at least one real playable episode (ep1 and ep3) proven with `readyState>=2` and advancing `currentTime` plus media 2xx.
