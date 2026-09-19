# Local votes

Scale: integer **1..10** (0 forbidden).

Operations: CREATE / UPDATE / DELETE(REVOKE) / MODERATION.

Rules:

- one active vote per `(canonical_title_id, voter_subject_id, scope, site_id)`
- UPDATE replaces score; count unchanged
- DELETE → REVOKED; aggregate rebuilt
- append-only `rating_vote_event`
- Idempotency-Key: same key+payload → replay; same key+different payload → 409
- QUARANTINED/REJECTED never enter aggregate
- scopes: `NETWORK`, `SITE_ANONYMOUS`
- no raw IP in rating rows

Module: `factory/ratings/local_votes.py`
