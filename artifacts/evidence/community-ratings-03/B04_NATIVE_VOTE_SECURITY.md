# B04 — native vote security (no second ledger)

Uses existing `CommunityVotesService` + `community_votes` / `community_vote_events` / `community_aggregates`.

Verified in B05 integrity suite + Animedia canary:

- score integer `1..10`
- exact-mapped subject for live canary title
- uniqueness `(rating_space_id, subject_id, actor_id, dimension)`
- canary actor = salted technical pseudonym (`canary-cr03-…`); no IP/UA/email/name/fingerprint in vote rows
- idempotency key replay → 0 extra events
- concurrent duplicate same key → 1 accepted row
- vote + aggregate in one transactional path (service)
- immutable `community_vote_events` retained after hard-delete of canary vote rows
- spaces isolated: Animedia canary did not insert Yummy votes
- kill switches remain off: `RATINGS_NATIVE_WRITE_ANIMEDIA=0`, `RATINGS_NATIVE_WRITE_YUMMY=0`
- admin: `RATINGS_ADMIN_READ_ENABLED=1`, `RATINGS_ADMIN_MODERATION_WRITE_ENABLED=0`

```text
ADMIN_EXTERNAL_RATING_EDIT_ENABLED=0
ADMIN_MANUAL_VOTE_INSERT_ENABLED=0
ADMIN_MODERATION_WRITE_ENABLED=0
PUBLIC_NATIVE_WRITES_FOR_ORDINARY_USERS=0
```
