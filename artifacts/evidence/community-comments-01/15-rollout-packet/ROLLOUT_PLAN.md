# COMMUNITY-COMMENTS-01 Rollout Plan

Dark-mode foundation only. Ratings `PUBLIC_WRITE_ROLLOUT_PERCENT` stays **1**
and is not modified by this packet.

## Stages

| Stage | Name | Comments flags | Gate |
| --- | --- | --- | --- |
| 0 | ADMIN_PREVIEW | `COMMENTS_ADMIN_PREVIEW_ENABLED=1`; publication/read/SEO/API write = 0 | Schema + unit tests green; no production inserts |
| 1 | SUPERVISED_CANARY | `COMMENTS_API_WRITE_ENABLED=1` on staging only; publication still 0 | CSRF/Origin/RBAC/PII tests; moderation queue staffed |
| 2 | 1% public read (future) | `COMMENTS_PUBLIC_READ_ENABLED` canary ≤1% | Requires owner approval + observation window |
| 3 | … | stepwise expand | Each step needs `keep` verdict |

## Gates before any 1% public comments

1. `COMMENTS_PUBLICATION_ENABLED` still 0 until explicit owner packet.
2. `PRODUCTION_COMMENTS_INSERTED=0`, `EXTERNAL_COMMENTS_REPUBLISHED=0`, `FAKE_COMMENTS_INSERTED=0`.
3. No second identity cookie; `SIGNED_PSEUDONYMOUS_DEVICE_V1` only.
4. Ratings isolation proven: comment create/edit/delete does not mutate votes.
5. Spoiler + anti-spam + moderation policies reviewed.
6. Kill switch / read-only path verified for comments API.
7. Ratings rollout percent unchanged at 1.

## Status after COMMUNITY-COMMENTS-01

- Research observations ACCEPTED: **1000** (DERIVED_ONLY; AniList).
- Dark foundation: schema/API/UI/moderation/security tests green.
- Ratings `PUBLIC_WRITE_ROLLOUT_PERCENT` remains **1**.
- Public comments remain **OFF**.

## Non-goals this packet

- Enabling public comments
- Republishing external comments
- Changing ratings canary percent
- Push / merge / deploy
