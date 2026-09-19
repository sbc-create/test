AMD_PERMISSION_STATUS=NOT_PROVIDED
AMD_SOURCE_STATE=BLOCKED_PENDING_WRITTEN_PERMISSION
AMD_PRODUCTION_INGESTION=0

# Evidence search (Stage 2)

Searched worktree for written owner permission covering AMD.online commercial
reuse, derivative rating formula, attribution, rate limits, and deletion.

**Result:** no such document found.

Public robots.txt allows crawling of detail pages (`User-agent: *` with limited
Disallow paths). Public accessibility ≠ commercial reuse permission.

Bounded Stage 2 technical probe (max 3 GET):

1. `https://amd.online/robots.txt` → 200
2. `https://amd.online/` → 200
3. one detail page → 200; selectors confirmed

Bulk live canary: **not started**.
