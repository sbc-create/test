# Admin boundary — COMMUNITY-RATINGS-05

## Read-only (enabled)

```text
ADMIN_READ_ENABLED=1
```

Surfaces (existing `admin_ui` / `readmodel`):

* aggregates by rating space;
* native vote counts;
* external source values + permission status;
* policy version/digest;
* projection lineage;
* quarantine queue;
* audit / vote events;
* rebuild comparison;
* crosswalk mapping status.

## Moderation actions (RBAC-gated; flag currently OFF for production mount)

```text
RATINGS_ADMIN_MODERATION_WRITE_ENABLED=0  # production flag remains 0
ADMIN_MODERATION_ENABLED=1_LIBRARY_READY
```

Allowed library operations:

* quarantine / unquarantine suspicious **native** vote (`admin_quarantine_vote`);
* rebuild aggregate from ledger;
* kill switch / read-only emergency mode on AntifraudGuard;
* revoke compromised principal (retract+quarantine).

## Explicitly forbidden

```text
ADMIN_EXTERNAL_EDIT_ENABLED=0
ADMIN_MANUAL_VOTE_INSERT_ENABLED=0
ADMIN_AGGREGATE_OVERRIDE=0
```

* no editing Shikimori/КП/IMDb/AMD scores;
* no inserting “user” votes as admin;
* no direct aggregate write bypassing ledger;
* no summing source vote counts into native N.
