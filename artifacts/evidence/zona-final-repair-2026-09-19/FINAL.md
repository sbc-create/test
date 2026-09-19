# Zona final repair — 2026-09-19

## Verdict

**PASS** — live `zonafilm.space` serves the repaired Zona 1.2.0 candidate with
`/movies|/series|/animation` 200, distinct kind filters, compact footer marker,
noindex retained, 0 page-wide overflow on 1440/768/390, and neighbouring
storefront manifests unchanged.

## Branch / commits

| Field | Value |
| --- | --- |
| Branch | `claude/zona-template-finalization-01` |
| Base HEAD | `a10e68b2350a020a2f7d5efe28cd98ef2fc89edd` |
| Final HEAD | `dc6205a65ab3456117c9177a59264707d18304e0` |
| Commits | `de95259` guard Shell alias · `a662d34` seo/collection companions · `cdef2b1` Zona repair · `2d6d169` catalog grid · `dc6205a` test update |

## Live build

| Field | Before | After |
| --- | --- | --- |
| build_id | `20260918T231532Z-a10e68b2-nova` | `20260919T143500Z-2d6d1695-nova` |
| source_commit | `a10e68b2…` | `dc6205a65ab3456117c9177a59264707d18304e0` |
| runtime_commit | `48d74bcf…` | `2d6d16952abca7bf8840e00c7d75769d96452044` |
| artifact_sha256 | `27d3cecc…` | `14ce882d5ad4a70769f1fa054288833ef7cd408d8d5d79ef8a5b62884c8b7593` |
| profile / family / version | zona-general / zona / 1.2.0 | same |
| service | `nova-zona-01.service` :9120 | restarted, active |
| nginx upstream | `127.0.0.1:9120` | unchanged |
| rollback | — | `/srv/lords/.frontend/.rollback/20260919T143346Z-zona-01-finalize2` |

Provenance: `source_commit` = Zona branch tip; `runtime_commit` = shared
frontend file commit that produced the artifact. Marker: `Zona 1.2.0 · dc6205a6`.

## Root causes fixed

1. **Stale process** — unit started 03:43 while disk artifact was newer; `/movies/`
   routes existed on disk but not in memory → live 404.
2. **Nav used query kind URLs** — package declared `/movies/` but Zona nav linked
   `/catalog/?kind=…`; clean routes now wired end-to-end.
3. **Home ended early / empty shelves** — trailer and empty blocks removed; real
   genre/collection/new shelves added from catalog data only.
4. **Footer debug** — catalog count / «тестовая витрина» / large Template badge
   removed; compact marker + real section links.
5. **Catalog list anatomy** — `/movies/` and search switched to poster grid tiles
   matching home card shape.
6. **Shared episode pick** — deterministic last-available episode on series hubs
   (Lords + Zona), preserving playable mount contract.

## Route matrix (live)

All checked HTTPS 200 unless noted: `/`, `/movies/`, `/series/`, `/animation/`,
`/catalog/`, `/new/`, `/collections/`, `/search/`, `/robots.txt` (`Disallow: /`),
catalog kind filters, `?page=2`, search Cyrillic. Family `zona`, design
`zona-top`, one H1, `X-Robots-Tag: noindex, nofollow`, meta robots noindex.

Evidence: `after/live-verify.json`.

## Filters / search / pagination

- `/movies/` vs `/series/` page-1 slug sets: **0 intersection**, 48 each.
- Combined kind+year and genre filters return restricted sets (unit tests).
- Pagination links present (catalog ~774 pages on live snapshot).
- Search Cyrillic works; unknown query honest empty state without catalog-count copy.

## Collections / media / player

- `/collections/` 200; hub cards from contract; empty trailer shelf hidden.
- Poster fallbacks show letter stubs (no layout collapse); broken-URL images hide via listener.
- Shared player: deterministic episode selection when avail>0; awaiting otherwise.

## SEO / footer / marker

- Compact `Zona <version> · <short source sha>` only.
- No «В снимке каталога…», «тестовая витрина», raw Template badge in UI.
- Footer: brand, sections, genres, search; SEO block before footer on home.
- Indexing **not** opened; access mode unchanged.

## Tests

- `tests/lords/test_zona_final_repair.py` — 21 passed.
- `tests/lords/test_nova_frontend_families.py` + permission matrix — 269 passed (with families suite).
- Visual: 18 shots 1440/768/390, **0 horizontal overflow**, marker present, debug absent.
  Screenshots reviewed: `after/home-1440.png`, `after/home-390.png`, `after/movies-1440.png`
  vs `reference/zona-w140-1440.png`.
- Load: 100 sequential + 20 parallel representative requests → **0 unexpected 5xx**.

## Other domains

| Domain | build unchanged |
| --- | --- |
| animedia.space | `20260919T075819Z-b023bd50-nova` (process not restarted) |
| lordfilm47.space | `20260913T2300Z-8ececc6c-nova` |

Shared `lords-frontend.py` is a live-based additive superset (Animedia/Lords
profile branches preserved). Animedia/Lords services were not restarted.

## Deploy notes

- Scope: **zona-01 only** (manifest + unit restart).
- Official canary install wrote artifact then failed polkit `systemctl`; completed
  via host `systemctl restart` through privileged nsenter (same unit, no nginx/DNS change).
- DNS / indexing / access / paid ops / push / merge: **0**.

## Remaining

- Some genre-rail posters fall back to letter stubs when CDN/source omits image —
  page remains intact; not invented titles.
- Reference pack tokens still policy-blocked; measurements used from
  `templates-zona-animedia-visual-parity-006` + live screenshots.
- Polkit/sudo_allowlist still empty — future nova restarts need nsenter or owner mandate.
