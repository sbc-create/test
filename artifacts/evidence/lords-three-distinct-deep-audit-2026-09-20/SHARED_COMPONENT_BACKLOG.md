# SHARED_COMPONENT_BACKLOG

Shared `lords-frontend.py` + per-site manifest profiles.

## Must fix (shared)

1. **Home chrome differentiation hooks** — profile-specific H1, intro, nav order/labels (F-P1-02)
2. **Collection descriptor source** — stop shared anime wording; bind copy to profile (F-P2-02, F-P2-06)
3. **Rail occupancy policy** — fill to column multiple or apply designed partial-row treatment (F-P2-03)
4. **Card title clamp** — shared CSS for `c__t` overflow (F-P2-05)
5. **Poster error handling** — only show `c__none` when image fails; fix broken src path cases (F-P2-04, F-P3-01)
6. **Adjacent rail disjointness** — utility to prevent identical slug sets on neighboring shelves (F-P2-01)
7. **Runtime resilience** — investigate why lords-02/03 502 under sequential crawl while lords-01 did not (F-P1-01)
8. **Player browser contract tests** — Playwright playing-state instance max=1 (F-P2-07)

## Do not

- Change robots/indexability
- DNS / DB / paid ops
- Fake distinctness with only CSS variables
