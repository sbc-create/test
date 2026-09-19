# HARD_LIMIT_AUDIT — Zona Pass 5

| Location | Limit | Affects results? | Status |
| --- | ---: | --- | --- |
| `(self.д.years or [])[:24]` (Pass4) | 24 years | Yes — hid pre-2003 facets | **Removed** |
| `НА_СТРАНИЦЕ_1_1` | 28 | Page size only | OK |
| Collection hub `предел=48` | 48 | Preview only | OK |
| Home rail `[:12]` / section limits | preview | Preview only | OK |
| `/new/` premiere filter | activity set | Intentional semantics | OK |
| SQL LIMIT | n/a | None in frontend path | OK |

Gates:

```text
FULL_CATALOG_TRUNCATED=NO
FACETS_COMPUTED_FROM_FULL_SET=YES
PAGINATION_COVERS_FULL_SET=YES
HARD_CAP_240_AFFECTS_RESULTS=NO
RECORD_AFTER_240_REACHABLE=YES
```
