# YEAR / DATE CONTRACT — Zona Pass 4

## Clock

* «Текущий год» = year from injectable clock (`LORDS_CLOCK_ISO` or system UTC).
* Never `MAX(year)` from the catalog for «Этого года».

## Field meanings

| Field | Meaning | Allowed uses |
| --- | --- | --- |
| `year` | Confirmed release/production year | `?year=` filter, year facets, «Этого года» |
| `premiere_date` | Confirmed premiere day (YYYY-MM-DD) | activity for /new/, display «Премьера · …» |
| `published_at` | Catalog ingest / supplier appearance (UTC) | `recently_added`, sort=`recently_added`, display «Добавлено · …» only |
| `published_at_estimated` | Whether published_at was estimated | Never treat estimated as premiere |

## Forbidden substitutions

* Import date ≠ premiere.
* Old title imported today ≠ «новый релиз».
* Missing date ≠ today / random / provider ordinal.
* Future bogus years in catalog must not redefine «current year».

## Route defaults

| Route | Primary order |
| --- | --- |
| `/new/` | `activity_at DESC` (premiere_date if present else published_at), NULLS LAST |
| `/movies/`, `/series/`, `/animation/` | release freshness: premiere_date DESC NULLS LAST, then year DESC, then title, then slug |
| year facet pages | premiere_date DESC NULLS LAST, year exact match |
| `recently_added` collection | `published_at DESC` |
| `rating` | rating DESC with min votes when available, else documented NULLS LAST |
| `title` | normalized title ASC |

## Tie-breaker (all sorts)

```text
primary_sort,
normalized_title ASC,
stable slug ASC
```

## Display timezone

* Stored timestamps: UTC (`Z`).
* Display dates: `DD.MM.YYYY` in Europe/Moscow for calendar days derived from `premiere_date` (date-only) or UTC date of `published_at`.

## /new/ freshness labels (only if data exists)

* `premiere_date` → `Премьера · DD.MM.YYYY`
* else `published_at` → `Обновлено · DD.MM.YYYY` (catalog update — honest, not «премьера»)
* Never invent episode numbers or air dates without sidecar fields.
