# Stage 3 — closed scale + public-index decision (NOT STARTED)

Sequential goals after Stage 2 `PASS_CLOSED_CANARY`:

1. **Two consecutive closed canary runs** (same constraints: concurrency=1,
   ≤0.1 rps, noindex animedia.icu/space, auto-stop on 403/429/challenge/parser drift).
2. **Prepare** daily capacity up to **500 titles/day** without opening public
   indexing.
3. **Daily report** `ratings_daily_v1` delivered to Qwen (configure
   `QWEN_DELIVERY`; currently `NOT_CONFIGURED`).
4. **Separate approval** for `AMD_PUBLIC_INDEXED_PUBLICATION=ALLOWED` — requires
   written permission (see `AMD_PERMISSION_REQUEST.md`). Until then remain
   `BLOCKED_PENDING_SEPARATE_APPROVAL`.

Out of scope until explicit go: production scheduler, frontend deploy, DNS/nginx,
search-indexable publication.
