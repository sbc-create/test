# COMMUNITY-COMMENTS-01 — next-stage contract

Comments are NOT enabled in COMMUNITY-RATINGS-06.

```text
COMMENTS_ROWS_INSERTED_THIS_STAGE=0
COMMENTS_PUBLICATION_ENABLED=0
COMMENTS_SEO_RENDERING_ENABLED=0
FAKE_COMMENTS_INSERTED=0
```

## Future module must cover

1. Reuse SIGNED_PSEUDONYMOUS_DEVICE_V1 identity (optional later account bind)
2. Future account binding path
3. Comment text body
4. Max length limits
5. Unicode normalization
6. HTML sanitization
7. XSS protection
8. URL policy
9. Profanity/spam classifier
10. Spoiler flag + hide
11. Edit history
12. Soft delete
13. User delete
14. Moderator delete
15. Report abuse
16. Quarantine
17. Premoderation for new identities
18. Rate limits
19. Thread depth
20. Replies
21. Sorting
22. Comment usefulness votes
23. Anti-gaming for usefulness
24. Admin RBAC
25. Immutable audit
26. Privacy (no raw IP/PII in ledger)
27. Retention
28. Legal owner data requirements
29. SEO rendering only for approved comments
30. No SEO indexing of spam/quarantine/deleted
31. No invented comments
32. No LLM comments presented as users
33. Kill switch
34. Rollout 1% → 10% → 50% → 100% with owner approvals

Schema foundation may already exist dark (`community_comments*`); publication stays OFF until COMMUNITY-COMMENTS-01 owner approval.
