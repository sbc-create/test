# B01 — Reference and acceptance contracts

## Owner-authorized design passports (frozen)

Source: `artifacts/evidence/lords-three-distinct-templates-2026-09-20/passports/`

| design | intended role | first_three_blocks | primary_card (passport) |
| --- | --- | --- | --- |
| lords-cinema-v2 | mass cinema catalog | Премьеры недели → Фильмы по жанрам → Новинки | vertical poster grid (.c) |
| lords-series-feed-v2 | series updates feed | Продолжающиеся сериалы → Новые поступления → Популярное за неделю | vertical poster **for now**; episode-horizontal **later** |
| lords-curated-v2 | editorial what-to-watch | Выбор редакции → Тематические подборки → Что посмотреть | mosaic/landscape **later**; poster grid **interim** |

## Passport-declared gaps (pre-audit, not findings yet)

Passports themselves document incomplete product differentiation:

- series-feed: episode-horizontal card deferred; player-forward title deferred; series footer deferred; token fork pending
- curated: mosaic editorial card deferred; why-watch title deferred; editorial footer deferred; ivory/plum token fork pending

These are acceptance expectations for distinctness scoring, not excuses.

## External live references

Priority names from audit brief: `lordfilm-hit.org`, `lordserials.fan`.

Repo docs: `docs/product/LORDS-REFERENCE-*.md`, `inventory/reference-sources.yaml`, `config/reference-packs/`.

**Limitation:** this stage does not scrape new external live references (CLOSED_WORLD / no invent). Frozen passports + prior reference inventory docs are used for IA/density comparison. External live reference reachability is not required to close the audit.

## Deploy baseline (not visual acceptance)

`artifacts/evidence/lords-three-distinct-templates-deploy-2026-09-20/` proves deploy identity only.
