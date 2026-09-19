# User vote contract — Stage 3

## Separation

| store | content |
| --- | --- |
| `rating_observations` / `rating_current` | External AMD (and separately Shikimori) baselines |
| `rating_vote_event` | Append-only user vote history |
| `rating_vote_current` | One active vote per `(scope, site_id, title, voter)` |
| `rating_local_aggregate` | Accepted local sum/count |
| `rating_combined_projection` | `animedia_blend_v1` result |

- AMD and Shikimori votes are **never** summed together
- One user vote never mutates the stored AMD baseline row
- Fake votes allowed **only** in unit tests

## Event fields

```text
event_id
site_id
canonical_title_id
pseudonymous_user_id
score            # 1..10
created_at
supersedes_event_id
idempotency_key
actor_type
```

## Rules

- Idempotent create with same key → no duplicate
- Update supersedes prior event (audit retained)
- Delete revokes active vote
- No raw IP / email / PII in ratings snapshot
- Rate limit + quarantine flags in `LocalVotesService`

Implementation: `factory/ratings/local_votes.py` (Stage 2, retained).
