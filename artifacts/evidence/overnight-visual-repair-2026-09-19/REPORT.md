# Overnight visual repair — REPORT — 2026-09-19 (deploy + Animedia continue)

## Commits

| Hash | Role |
| --- | --- |
| `3c4a9d3` | overnight search/encoding/shelves/overflow + audit evidence |
| `9ed4ba8` / `b5c88cd` | provenance → overnight tip + tests |
| `48d74bc` | Animedia mobile hamburger + amd-aligned shelf titles |
| `dca44cb` | provenance → mobile-nav tip (worktree tip) |

Starting HEAD (this phase): `5dfc582`  
Tip HEAD: `dca44cb` (runtime bytes = `48d74bc` frontend)

## Deployed domains (official `apply-nova-closed-update.py`)

Order: lords-02 → zona-01 → animedia-01 → animedia-02, then redeploy all four after Animedia nav fix.

| Domain | site | before source/runtime | after source / runtime | build_id | rollback |
| --- | --- | --- | --- | --- | --- |
| lordserial33.biz | lords-02 | 479f7d2 / 479f7d2 | **48d74bc / 48d74bc** | `20260918T231526Z-48d74bcf-nova` | `/srv/lords/.frontend/.rollback/pre-closed-update-20260918T231526Z` |
| zonafilm.space | zona-01 | a10e68b2 / 479f7d2 | **a10e68b2 / 48d74bc** | `20260918T231532Z-a10e68b2-nova` | `.../pre-closed-update-20260918T231532Z` |
| animedia.icu | animedia-01 | b023bd50 / 479f7d2 | **b023bd50 / 48d74bc** | `20260918T231505Z-b023bd50-nova` | `.../pre-closed-update-20260918T231505Z` |
| animedia.space | animedia-02 | b023bd50 / 479f7d2 | **b023bd50 / 48d74bc** | `20260918T231520Z-b023bd50-nova` | `.../pre-closed-update-20260918T231520Z` |

`artifact_sha256` (current): `27d3ceccb2ff85550cd416b1d9a75806ef258f333eda312c747cdd62e0c59974`

Note: `apply-nova-closed-update.py --help` is **not** argparse — invoking it without `DRY_RUN=1` mutates. First accidental full apply tonight only relabeled manifests; frontend bytes already contained `3c4a9d3`. Corrected with `APPLY_SITES` + `FORCE_INSTALL_FRONTEND=1` + `DRY_RUN` for plans.

## HTTP / closed access (post-deploy)

All four: home/catalog/search/collections/new → **200**; unknown → **404**; `X-Robots-Tag: noindex, nofollow`; meta robots noindex; `robots.txt` → `Disallow: /`.  
Animedia `/sitemap.xml` → **404** (unchanged). Lords/Zona sitemap → 200 + noindex.  
Services `nova-lords-02`, `nova-zona-01`, `nova-animedia-01/02` → **active**. `nginx -t` → ok.  
`DNS_MUTATIONS=0` · `INDEXING_OPENED=0` · `DEPLOY_PERFORMED=1` (closed operator path only).

## Search (live)

| Domain | cyr | latin | slug/mixed |
| --- | --- | --- | --- |
| Lords | матрица 8 | matrix 1 | slug/mixed hit |
| Animedia | наруто 2 | naruto 2 | Naruto 2 |
| Zona | аватар 17 | avatar 17 | — |

## Filters / encoding

- `kind`/`genre` hrefs percent-encoded (no raw Cyrillic in markup).
- Zona kind filter + reset work; trailers shelf **absent** when empty.
- Catalog `?page=2` 200.

## Player (Lords — no regression)

| URL | state | video-player | iframe |
| --- | --- | --- | --- |
| `/title/eho-kamera/` | playable | 1 | 0 |
| `/title/troe-papash/` | awaiting | 0 | 0 |
| `.../episode-1/` | playable | 1 | 0 |

## Animedia vs amd.online (continued)

### Fixed this phase
- Mobile nav no longer clips mid-label: **hamburger** (`data-nav-toggle` / `#zhd-nav`) — 390 scrollWidth=clientWidth; menu opens full link set.
- Shelf labels → «Новые серии аниме» / «Новые аниме на сайте» (amd wording).
- Empty Ongoing/Today still **hidden** (no invented schedule data).
- Placeholder «Поиск аниме»; shorter home lead «Аниме онлайн».
- Overflow-x clip + filter wrap (earlier overnight commit).

### Remaining blockers
| ID | Item | Owner |
| --- | --- | --- |
| B1 | `/poster/` proxy needs nginx cache on Animedia/Zona | infra (forbidden tonight) |
| B2 | Ongoing/Today need source fields | content pipeline |
| B3 | Circe font / Premium mega-menu / login / Telegram chrome | rights / product — not inventable on closed stand |
| B4 | Hero carousel / episode list-with-time like amd | needs schedule timestamps in snapshot |
| B5 | Reference pack `VISUAL_DECISIONS.md` still empty (no measurement_plan) | cannot claim pixel-parity |
| B6 | Unrelated dirty `seo_operator/*` left untouched | other owners |

## Tests

```
pytest overnight + player skew + provenance + search/header → green (14–70 depending on set)
git diff --check → clean on touched files
```

## Files changed (this overnight continuum)

- `automation/host/lords-frontend.py`
- `automation/host/nova_closed_provenance.py`
- `tests/unit/test_lords_overnight_visual_repair.py`
- `tests/unit/test_nova_closed_provenance.py`
- `artifacts/evidence/overnight-visual-repair-2026-09-19/**`

## Explicit non-actions

No push/merge/reset/stash/force-push · no DNS · no indexing open · no fake iframes/providers · no reference-pack / visual-scoring edits · no foreign worktrees.
