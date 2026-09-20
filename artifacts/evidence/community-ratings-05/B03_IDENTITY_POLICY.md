# Identity policy — COMMUNITY-RATINGS-05

## Production authentication status

Yummy Prisma schema has **no** User/Session/Account models for visitor login.
Admin moderation uses a separate HMAC cookie (`yami_moderation`), unsuitable as a voter identity.

```text
PRODUCTION_ACCOUNT_IDENTITY_AVAILABLE=0
PUBLIC_NATIVE_WRITES_ENABLED=0
```

## Stage05 approach

* Complete write API + antifraud against **test principals** (`canary-cr05-…`).
* Do not enable ordinary visitor writes.
* Store only opaque `actor_id` in the vote ledger (no email/IP/UA/fingerprint).
* Optional abuse signal: rotating HMAC of IP prefix (never raw IP in ledger/evidence).

## Owner options for a later public-write stage

### Option A — account-based

* Require a real Yummy account subject id.
* One active vote per `(rating_space, title, account_id)`.
* Pros: accountable; cons: needs auth product work.

### Option B — privacy-safe pseudonymous

* Session-bound salted/peppered pseudonym with documented rotation/retention.
* Not raw IP, not browser fingerprint as sole identity.
* Pros: lower friction; cons: requires privacy review + CSRF/session hardening.

Neither option is activated in Stage05.
