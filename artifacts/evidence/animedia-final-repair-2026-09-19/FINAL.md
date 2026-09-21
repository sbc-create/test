# Animedia final template repair — 2026-09-19

## Verdict

**PASS** — both closed Animedia domains serve design `1.2.1` / `animedia-portal` with split SEO profiles, noindex retained, genre filters distinct, poster proxy healthy, peers unchanged.

## Branch / commits

| Field | Value |
| --- | --- |
| Branch | `claude/animedia-template-finalization-01` |
| Base HEAD | `b023bd50cced8d281cb3814a75bf72b429afee0b` |
| Final HEAD | `5e9e816ee924cd1d61a874f884bad3ec5b76b778` |
| Runtime commit (frontend bytes) | `289a459f0e9359777b988f61cc0d66084fc94cd3` |
| Runtime artifact sha256 | `0940212f9cbd317400bf11eae1c7da44e98dc30ef4be357bb7ddfd6dffde8afb` |

Commits on this window (after base):

1. `0ec9262` — unattended Shell↔Bash guard
2. `f772c02` — Animedia storefront repair batch
3. `a3d6309` — closed-update tooling / SEO profiles
4. `d9bd7b3` — shared-runtime superset (live Zona + Animedia)
5. `400e831` — deploy lock + provenance
6. `6ce421e` — accept design `1.2.1` portal gate
7. `960bf9d` — provenance tip for gate fix
8. `289a459` — genre index from Russian names
9. `43dc842` — provenance tip (superseded by evidence commit tip)
10. `5e9e816` — live matrix + FINAL report + provenance tip = runtime `289a459`
## Live manifests (after deploy)

### animedia.space (`animedia-02`)

- profile: `animedia-space`
- design_version: `1.2.1`
- source_commit / runtime_commit: `289a459f0e9359777b988f61cc0d66084fc94cd3`
- build_id: `20260919T144719Z-289a459f-nova`
- artifact_sha256: `0940212f9cbd317400bf11eae1c7da44e98dc30ef4be357bb7ddfd6dffde8afb`
- systemd: `nova-animedia-02` → `:9122`
- rollback: `/srv/lords/.frontend/.rollback/pre-closed-update-20260919T144719Z`

### animedia.icu (`animedia-01`)

- profile: `animedia-icu`
- same runtime artifact / commits as space
- build_id: `20260919T144739Z-289a459f-nova`
- systemd: `nova-animedia-01` → `:9121`
- rollback: `/srv/lords/.frontend/.rollback/pre-closed-update-20260919T144739Z`

### Peers (not mutated)

- zona-01 artifact still `14ce882d…` / build `20260919T143500Z-2d6d1695-nova` / design `zona-top`
- lords-02 artifact still `b08519b2…` / build `20260919T135218Z-5fc22310-nova` / design `lords-sheet`

## Root causes fixed

1. **Runtime superset** — candidate rebuilt on live Zona tip (`_подвал_зона`, menu, SEO home) before install; Animedia changes are profile-gated.
2. **Design gate** — `1.2.1` was excluded from `ПЕРЕРАБОТАНО_С`, forcing the dark legacy shell; now `{1.2.0, 1.2.1}` for Animedia.
3. **Genre filters empty** — details lack `genre_codes`; index now derives Latin codes via translit and accepts Cyrillic query values.
4. **Public diagnostics** — Animedia player/poster/footer copy stripped of provider/test banners; compact build marker only.

## Live acceptance (both domains)

| Check | space | icu |
| --- | --- | --- |
| Home 200 / portal design | yes | yes |
| Title / H1 distinct | Space catalog focus | ICU series/collections focus |
| Self-canonical | `https://animedia.space/` | `https://animedia.icu/` |
| robots meta + X-Robots-Tag | `noindex, nofollow` | same |
| robots.txt | `Disallow: /` | same |
| Build marker | `Animedia 1.2.1 · 289a459` | same |
| Cross-host links | none | none |
| Genre drama / comedy / thriller counts | 1418 / 2548 / 207 | same catalog |
| Poster `/poster/` sample | 48/48 image/200 | (shared runtime) |
| Load 100 sequential + 20 parallel catalog | 0 × 5xx | — |
| Title page player shell | present, no provider diagnostics | — |

Evidence JSON: `artifacts/evidence/animedia-final-repair-2026-09-19/live-matrix.json`

## Tests run

- `tests/unit/test_animedia_final_repair.py` — 12 passed (tokens, portal gate, genres, player copy, posters, domains, episodes)
- `tests/unit/test_animedia_parity_surfaces.py` — passed earlier in session
- `tests/operator/test_hookguard.py` — passed

## Boundaries

DNS / indexing / access / Lords / Zona / Yummy / SEO Operator / Topvisor / push / merge — not mutated.
