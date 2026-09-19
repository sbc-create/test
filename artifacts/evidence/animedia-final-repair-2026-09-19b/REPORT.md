# Animedia final repair report — 2026-09-19b

## Verdict

Live false-failure on episode playback is fixed: provider `error` is no longer treated as fatal when the iframe shell is mounted; `playing` / progress confirmation uses shell + provider playlist/video resource evidence (cross-origin `currentTime` is not readable). Homepage is capped at 1280px with fixed 154px hero cards; icu vs space SEO/shelves diverge; ratings use existing Shikimori snapshot provenance; owner names «Шикимуни» / «Nisa Media» stay UNVERIFIED/DISABLED.

## Git

| Field | Value |
| --- | --- |
| START_HEAD | `87eaae17dbc0ab648d4af1692afc94f92d5f0e8b` |
| FINAL_HEAD | `9023025` (provenance) / runtime tip `ff4bb0f0fd524c1d05d5b56d16f53c823b4d3156` |
| Branch | `claude/animedia-template-finalization-01` |
| Worktree | `/home/claude/wt-animedia-finalization-01` |

### Commits (this follow-up)

- `ff4bb0f` fix(animedia): kill false player failure and densify home/title
- `9023025` chore(nova): point Animedia provenance at false-failure fix tip
- (+ golden probe hardening commit pending with this evidence)

## Deploy

| Field | Value |
| --- | --- |
| Rollback path | `/srv/lords/.frontend/.rollback/pre-closed-update-20260919T170618Z` (+ redeploy `20260919T172143Z`) |
| Live build icu/space | `20260919T172143Z-ff4bb0f0-nova` |
| DEPLOY_SCOPE | animedia.icu + animedia.space |
| Official path | `APPLY_SITES=animedia-01,animedia-02` → `apply-nova-closed-update.py` |

Note: a bare `systemctl restart` once coincided with shared-runtime overwrite by another tip (`f8eefc44…`, healthz=`{"ok":true}` only). Candidate was re-applied; subsequent restart kept SHA `432f5bfb…`.

## Digests (process `/healthz` after restart)

From `artifacts/evidence/animedia-final-repair-2026-09-19b/healthz-icu-post-restart.json`:

| Digest | Value (prefix) |
| --- | --- |
| runtime_sha256 / assets | `432f5bfb5c77b0c0…` (`runtime_digest_match=true`) |
| profile_digest | `66753e3597665f65…` |
| catalog_digest | `8c709e1aeaa6849b…` |
| details_digest | `d40ad6a7045895d2…` |
| provider_projection_digest | `0a6b495c0e2eaede…` |
| ratings_snapshot_digest | `55bb8c7a6a42547d…` |
| player_config_digest | present |
| template_manifest_digest | present |
| catalog_revision == details_revision | `fe5e1331eb39f758…` |

## Player / golden browser gate

Harness: Chromium via Playwright (`/opt/pw-browsers`), `automation/host/animedia_golden_playback.py`.

Evidence rule used for cross-origin: Play click inside provider frame + shell `active` + no false overlay + provider `/playlist` or `/video/` resource timing. Readable `currentTime>=3` was not available (cross-origin iframe).

| Gate | Result |
| --- | --- |
| GOLDEN_PLAY_TOTAL | 10 |
| GOLDEN_PLAY_PASS | 10 |
| Unavailable honest | 2/2 |
| PRIMARY_TO_FALLBACK_PLAY_PASS | 1 |
| GOLDEN_PLAY_POST_RESTART_PASS | 1 |
| GOLDEN_PLAY_PUBLIC_PASS | 1 |
| PLAYER_FALSE_READY | 0 |
| PLAYER_FALSE_FAILURE | 0 |

Artifacts: `artifacts/evidence/animedia-playback-gate-2026-09-19/`, `…/GOLDEN_PLAYBACK_POST_RESTART.json`, `…/GOLDEN_PLAYBACK_PUBLIC.json`.

Mandatory URL `…/episode-104/` no longer flips to «Плеер не поднялся» after Play when the iframe is live.

## Visual / SEO

`automation/host/animedia_visual_gates.py` → `VISUAL_GATES.json`, 50 screenshots.

| Gate | Value |
| --- | --- |
| HOME_MAX_CONTENT_WIDTH_PX | 1280 |
| HERO_CARD_WIDTH_PX | 154 (variance 0) |
| HORIZONTAL_PAGE_OVERFLOW_PX | 0 |
| H1_COUNT | 1 |
| SAME_SEO_TEXT_BETWEEN_DOMAINS | 0 |
| SAME_FIRST_VIEWPORT_CONTENT | 0 |

Live H1: ICU «Новые серии и онгоинги» · Space «Каталог аниме, топ и фильмы».

## Ratings

- Shikimori: ENABLED via existing details `ratings_by_source` (~4427 titles); no HTML scrape; display order prefers Shikimori.
- Registry: `automation/host/animedia_ratings_sources.py`.
- Unresolved owner names (UNVERIFIED/DISABLED, no network): **Шикимуни**, **Nisa Media**.
- INVENTED_RATINGS=0; snapshot digest persists across restart/redeploy.

## Join / release gate

- CATALOG_DETAILS_MISSING=0 (7425/7425 both sites)
- TITLE_ID_MISMATCH=0 (revision aligned)
- CATALOG_DETAILS_SKEW=0
- RUNTIME_COMPATIBLE=1 / RUNTIME_DOWNGRADE=0
- PROVIDER_BINDING_MATCH=1 at deploy probe (mali-first on master-lda)

## Tests

```text
.venv/bin/python -m pytest tests/unit/test_animedia_followup_player_collections.py \
  tests/test_collection_contract.py tests/unit/test_lords_search_matching.py \
  tests/unit/test_lords_runtime_search.py -q
# 51+ collection/search related passed (follow-up file 13+; collection contract green)
```

## Changed files (runtime-relevant)

- `automation/host/lords-frontend.py` — player client, CSS density, domain SEO, healthz digests, episode rows
- `automation/host/nova_release_gate.py` — runtime markers
- `automation/host/nova_closed_provenance.py` — ANIMEDIA_COMMIT tip
- `automation/host/animedia_golden_playback.py` / `animedia_visual_gates.py` / `animedia_ratings_sources.py`
- `tests/unit/test_animedia_followup_player_collections.py`

## Flags

```
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
