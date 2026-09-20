# Root cause matrix

| ID | Symptom | Sites | Severity | Root cause | Shared? | Phase B action |
|---|---|---|---|---|---|---|
| RC-COUNTRY-404 | All `/country/<cyrillic>/` facet links 404 | 01/02/03 | P0 | Index code Cyrillic; route regex ASCII-only | YES (shared frontend) | Align country codes to latin translit (like genres) OR widen route regex + one canonical form + redirects |
| RC-LEGACY-FILMS | `/films/`, `/cartoons/` 404 | 01/02/03 | P2 | No legacy redirect map entry | YES | Add 308 → `/movies/`, `/animation/` |
| RC-MANIFEST-DRIFT | Header artifact sha ≠ disk for 02/03 | 02/03 | P1 | Per-site manifests stale vs shared disk | deploy hygiene | Refresh manifests on next site-scoped deploy |
| RC-FILTER-UX | Tall multi-row filter chips | 01/02/03 | P1 UX | Design not compact | NO (per profile skin) | Compact filter per profile |
| RC-502-SERIES-2016 | Reported 502 on series+year | 02 (seed) | P0? | Not reproduced; logs inaccessible | unknown | Keep monitor; do not blind-restart; treat as unresolved until log access or re-break |
| RC-NGINX-BANNER | `Server: nginx/1.18.0` on errors | all | infra | default nginx | infra | Document only; no nginx change without approval |

## Player full-bleed-v1

Disk artifact contains contract. lords-01 header build `20260919T224500Z-0a5fe648-nova` matches PLAYER_FIX_HEAD staging.
Live provider geometry not fully re-validated in Phase A (fixture suite still green in repo); Phase B must re-check live per site.
