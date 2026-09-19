# Animedia follow-up — FINAL

## Identity

| Field | Value |
| --- | --- |
| branch | `claude/animedia-template-finalization-01` |
| START_HEAD | `6d0625498a65adab477b3543099348f5c6142d86` |
| FINAL_HEAD | `0a6874a` (see `git log`) |
| worktree | `/home/claude/wt-animedia-finalization-01` |

## Root cause (player loss)

Proven on live `animedia.icu/title/master-lda-i-plameni-2/` **before** this follow-up:

- HTML bound `data-aggregator="cvh"` + UUID title id
- **no** `data-src-candidates`
- details sidecar already had `sources: [{provider: mali, source_id: 53477, availability_status: available}]`
- disk `/srv/lords/.frontend/lords-frontend.py` already contained mali-first `кандидаты_источника`, but **nova-animedia-0{1,2} processes were still running the previous in-memory module** (footer tip `289a459`, build `…-289a459f-nova`)

So the recurring “player disappears after deploy” was **not** a missing provider track for episode 104. It was **stale process + CVH-only binding** (and earlier deploys that could leave Animedia on a tip without candidate fallback while Zona’s file on disk advanced).

Architectural fix:

1. Keep Zona `markReady` / `__zonaPlayerReady` playback-ready contract (no shadowRoot false READY)
2. Emit `data-src-candidates` with **mali before cvh**
3. Release gate blocks runtime downgrade / catalog-details skew
4. Apply path installs frontend for Animedia-only updates and **restarts** units, then probes binding on localhost

## Release bundle

| Field | animedia.icu | animedia.space |
| --- | --- | --- |
| profile | `animedia-icu` | `animedia-space` |
| revision | `3fb63ad52ed82a1959c93e591763fa968e9333ec` | same |
| build_id | `20260919T155522Z-3fb63ad5-nova` | same |
| artifact_sha256 | `42299302a0dc61f966b02f88e4c3e16a0366fc8bab95e0a93fc382f95f4ce7c5` | same |
| content snapshot | catalog/details revision `fe5e1331…` match | same revision family |
| rollback | `/srv/lords/.frontend/.rollback/pre-closed-update-20260919T155522Z` | same |

## Playback evidence

| Stage | Result |
| --- | --- |
| BEFORE live | `PROVIDER_BINDING_MATCH=0`, agg=`cvh`, no candidates (`PLAYER_BEFORE.json`) |
| CANDIDATE/local after restart | `PROVIDER_BINDING_MATCH=1`, agg=`mali`, mali_first |
| AFTER live both domains | `PROVIDER_BINDING_MATCH=1`, candidates present, tip `3fb63ad` |

Golden HTTP sample recorded in `LIVE_AFTER.json` / `LIVE_AFTER_COLLAGE.json`.

**Remaining:** no headed browser in this environment → real click / `playing` / `currentTime>3s` / provider ready callback was **not** instrumented end-to-end. Binding + markup gate is green; owner click confirmation still required for full golden PASS.

## Episodes

- Label: `Сезон 2 · 104 серий` (no `Сезон 2104`)
- Numbers `1…104` all present in DOM (`HIDDEN_EPISODE_NUMBERS=0`)
- CSS Grid `auto-fill` minmax 44–48px

## Collections

Independent selectors: movies / donghua / short / classic / action / romance / family / series_with_episodes / top_rated / year / playable.

`new_episodes` no longer falls back to `catalog[:N]` — requires episode timestamps (absent in current sidecar → empty/hidden).

Hub collage after fix: `EXACT_DUPLICATE_SHELVES=0`, `MAX_CROSS_SHELF_JACCARD_TOP4=0.0`.

Home shelves (icu): Сериалы с сериями → Новые аниме → Топ → Аниме-фильмы → Дунхуа (deduped across shelves).

## Layout

- Cards: denser grid up to 7–8 columns, poster `aspect-ratio: 2/3`, wrap max 1440px
- Title: `ztitle` three-column (poster / main / rail), no technical synopsis stub
- Compact episode list items on home

## SEO / safety

- Profiles still split (icu vs space title/description differ)
- `X-Robots-Tag: noindex, nofollow` preserved
- Lords/Zona/Yummy not in APPLY_SITES
- No DNS / indexing / access open / push / merge

## Tests

```text
tests/unit/test_animedia_followup_player_collections.py  9 passed
tests/test_collection_contract.py                        passed (incl. episode-events contract)
```

## Flags

```
VERDICT=NEEDS_REPAIR
DEPLOY_PERFORMED=1
DEPLOY_SCOPE=animedia.space+animedia.icu
RUNTIME_DOWNGRADE=0
CONTENT_SNAPSHOT_DIGEST_MATCH=1
PLAYER_FALSE_READY=0
HIDDEN_EPISODE_NUMBERS=0
EXACT_DUPLICATE_SHELVES=0
DNS_MUTATIONS=0
INDEXING_OPENED=0
ACCESS_OPENED=0
OTHER_DOMAINS_MUTATED=0
PAID_OPERATIONS=0
PUSH_PERFORMED=0
MERGE_PERFORMED=0
SECRETS_EXPOSED=0
```

## Remaining blockers

1. **Golden click playback** not auto-verified (no browser runtime here).
2. **Episode wall-clock times / «Сегодня выйдет»** — sidecar has no `episode.published_at` / `next_episode_at`; sections stay empty by contract (not filled from catalog dates).
3. Visual screenshot matrix (1440/768/390) not captured — no chromium/playwright binary.

ANIMEDIA_FOLLOWUP_CAN_BE_CLOSED=NO
