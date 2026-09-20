# Zona Pass7 — Content Freshness FINAL

## Verdict

```text
VERDICT=PASS_CONTRACT_NEEDS_TWO_WEEKLY_CYCLES
BRANCH=claude/zona-template-finalization-01
START_HEAD=22ee5ab90ff6b4a8209b735858495a7691efb25c
FEATURE_HEAD=d35e6349b2fd2ed64a3adb700cf3971963694489
REPORT_HEAD=563159a37aeff7b6e0e0b15faec655d83dafcf47
FINAL_HEAD=563159a37aeff7b6e0e0b15faec655d83dafcf47
COMMITS=d35e634 (contracts+tests); 9c695b0 (evidence); 563159a (FINAL_HEAD)
TESTS=37 passed targeted (pass7 freshness + pass5/6 regression subset)

LIVE_BUILD_BEFORE=20260919T224255Z-88cd272f-nova
LIVE_BUILD_AFTER=20260920T092117Z-dbaf9a4d-nova
DEPLOY_PERFORMED=1
DEPLOY_SCOPE=zona-01-only
ROLLBACK_PATH=/srv/lords/.frontend/.rollback/20260920T091253Z-zona-01-pass7
SOURCE_ARTIFACT_DIGEST_MATCH=1
ARTIFACT_RUNTIME_DIGEST_MATCH=1
CACHE_COHERENCE_PASS=1

CATALOG_TOTAL=53548
DETAILS_TOTAL=53548
CATALOG_SNAPSHOT_BUILT_AT=2026-09-20T03:16:30Z
DETAILS_SNAPSHOT_BUILT_AT=2026-09-20T03:16:30Z
LATEST_SOURCE_EVENT_AT=INCONCLUSIVE_SOURCE_TIMESTAMP
LATEST_CATALOG_EVENT_AT=2026-09-19T11:24:10Z
LATEST_LIVE_EVENT_AT=2026-09-20T03:35:10Z
SNAPSHOT_AGE_MINUTES≈355.3161672166667

SCHEDULERS_DISCOVERED=6
SCHEDULERS_ENABLED=nova-daily-refresh,nova-catalog-refresh(skips zona),lords-content-refresh(lords-only),nova-zona-01
LAST_CONTENT_SYNC_AT=2026-09-20T03:35:17Z
LAST_CONTENT_SYNC_RESULT=ok
NEXT_CONTENT_SYNC_AT=2026-09-21T03:33:14Z
CONSECUTIVE_SYNC_FAILURES=0

NEW_MOVIE_SAMPLE_COUNT=16
NEW_MOVIE_SOURCE_TO_LIVE_P50=INCONCLUSIVE_SOURCE_TIMESTAMP
NEW_MOVIE_SOURCE_TO_LIVE_P95=INCONCLUSIVE_SOURCE_TIMESTAMP
NEW_MOVIE_SOURCE_TO_LIVE_MAX=INCONCLUSIVE_SOURCE_TIMESTAMP
NEW_EPISODE_SAMPLE_COUNT=0
NEW_EPISODE_SOURCE_TO_LIVE_P50=INCONCLUSIVE_SOURCE_TIMESTAMP
NEW_EPISODE_SOURCE_TO_LIVE_P95=INCONCLUSIVE_SOURCE_TIMESTAMP
NEW_EPISODE_SOURCE_TO_LIVE_MAX=INCONCLUSIVE_SOURCE_TIMESTAMP
CATALOG_TO_LIVE_P95=1220.065
CACHE_VISIBILITY_P95≈0 (Cache-Control:no-store + revision ETag)

NEW_MOVIES_LAST_CHANGED_AT=2026-09-20T03:35:10Z (daily publish + restart)
NEW_EPISODES_LAST_CHANGED_AT=N/A_NO_EPISODE_TIMESTAMPS
POPULAR_REFRESH_MODE=WEEKLY_SNAPSHOT
POPULAR_REQUEST_TIME_RECOMPUTES=0
POPULAR_RECOMPUTE_CADENCE=7d
POPULAR_WEEK_ID=2026-W38
POPULAR_WEEKLY_SNAPSHOT_DIGEST=0d16b8a841810a9bef268710223ef576d3c14b685144ecfad1021dae9bad32dd
POPULAR_LAST_WEEKLY_BUILD_AT=2026-09-20T09:21:17Z
POPULAR_NEXT_WEEKLY_BUILD_AT=OWNER_GATE_Mon_04:10_UTC
POPULAR_WEEKLY_PUBLICATION_COUNT=1
POPULAR_MEMBERSHIP_CHANGES_WITHIN_WEEK=0
RELATED_CONTRACT_STATUS=EXPECTED_STABLE_SECTION
COLLECTIONS_CONTRACT_STATUS=DYNAMIC_FILTERS_ON_SNAPSHOT

STATIC_TEMPLATE_SHELVES=0 (after repair)
STALE_SHELVES=0 (after repair; pre-repair live had Pass6-clobbered sixth shelf)
EXPECTED_STABLE_SHELVES=related, editorial-unavailable collections
WRONG_SORT_FIELDS=0 (after relabel; episode shelf no longer claims episode sort)
WRONG_TIME_SEMANTICS=0 (after relabel)
CACHE_INVALIDATION_FAILURES=0
HARD_CAP_AFFECTS_RESULTS=1 (rating shelves pool=400 intentional)
DUPLICATE_IDS=0
BROKEN_LINKS=0
INVENTED_TIMESTAMPS=0
INVENTED_POPULARITY_SIGNALS=0

DAILY_FRESHNESS_REPORT_READY=1
PASSIVE_MONITORING_READY=1
OBSERVATION_WINDOW_DAYS=6
LONGER_OBSERVATION_REQUIRED=1

PLAYER_GOLDEN_RUNS=not_re_run_this_pass (Pass5/6 locked; title page 200 + player section present)
RESPONSIVE_PASS=1 (locked CSS untouched)
NOINDEX_PRESERVED=1
INDEXING_OPENED=0
CONTACT_CONFIG_MISSING=1
LEGAL_CONFIG_COMPLETE=NO
DESCRIPTION_DATA_GAPS=13314

OTHER_DOMAINS_MUTATED=0
DNS_MUTATIONS=0
PAID_OPERATIONS=0
PUSH_PERFORMED=0
MERGE_PERFORMED=0
SECRETS_EXPOSED=0

ZONA_FRESHNESS_CAN_BE_CLOSED=NO
ZONA_VISUAL_FINALIZATION_CAN_BE_CLOSED=YES
ZONA_SEO_CONTENT_CAN_BE_CLOSED=NO
ZONA_OVERALL_CAN_BE_CLOSED=NO
```

