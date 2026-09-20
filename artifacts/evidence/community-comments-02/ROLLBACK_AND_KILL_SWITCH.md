# Rollback and kill switch — COMMUNITY-COMMENTS-02

## Kill switch capabilities

1. `block_writes` — reject new creates
2. `hide_new_public` / `force_pending_hidden` — new comments → `PENDING_MODERATION_DEGRADED`
3. `stop_worker` — Qwen worker no-ops
4. `keep_reading_approved` — previously approved remain readable when module partially on
5. `hide_module` — hide entire comments UI

Persisted under `COMMUNITY_COMMENTS_KILL_SWITCH_PATH` (default var path) with audit JSONL + DB table `community_comment_kill_switch_audit`.

## Drill

`drill_and_restore()` engages all restrictive flags then restores defaults. Covered by unit tests and fake canary.

## Rollback

- Additive schema only (`community_comments_v2`); no destructive migrations.
- Soft-delete only; Qwen never physically deletes bodies.
- Ratings tables untouched; ratings rollout ceiling remains 1%.
- Feature flags default OFF: `COMMENTS_PUBLICATION_ENABLED`, `COMMENTS_QWEN_POSTMOD_ENABLED`, `COMMENTS_QWEN_WORKER_ENABLED`, `COMMENTS_SEO_RENDERING_ENABLED`.
