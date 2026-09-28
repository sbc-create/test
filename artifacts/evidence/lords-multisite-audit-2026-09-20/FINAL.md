# Phase A final (audit-only)

at_utc: 2026-09-20T09:25:11.502342+00:00
HEAD: ad54ffc39c2804b97dfb1dcb0f43ab970b58bf09
PLAYER_FIX_HEAD ancestor: True
routes_live: 132
error_class: {'ok': 111, 'internal_link_404': 12, 'expected_404': 3, 'redirect': 6}
HTTP_5XX_COUNT: 0
INTERNAL_LINK_404_COUNT: 12 (includes country facets + legacy /films|/cartoons seeds)
SOFT_404_COUNT: 0
EXPECTED_404_COUNT: 3
SEED_SERIES_2016_STATUS: 200
SEED_COUNTRY_UK_STATUS: 404 (path); query form 200
PHASE_B: start with shared country fix, then site-scoped deploys beginning with highest-impact site (all share country bug; prioritize lords-02 as seed reporter).
