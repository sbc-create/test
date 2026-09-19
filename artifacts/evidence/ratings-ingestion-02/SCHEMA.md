# Schema Stage 2

Migration: `migrations/0003_ratings_local_amd.py` (isolated SQLite only).

## Entities

| Logical | Table |
| --- | --- |
| external_rating_observation | `rating_observations` (+ component_scores, permission_version, quality_flags, source_url) |
| external_rating_current | `rating_current` (+ component_scores, quality_flags, degraded) |
| title_source_mapping | `title_source_mappings` (Stage 1) |
| rating_vote_event | `rating_vote_event` |
| rating_vote_current | `rating_vote_current` |
| rating_local_aggregate | `rating_local_aggregate` |
| rating_combined_projection | `rating_combined_projection` |
| ratings_daily_run | `ratings_daily_run` |
| ratings_daily_outcome | `ratings_daily_outcome` |
| idempotency | `rating_idempotency` |

Sources remain separate: `shikimori`, `amd_online`, local votes, provider-feed.
