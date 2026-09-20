# Owner public-write rollout packet — COMMUNITY-RATINGS-05

```text
READY_FOR_OWNER_PUBLIC_WRITE_APPROVAL=1
PUBLIC_NATIVE_WRITES_ENABLED=0
```

## Variants

### A. Native-only Yummy (recommended immediate)

* Public display: only real Yummy native votes;
* Prior/Shikimori hidden;
* Identity: Option A account-based **or** Option B privacy-reviewed pseudonym (see B03).

### B. Native + authorized prior

* Requires separate source-policy grant for open-index Shikimori;
* Attribution + preliminary label + prior strength disclosure;
* Shikimori used at most once; never via animedia_projected.

### C. Identity choice

* Account-based vs privacy-safe pseudonymous — risks and rollback documented in B03.

## Rollout steps

1. shadow writes  
2. supervised principals  
3. internal allowlist  
4. 1%  
5. 10%  
6. 50%  
7. 100%

Each step requires ≥2 stable windows with:

* security errors=0;
* aggregate mismatches=0;
* duplicate active votes=0;
* canary residue=0;
* indexability unchanged;
* rollback verified.

## Owner approval must pin

* FINAL_CODE_HEAD (full SHA);
* code-tree digest;
* migration digest;
* artifact SHA;
* domain + rating space;
* identity mode;
* rollout percentage;
* start/end window;
* kill switch + rollback command.
