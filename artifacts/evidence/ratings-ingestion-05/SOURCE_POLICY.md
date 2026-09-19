# SOURCE_POLICY — Stage 5

## Shikimori

```json
{
  "source": "shikimori",
  "access_method": "official_graphql",
  "public_api_or_html": "graphql_api",
  "robots_status": "robots_disallow_/api/*_for_crawlers; official_API_client_per_docs/rights",
  "terms_status": "CONTRACT_GATE_attribution_long_term_storage_undocumented",
  "permission_status": "granted_for_factory_ratings_adapter",
  "owner_use_approval": "docs/rights/shikimori-ratings.md Stage1+; HTML scrape forbidden",
  "allowed_rate": "<=2 rps operational (upstream 5 rps / 90 rpm)",
  "concurrency": 1,
  "challenge_policy": "circuit_on_401_403_schema_drift; no_html_fallback",
  "publication_scope": "CLOSED_NOINDEX_ANIMEDIA_UNTIL_INDEXING_DECISION",
  "decision": "SHIKIMORI_SOURCE_POLICY_RESOLVED",
  "new_fetches_allowed": true,
  "SOURCE_POLICY_RESOLVED": "YES",
  "API_CONTRACT": "POST https://shikimori.io/api/graphql; animes(ids:String CSV, limit:Int<=50); fields id,malId,name,russian,score,scoresStats{score,count},updatedAt,url",
  "ATTRIBUTION_CONTRACT": "docs/rights/shikimori-ratings.md; score labelled Shikimori not MAL; CONTRACT_GATE attribution/long-term storage undocumented — provenance retained",
  "RATE_LIMIT_RPS": 0.1,
  "CONCURRENCY": 1,
  "FIELDS_ALLOWED": [
    "id",
    "malId",
    "name",
    "russian",
    "score",
    "scoresStats",
    "updatedAt",
    "url"
  ],
  "FIELDS_REJECTED": [
    "html_scrape",
    "rest_v1",
    "rest_v2",
    "mal_score_as_shikimori",
    "browser_ua_spoof"
  ],
  "stage5_override_note": "Stage5 pilot caps RPS at 0.1 regardless of upstream 5 rps / operational 2 rps"
}
```

## AMD

```json
{
  "source": "amd.online",
  "access_method": "public_html_detail_get",
  "public_api_or_html": "html_detail_only",
  "robots_status": "detail_html_not_disallowed; engine/user paths disallowed (robots.txt 2026-09-19)",
  "terms_status": "no_written_reuse_grant_on_file",
  "permission_status": "NOT_PROVIDED",
  "owner_use_approval": "closed_canary_only_stage2_3; recurring_not_approved",
  "allowed_rate": "0.1 rps (if authorized)",
  "concurrency": 1,
  "challenge_policy": "AUTO_STOP_NO_BYPASS",
  "publication_scope": "CLOSED_NOINDEX_ONLY_WHEN_AUTHORIZED",
  "decision": "AMD_SOURCE_DISABLED_PERMISSION_MISSING",
  "new_fetches_allowed": false,
  "AMD_SOURCE_STATUS": "DISABLED_PERMISSION_MISSING",
  "AMD_NETWORK_CALLS": 0,
  "AMD_RECURRING_FETCHES": 0,
  "AMD_LAST_GOOD_PRESERVED": 1,
  "forbidden_actions": [
    "AMD GET",
    "HTML fetch",
    "robots probe",
    "canary",
    "refresh",
    "parser test via network"
  ]
}
```

## Isolation gates

```json
{
  "AMD_SOURCE_STATUS": "AMD_SOURCE_DISABLED_PERMISSION_MISSING",
  "SHIKIMORI_SOURCE_STATUS": "SHIKIMORI_SOURCE_POLICY_RESOLVED",
  "AMD_SOURCE_AUTHORIZED_OR_DISABLED": "YES",
  "SHIKIMORI_SOURCE_POLICY_RESOLVED": "YES",
  "AMD_NEW_FETCHES_ALLOWED": "NO",
  "SHIKIMORI_NEW_FETCHES_ALLOWED": "YES_POLICY",
  "AUTHORIZED_SOURCE_COUNT": "1",
  "ACTIVE_SOURCE_COUNT": 1,
  "ACTIVE_SOURCE": "shikimori",
  "AMD_CALLS": 0,
  "UNAUTHORIZED_SOURCE_CALLS": 0,
  "SOURCE_RATE_LIMIT_CONFIGURED": 1,
  "SOURCE_CONCURRENCY": 1,
  "SOURCE_RATE_LIMIT_RPS": 0.1
}
```
