# When to enable AggregateRating structured data

Keep STRUCTURED_AGGREGATE_RATING_ENABLED=0 at 1%.

Recommend enabling only after:
* ≥100 real accepted native votes on the title (or site-wide threshold owner picks)
* ≥7 days stable canary without aggregate mismatches
* antifraud quarantine review with no systemic forgery
* PUBLIC_WRITE_ROLLOUT_PERCENT=100 with owner approval
* voteCount always equals native active votes; never prior/m
