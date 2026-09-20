# Source permission matrix — COMMUNITY-RATINGS-02

OWNER_POLICY_DECISION_ID=COMMUNITY-RATINGS-POLICY-V1-20260920  
OWNER_POLICY_APPROVAL_SCOPE=SHADOW_AND_PUBLIC_READ_ONLY  
NATIVE_PUBLIC_WRITES_APPROVED=false

Permissions are **not** interchangeable. Fetch ≠ existing-use ≠ production-storage ≠ public-display.

## Matrix

| SOURCE_ID | ARTIFACT / DB | RECORDS | PROVENANCE | FETCH_NEW | USE_EXISTING | STORE_PROD | DISPLAY_PUBLIC | ATTRIBUTION | DECISION |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| amd_online | ratings.sqlite obs + Stage2/3 evidence | 100 | URL+sha+adapter | **0** NOT_PROVIDED | CLOSED_CANARY last-good retain | already present; retain only | **CLOSED_NOINDEX display historically allowed; PUBLIC_INDEXED=0**. Exact site crosswalk **0** → **no public projection** | AMD attribution if shown | SKIP_PUBLIC_PROJECTION |
| shikimori | ratings.sqlite obs + Stage5 | 125 | URL+sha+adapter+MAL_ID_CROSSWALK | policy allows; **this stage: no new crawl** | YES (adapter grant) | already present; CONTRACT_GATE provenance retained | CLOSED_NOINDEX + owner SHADOW_AND_PUBLIC_READ_ONLY; **exact nova:UUID match to Animedia details = 125** | Label «Shikimori»; docs/rights/shikimori-ratings.md | AUTHORIZED_PUBLIC_READ_ONLY |
| provider_feed_imdb | site details `ratings_by_source` | catalog | provider feed | N/A (feed) | YES granted 2026-09-06 | via catalog feed | YES (existing vitrine) | IMDb | KEEP_EXISTING_VITRINE |
| provider_feed_kinopoisk | site details | catalog | provider feed | N/A | YES | via catalog | YES | КП | KEEP_EXISTING_VITRINE |
| animemedia | — | 0 | unverified | 0 | 0 | 0 | 0 | — | DISABLED |
| anilist/simkl/kitsu | — | 0 | absent | 0 | 0 | 0 | 0 | — | ABSENT |

## AMD detail

```text
AMD_FETCH_PERMISSION=0
AMD_EXISTING_ARTIFACT_USE_PERMISSION=1_LAST_GOOD_RETAIN
AMD_PRODUCTION_STORAGE_PERMISSION=1_RETAIN_NO_NEW_IMPORT
AMD_PUBLIC_DISPLAY_PERMISSION=0_NO_EXACT_SITE_CROSSWALK
```

Evidence: `artifacts/evidence/ratings-ingestion-02/AMD_PERMISSION_STATUS.md`, Stage5 `SOURCE_POLICY.json`.

## Shikimori detail

```text
SHIKIMORI_FETCH_PERMISSION=1_POLICY_BUT_NO_CRAWL_THIS_STAGE
SHIKIMORI_EXISTING_USE_PERMISSION=1
SHIKIMORI_PRODUCTION_STORAGE_PERMISSION=1_WITH_PROVENANCE_CONTRACT_GATE
SHIKIMORI_PUBLIC_DISPLAY_PERMISSION=1_CLOSED_NOINDEX_READ_ONLY
```

## Implications

- Do **not** network-fetch AMD or Shikimori in this stage.
- Do **not** write external scores into native vote ledger.
- Do **not** project AMD onto Animedia/Yummy title pages (no exact mapping).
- Do project Shikimori (125) as external badges only.
- Provider-feed KP/IMDb remain as today (not community native).
