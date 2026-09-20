# Community ratings — Block 00 audit & policy freeze

**STAGE:** COMMUNITY-RATINGS-AND-COMMENTS-FOUNDATION-01  
**START_HEAD:** `77af9da`  
**DB:** `/srv/site-factory/repo/var/ratings/ratings.sqlite` (read-only audit)  
**PRODUCTION_POLICY_ACTIVATION:** owner-gated (not activated this stage)

## Inventory

### External observations (immutable sources)

| source_key | rows (obs) | namespace | notes |
| --- | --- | --- | --- |
| `amd_online` | 100 | `amd_online:{id}` | Stage2/3 closed canary; recurring fetches DISABLED |
| `shikimori` | 125 | `nova:{uuid}` | Stage5 supervised; 25 overshoot retained, not pilot PASS |

Migrations present: `0002`, `0003`, `0004`. No community migration applied to production.

### Legacy local votes (0003)

Tables: `rating_vote_event`, `rating_vote_current`, `rating_local_aggregate`, `rating_combined_projection`.  
Prod counts: vote_current=0, vote_event=0, local_aggregate=0.  
API: `LocalVotesService` (library-only, no HTTP). Identity = opaque `voter_subject_id`.

### Formula today

`animedia_blend_v1` (`factory/ratings/formula.py`): **AMD baseline + local votes**.  
Shikimori does **not** participate. Name says “animedia” but math is AMD+local — **not** `animedia_native`.

### Domains / sites

| domain | site_id | brand space (Stage6) |
| --- | --- | --- |
| animedia.icu | animedia-01 | `animedia` (shared) |
| animedia.space | animedia-02 | `animedia` (shared) |
| yummyani.* | yummyani-* | `yummy` (isolated) |

### Frontend today

Lords/Animedia + Yummy UIs show **provider-feed KP/IMDb** only.  
`RatingGateway.contract()` (local/combined) is not wired into public HTML.

### Auth

No session-bound voter. Stage6 introduces actor abstraction (account / signed guest / merge).

## Three score layers (must not collapse)

1. **External source rating** — `rating_observations` / snapshot badges (Shikimori, AMD, KP, IMDb). Immutable by user votes.
2. **Native user average** — space-scoped mean of accepted community votes only (`A = S/N`).
3. **Public brand score** — versioned policy composite (Yummy: Bayesian prior + Yummy votes). Animedia native UI shows layer 2 as «Оценка Animedia».

## Name traps

| name | meaning |
| --- | --- |
| `amd_online` | External HTML adapter / source_key |
| `animemedia` | Stub UNVERIFIED — not our sites |
| `animedia` rating_space | Community native votes for Animedia brand |
| `animedia_blend_v1` | Legacy AMD+local blend — superseded for brand UI by `rating_policy_v1` |

## Dependency DAG (acyclic)

```text
external adapters → observations → rating_current → snapshot badges
community actors → vote_events → rating_votes → rating_aggregates → native UI
yummy prior uses (animedia native OR shikimori) with provenance — never both if Animedia already embeds Shikimori
comments foundation → same actors/subjects — NEVER writes rating aggregates
```

## Owner gates (this stage)

- No production DB migration apply
- No public rating activation / deploy / restart
- No scheduler enable
- No new Shikimori ingestion cycle
- No comments publication
- `rating_policy_v1` written; activation owner-gated
