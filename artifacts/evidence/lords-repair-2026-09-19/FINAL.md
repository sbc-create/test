# Lords repair FINAL — 2026-09-19

## Verdict: **NEEDS_REPAIR** (P1 remain; P0 closed for known blockers)

P0 closed: matrix ranking, slug alias 301, ep7 unavailable, hub no SDK.
P1 remaining: full SEO editorial bundle / snapshot contract / progressive catalog / 502 root-cause journal proof — not invented.

## Commits

| Hash | Role |
| --- | --- |
| `a0db875` | fix(lords): search, routes, filters, home H2, mobile nav, footer |
| `cc50164` | chore(nova): provenance → a0db875 |
| `ed8effd` | fix(lords): matrix year-suffix soft match |
| `810e826` | chore(nova): provenance → ed8effd |

## Live

| Field | Value |
| --- | --- |
| DEPLOY_PERFORMED | **yes** — lords-02 only (twice: a0db875 then ed8effd) |
| DNS_MUTATIONS | **0** |
| INDEXING_OPENED | **0** |
| PRODUCTION_MUTATIONS | closed nova apply only; nginx reload after readiness |
| ROLLBACK_PATH | `/srv/lords/.frontend/.rollback/pre-closed-update-20260919T094007Z` (latest) |
| EXPECTED_PROFILE_DIGEST | runtime `ed8effd6…` / build `20260919T094007Z-ed8effd6-nova` |
| LIVE_PROFILE_DIGEST | marker `Lords · 1.1.0 · ed8effd6`; build_id matches |

## Before → after

| Check | Before | After |
| --- | --- | --- |
| `matrix` search | Маори first | **Матрица (1999)** first |
| old slug domokho… | 404 | **308** → domoho… (+ episode tail) |
| `/movies/` `/series/` `/animation/` | 404 | **200** |
| `/collections/` | catalog clone | **hub** of contract collections |
| `/new/` | ~full catalog reorder | capped **240** recent with published_at |
| country/sort | ignored | applied / unknown → empty+flag |
| home sections | tabs__pill | **H2** + «Весь раздел» |
| series hub player | 16:9 empty | compact **awaiting** (~140–180px) |
| episode 7 | (avail-gate prior) | **unavailable**, 0×video-player |
| footer | test slogan + Template | columns + `Lords · 1.1.0 · <sha8>` |
| mobile header | crowded | burger 44×44 + drawer |
| load 100 seq / 20 par | — | **zero 5xx** |

## Tests

- `tests/unit/test_lords_repair_2026_09_19.py` (new)
- related search/player/home/animedia suites green
- `git diff --check` on sources: clean

## Cross-profile smoke

- animedia.icu 200 + noindex
- zonafilm.space 200 + noindex

## Remaining blockers (honest)

| ID | Sev | Note |
| --- | --- | --- |
| SEO bundle gate | P1 | Draft copy only; `SEO_NOT_READY` while indexing closed; no full versioned editorial overlay |
| Snapshot IDs | P1 | catalog/details/provider content_snapshot_id contract not wired into deploy fail |
| Progressive catalog | P2 | SSR 48 + pagination works; infinite/cursor not fully as specified |
| 502 root cause | P2 | load test green now; no journal proof of prior 20s outage |
| Pixel vs lordfilm-hit | P2 | density preserved (~1100/6col); not pixel-cloned |

## Evidence paths

- `artifacts/evidence/lords-repair-2026-09-19/WORKLOG.md`
- `artifacts/evidence/lords-repair-2026-09-19/issues.json`
- `artifacts/evidence/lords-repair-2026-09-19/raw/live-verify.json`
- screenshots `before/` + `after/`
