# Lords repair WORKLOG — 2026-09-19

## Baseline (re-measured)

| Field | Value |
| --- | --- |
| worktree | `/home/claude/wt-lords-integration-canary-01` |
| branch | `cursor/lords-integration-canary-01` |
| HEAD | `6a44a23cd349694da6dfcb096e94a4b1a6cde880` |
| live build_id | `20260919T074636Z-a67bf79d-nova` |
| live Template marker | `lords 1.1.0 · a67bf79d` |
| live frontend sha256 | `20772a574f0542e9d71bd82fe7f974d526723612a8b1f9d54cf2bf8b1453d196` (bytes = cc83fd7 tip; manifest still a67bf79) |
| X-Robots-Tag | `noindex, nofollow` |
| robots.txt | `Disallow: /` |

Note: marker `a67bf79d` is **live lords-02 manifest**, not current worktree HEAD. Frontend file on disk already includes avail-gate + later Animedia CSS (shared runtime).

## Confirmed live defects

- `matrix` → top hit «Маори» (soft Hamming match on `maori`)
- `Матрица` → relevant Matrix titles
- `/movies/`, `/series/`, `/animation/`, `/genres/` → 404
- `/genre/<code>/` redirects to catalog query (OK as alias) but path routes missing
- old slug `domokhozyaykoy` → 404
- country/sort query silently ignored (code inspection)
- home sections use `.tabs__pill` not H2
- footer: «тестовая витрина» + Template line

## Plan (max 3–4 commits)

1. Functional: search ranking, filters, clean routes, aliases, collections, player hub, home sections
2. Chrome: mobile header, footer, layout contract tweaks, SEO overlay stubs
3. Tests + evidence
4. Provenance + lords-02 deploy

## Progress

- [x] baseline inventory
- [ ] implement functional package
- [ ] implement chrome/SEO
- [ ] tests
- [ ] deploy + live verify
