# COMMUNITY-COMMENTS-01 — next stage handoff

Ratings Stage05 leaves comments dark.

```text
COMMENTS_SCHEMA_READY=1
COMMENTS_PUBLICATION_ENABLED=0
COMMENTS_SEO_RENDERING_ENABLED=0
COMMENTS_WRITE_ENDPOINT_ENABLED=0
COMMENTS_ROWS_INSERTED=0
```

## Compatibility verified

* Shared subject identity may later bind ratings and comments;
* comment id ≠ vote id;
* deleting a vote must not delete comments;
* deleting a comment must not mutate rating aggregates;
* moderation roles remain separable.

## Next stage must cover

* publication / edit / delete;
* reply threads;
* moderation queue + reports;
* antispam / toxicity / spoiler marks;
* age limits and PII;
* SEO rendering policy (separate owner decision);
* retention + audit;
* never co-ship first public rating write with first comment write.
