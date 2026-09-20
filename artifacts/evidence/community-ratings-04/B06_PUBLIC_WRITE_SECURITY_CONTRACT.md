# Public-write security contract (Stage05 prep) — not enabled

```text
PUBLIC_NATIVE_WRITES_ENABLED=0
```

Required before gradual public write pilot:

1. Identity: authenticated and/or session-bound salted pseudonymous voter ID
2. Uniqueness: one active vote per (user, title, rating_space, dimension)
3. CSRF protection + Origin/Referer/SameSite validation
4. Rate limit + abuse detection + kill switch (scoped)
5. Idempotency key + concurrent update locking
6. Preview equals commit; read-your-write projection
7. Retract → audit tombstone without excess PII (no raw IP/UA/email/name/fingerprint)
8. IP retention only as salted hash with documented TTL (if required for abuse)
9. Admin remains read-only: EXTERNAL_SCORE_EDIT=0, MANUAL_VOTE_INSERT=0, AGGREGATE_OVERRIDE=0
10. Monitoring + immutable daily report + rollback path
11. Structured AggregateRating only after separate vote-threshold owner decision
12. Comments remain a separate stage (never co-ship with first public vote write)
