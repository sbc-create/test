AMD_PERMISSION_STATUS=NOT_PROVIDED
AMD_CLOSED_CANARY_INGESTION=ALLOWED
AMD_CLOSED_NOINDEX_PUBLICATION=ALLOWED
AMD_PUBLIC_INDEXED_PUBLICATION=BLOCKED_PENDING_SEPARATE_APPROVAL
AMD_SOURCE_STATE=CLOSED_CANARY_ALLOWED
AMD_PRODUCTION_INGESTION=0
AMD_PUBLIC_INDEXED_PUBLICATION_ALLOWED=0

# Stage 2 correction (2026-09-19)

Written commercial/indexed permission is NOT required for closed technical canary.
It remains a separate gate only before mass public indexed publication (Stage 3+).

Allowed now:
- read-only AMD detail canary up to 100 unique titles
- isolated DB write of accepted baselines
- candidate snapshot for closed noindex animedia.icu / animedia.space
- display AMD score/votes/components + attribution
- animedia_blend_v1 with local votes
- rotation/sort verification

Still blocked:
- public indexed publication
- production scheduler enable
- CAPTCHA/DDOS bypass / proxy rotation / AMD voting endpoints
