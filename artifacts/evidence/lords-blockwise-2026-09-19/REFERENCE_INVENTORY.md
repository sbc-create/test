# REFERENCE_INVENTORY — Lords blockwise 2026-09-19

## Authoritative reference

| Field | Value |
| --- | --- |
| Primary reference | `lordfilm-hit` → https://lordfilm-hit.org/ |
| Inventory source | `inventory/reference-sources.yaml` |
| Token sheet | `docs/product/REFERENCE-DESIGN-TOKENS.md` (capture 2026-08-27) |
| Parity report | `docs/product/LORDS-REFERENCE-PARITY.md` (capture 2026-09-13) |
| Secondary | `lordserials.fan` (same family tokens; historically intermittent) |

No new public scrape in this session. Measurements below are from committed token/parity docs.

## Container width (px)

| Viewport | Reference | Token |
| ---: | ---: | --- |
| 390 | 380 | `--container-390` |
| 768 | 758 | `--container-768` |
| 1024 | 1000 | `--container-1024` |
| 1440 | 1100 | `--container-max` |
| 1920 | 1100 | `--container-max` |

Current Lords 1.1 sheet: `max-width:1100px` — aligned with token.

## Header

| Viewport | height_px | position | sticky |
| ---: | ---: | --- | --- |
| 390–1920 | 70 (±1) | relative | false |

## Card / grid notes

- Poster ratio target: 2:3
- Reference `grids=[]` on lordfilm-hit — column counts not instrumented there
- Lords 1.1 implements CSS grid: 2 / 3 / 4 / 6 columns by breakpoint

## Section / title / player / footer

Documented further in block evidence folders; player geometry baseline is FEATURE_HEAD `63216915` (local fixture PASS; live pending owner restart).

## Screenshot paths (existing, not re-scraped)

- `artifacts/evidence/templates-lords-zona-canary-004/reference-compare/`
- Product docs screenshots referenced from LORDS-VISUAL-PARITY-001*