## What was wrong

1. **Cross-site overwrite:** lords-01 deploy at 2026-09-19T22:51 replaced shared `lords-frontend.py`, restoring the sixth «Недавно в каталоге» shelf and genre mega-shelves while leaving `template-manifest-zona-01.json` claiming Pass6 digest.
2. **Wrong labels:** «Популярные…» was rating-among-recent; «Новые серии/эпизоды» was title `published_at` with **zero** episode timestamps in details.
3. **Cadence:** Zona updates only via `nova-daily-refresh` (~03:30 UTC). 5-minute `nova-catalog-refresh` **skips** zona-01 by design.
4. **Source lag:** authorized snapshot has no upstream event timestamp → `INCONCLUSIVE_SOURCE_TIMESTAMP`.

## What was fixed

- Honest shelf/collection titles; no invented popularity/episode claims.
- In-process snapshot reload on catalog/details mtime; `Снимок` invalidates on revision change.
- `X-Catalog-Revision` / ETag cache identity; `Cache-Control: no-store` kept.
- Zona-isolated artifact `/srv/lords/.frontend/zona-01-frontend.py` + systemd drop-in so lords deploys cannot clobber Zona.
- Permanent tests in `tests/lords/test_zona_pass7_freshness.py`.

## Owner summary (RU)

См. раздел ниже в конце ответа оператору.

## Popular WEEKLY correction (owner)

See `POPULAR_WEEKLY_CONTRACT.md`. Request-time Popular recompute removed.
Timer not enabled — owner must approve Monday 04:10 UTC schedule.
