# ROOT_CAUSES — Zona Pass 4

| Defect | Root cause | Location |
| --- | --- | --- |
| Alpha default on /movies|/series|/animation|/catalog | `отбор()` sorts by normalized title when sort absent for those routes | `lords-frontend.py` ~3302–3305 |
| Conflicting `?kind=` ignored | `маршрут_1_1` overwrites query kind with path kind; no redirect | ~5667–5671 |
| Redundant `?kind=` in chips/pager | `запрос_строкой(выбрано)` always emits kind; chips stay on same `разд` | `ВидЗона.список` ~4525–4530, `листалка` |
| `/new/` hard cap 240 | `НОВИНКИ_ПРЕДЕЛ = 240` after published_at sort | `отбор()` ~3291–3294 |
| `/new/` == recently_added | Both use `published_at` DESC only | `отбор` + `collection_contract` recent |
| «Новые фильмы» = import order | Collection `recently_added_movies` sorts by `published_at`, kind=Фильм | `collection_contract.py` ~266–269 |
| `current_season` = MAX(year) | `year=max` → `с.максимальный_год` | `collection_contract.py` ~165–198, 278–281 |
| Generic H1 on year filter | `титул` only swaps for genre name, not year | `ВидЗона.список` ~4511–4546 |
| page overflow soft-clamped | `стр = min(стр, всего)` never 404; page=0 → 1 | ~4507–4509 |
| Footer placeholders | Empty `footer-zona-01.json` → placeholder spans | `_подвал_зона` ~4077–4083 |
| No freshness label on /new/ cards | Card template has kind·year only | `плитка` |
| Sparse true release dates | Only `premiere_date` (~2.3%) + `year`; no episode air dates in sidecar | details snapshot |

## Provenance limits (handoff, not fiction)

Episode `air_date` / `video_verified_at` / `catalog_added_at` distinct from `published_at` are **not projected** into Zona sidecars. Pass4 must:

* treat `published_at` as catalog-ingest time;
* treat `premiere_date` as release when present;
* treat `year` as release year only;
* document missing fields in `DATE_PROVENANCE.csv` / handoff — do not invent.
