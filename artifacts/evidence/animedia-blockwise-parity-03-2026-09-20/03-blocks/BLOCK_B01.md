# BLOCK_B01 — Shared shell / header / taxonomy

- stage: ANIMEDIA-BLOCKWISE-PARITY-03
- block_id: B01
- status: PASS_LOCAL_PENDING_LIVE
- CONTRACT_SHA256: `5f2112e25ef974333c388bad405abfae3c3d460a713b028afa3c0e549b8eaeb3`
- CONTRACT_MUTATED: 0

## Intent

Shared header, primary nav from versioned route registry, taxonomy mega-panel
with oracle counts, theme + mobile drawer, breadcrumbs on title routes.

## Ownership

template

## Source provenance

- Nav links: `СЕМЕЙСТВА_1_1["animedia"]["нав"]` aligned to B00 `ROUTE_REGISTRY`
  (`/`, `/catalog/`, `/new/`, `/collections/`, `/schedule/`).
- Top-100 omitted (`absent_from_registry_until_core` → no link).
- Taxonomy facets: `индекс.genre` / `type` / years with counts; empty facets hidden.
- Breadcrumb intermediates: `/catalog/` only (no `/series/`/`/movies/` soft aliases).

## BEFORE gaps (measured)

| viewport | issue |
| --- | --- |
| d1440 | search w=220 (need 280–360); logo w=113 (need 120–155); no Schedule; no desktop `.zhd__n` |
| t768 | header h=72 (need ≤64); Schedule missing |
| all | `/new/?page=1` in taxonomy lists; no `.zcr` styles; tax panel max ~420px |

## Implementation (minimal)

- Nav: add `/schedule/`, rename Каталог, keep honest «Новое в каталоге».
- Desktop primary nav `.zhd__n` (≥1100px) + taxonomy mega-panel 720–960 / 4–5 cols.
- Search 280–360×44; logo min 120 / max 155; drawer `min(360px, 100vw-24px)`.
- Header heights: desktop 64–72, tablet/mobile 56–64.
- Taxonomy counts via `.zhd__cnt`; `/new/` without `page=1`.
- Breadcrumb `.zcr` 32–40px; title/episode crumbs → Catalog.

## AFTER_LOCAL oracle

`03-blocks/B01/AFTER_LOCAL/ORACLE.json` — **failures: 0**

Sample d1440 home: header h=68, search w=320, logo w=120, nav=flex, overflowX=0,
Schedule present, Top-100 absent, touch targets ≥44.

## Tests

```
.venv/bin/python -m pytest tests/unit/test_animedia_parity03_b01.py \
  tests/unit/test_animedia_parity02_block02_header.py -q
# 12 passed
```

## Remaining gaps

- none for B01 shell; Top-100 link correctly absent until Core route
- after-live screenshot for B01 deferred to B16 matrix

## Next

B02 weekly popular shelf + telegram/ad collapse
