# Card audit (Phase A)

Phase A sampled title cards from home/nav (5 titles × 3 sites) — all returned HTTP 200.
Full geometry matrix (columns, overflow, stretch, rating-as-zero) requires screenshot/Playwright
pass in Phase B per profile; source still has block-03 card regression tests in repo.

Observed:
* CARD_BROKEN_LINKS on sampled home titles: 0
* Poster URLs from catalog `poster` field when present
* Rating source must not render missing as 0 (existing unit tests)

Deferred to Phase B live visual matrix: COLUMN counts, LAST_ROW_STRETCH, TITLE_OVERFLOW, HORIZONTAL_OVERFLOW.
