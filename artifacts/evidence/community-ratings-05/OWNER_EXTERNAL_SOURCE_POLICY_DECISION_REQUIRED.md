# Owner decision required — external source policy (open-index Yummy)

```text
OWNER_POLICY_DECISION_ID=COMMUNITY-RATINGS-05-NATIVE-SECURITY-20260920
STATUS=REQUIRED_NOT_BLOCKING
```

## What is blocked without a new grant

On **open-index** `yummyani.site`:

* public Shikimori badge;
* derived/preliminary Yummy prior that includes Shikimori;
* Animedia projected/blended score used as if it were Animedia native;
* JSON-LD `aggregateRating` built from shadow prior.

Existing evidence keeps Shikimori publication scope at:

```text
CLOSED_NOINDEX_ANIMEDIA_UNTIL_INDEXING_DECISION
```

Stage05 supervised canary auth does **not** expand that scope.

## What continues without the grant

```text
SOURCE_POLICY_BRANCH=NATIVE_ONLY_SAFE_FALLBACK
```

* Yummy / Animedia **native** vote ledgers;
* write API + security suite;
* admin read / moderation;
* UI for native-only display + gated voting controls;
* observability and owner public-write rollout packet.

## Decision options for owner

| Option | Effect |
| --- | --- |
| A. Keep native-only | Safest immediate public-read path after write approval |
| B. Grant Shikimori on OPEN Yummy | Requires attribution + prior label + digest pin |
| C. Deny permanently | Native-only remains default |

Absence of grant ≠ FAIL for COMMUNITY-RATINGS-05.
