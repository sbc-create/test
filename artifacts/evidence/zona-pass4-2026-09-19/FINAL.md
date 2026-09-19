# FINAL — Zona Pass 4 (2026-09-19)

## Verdict

```text
VERDICT=NEEDS_OWNER_CONFIG
```

Route/date/sort/pagination/collections/layout/player gates are green on live
`zonafilm.space`. Overall PASS is blocked by missing owner contacts/documents
and unchanged SEO description gap (~75.12% / 13316 missing; no invented text).

## Heads

| Field | Value |
| --- | --- |
| BRANCH | `claude/zona-template-finalization-01` |
| START_HEAD | `140d2ca7657e36707179a06a2fd818fd1d1566c5` |
| FINAL_HEAD | `c624bebce3f6fac6eb05a5ee01907e02e813456b` |
| LIVE_BUILD | `20260919T211402Z-c624bebc-nova` |
| CONTENT_SNAPSHOT_DIGEST | `14add2ef912f0fe706db40a35c56ad4a` (catalog sha256 prefix) |
| ROLLBACK_PATH | `/srv/lords/.frontend/.rollback/20260919T211402Z-zona-01-pass4` |

## Commits (Pass 4)

1. `1402cad` fix(zona): route kind redirects, release sort, pagination gates
2. `9962dae` test(zona): Pass4 route, sort, pagination and footer gates
3. `d440d44` evidence(zona): Pass4 before-state, date contract, live defect probe
4. `c624beb` fix(zona): deployable collections + premiere-only /new/ activity
5. evidence commit (this pack)

## What was fixed on live

* Conflicting `kind` → single 308 to matching section; redundant `?kind=` stripped.
* Default sort is release/activity freshness, not alphabet; visible sort selector.
* `/new/` hard cap 240 removed; total now **1218** premiere-backed titles (was 53524 ingest-order clone).
* `/new/` freshness labels: `Премьера · DD.MM.YYYY` only from `_premiere_date`.
* Year filter H1 e.g. `Сериалы 2026 года`; year = release year; clock year for `current_season`.
* Pagination PAGE_SIZE=48; page>last → 404; page=1 stripped; neighbor pages disjoint.
* Collections hub: **12** distinct published sets (was 5); identical first-20 pairs = 0.
* Footer placeholders removed; empty contact/doc columns omitted (fail-closed).
* Player golden **10/10** on build `c624bebc` (ACTUAL_PROGRESS, no dual error/playing).

## What remains blocked

* `CONTACT_CONFIG_MISSING=1` — owner must fill footer config (see `CONTACTS_AND_DOCUMENTS_REQUIRED.md`).
* Descriptions: coverage ~75.12%, missing 13316 with `description_source=none`; no invention; SEO content cannot close.
* Card width at 1440 ≈ 205px (target 216±2) — columns 6/4/2 correct; note in REFERENCE_COMPARISON.

## Gates

| Gate | Pass |
| --- | --- |
| PLAYER_GATE_PASS | 1 |
| ROUTE_CONTRACT_PASS | 1 |
| YEAR_DATE_GATE_PASS | 1 |
| SORTING_GATE_PASS | 1 |
| PAGINATION_GATE_PASS | 1 |
| COLLECTION_DISTINCTNESS_PASS | 1 |
| RELATED_GATE_PASS | 1 |
| CARD_GRID_GATE_PASS | 0 (width band) |
| RESPONSIVE_GATE_PASS | 1 |
| FOOTER_VISUAL_GATE_PASS | 1 |
| FOOTER_CONTACT_GATE_PASS | 0 |
| FOOTER_DOCUMENTS_GATE_PASS | 0 |
| REFERENCE_PARITY_PASS | 1 |
| LIVE_SMOKE_PASS | 1 |
| DEPLOY_PROVENANCE_PASS | 1 |

## Close flags

```text
ZONA_PLAYER_CAN_BE_CLOSED=YES
ZONA_ROUTE_GENERATION_CAN_BE_CLOSED=YES
ZONA_YEAR_DATE_FILTERS_CAN_BE_CLOSED=YES
ZONA_COLLECTIONS_CAN_BE_CLOSED=YES
ZONA_FOOTER_TEMPLATE_CAN_BE_CLOSED=NO
ZONA_SEO_CONTENT_CAN_BE_CLOSED=NO
ZONA_TEMPLATE_CAN_BE_CLOSED=NO
ZONA_OVERALL_CAN_BE_CLOSED=NO
```

## Safety

```text
DEPLOY_SCOPE=zona-01-only
DNS_MUTATIONS=0
INDEXING_OPENED=0
OTHER_DOMAINS_MUTATED=0
PAID_OPERATIONS=0
PUSH_PERFORMED=0
MERGE_PERFORMED=0
SECRETS_EXPOSED=0
```
