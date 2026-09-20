# Moderation Policy V1

Status: dark-mode policy for COMMUNITY-COMMENTS-01.

## Principles

1. Soft-delete only for normal moderation (`REMOVED_BY_MODERATOR`, `DELETED_BY_USER`).
2. Edit history is immutable (append-only revisions).
3. Heuristics never auto-publish.
4. Moderators act under RBAC `moderation` (or `write`) scope.
5. No impersonation, fake inserts, or silent text rewrites.

## Statuses

| Status | Meaning |
| --- | --- |
| `PENDING` | Awaiting review / dark hold |
| `PUBLISHED` | Public (requires publication flag — currently OFF) |
| `QUARANTINED` | Held for risk / PII / abuse |
| `REJECTED` | Not allowed |
| `DELETED_BY_USER` | Author soft-delete |
| `REMOVED_BY_MODERATOR` | Moderator soft-remove |

## Queue actions

- `approve` — clear risk; in dark stage remains non-public (`PENDING` + note)
- `quarantine` — hold for review
- `reject` — terminal reject
- `remove` — soft-remove
- `restore` — back to `PENDING`
- `mark_spoiler` — set spoiler flag
- `dismiss_report` — close a report

## Forbidden

- `ADMIN_FAKE_COMMENT_INSERT`
- `ADMIN_IMPERSONATE_USER`
- `ADMIN_SILENT_TEXT_REWRITE`
- Hard delete of comment rows as a normal path
- Mutating rating votes / aggregates from comment actions

## Appeals

Appeals are out of band in V1 (operator ticket). Restore is the ledger path.
