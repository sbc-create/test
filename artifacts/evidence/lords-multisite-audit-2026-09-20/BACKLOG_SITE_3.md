# Backlog lords-03 (1lordserials1.online)

Profile: `lords-curated` — keep visual identity independent.

## P0
1. Country facet links all 404 (shared root cause RC-COUNTRY-404) — fix shared route/index contract, verify on this site.
2. Re-validate series+year filters under load; watch for 502 recurrence (especially lords-02).

## P1
3. Compact filter UX for **this** profile only (dropdown/chips contract).
4. Refresh template-manifest so header artifact sha == disk (lords-02/03).
5. Recommendation module live gates (similar/popular weekly snapshot).
6. Card visual matrix screenshots @1440/768/390.

## P2
7. Legacy redirects `/films/`→`/movies/`, `/cartoons/`→`/animation/`.
8. Player live full-bleed-v1 on ≥1 film + ≥2 series + episode route.

## Deploy rule
Site-scoped cycle: tests → stage → rollback point → restart **only** `lords-03` unit → two stable live runs before next site.
