# ROOT_CAUSES — Zona Pass 5

## RC-1 Year facet hard truncation `[:24]`

**Symptom:** Facet UI shows only 24 newest years (2026…2003). Older years
unreachable from chips. Owner suspicion about “empty” early years may also
stem from missing counts on chips and truncated history.

**Cause:** `список()` builds year chips from `(self.д.years or [])[:24]`.

**Fix:** Build year facets from the kind-scoped full set (before year filter /
pagination), include every year with `count > 0`, render compact `<select>`
plus count labels. No `[:24]`.

## RC-2 Owner “~7 titles in 2019”

**Oracle:** catalog.year 2019 = **2144** (films 1100 + series 825 + animation …).
Live `/series/?year=2019` → Results: 825. `/catalog/?year=2019` → 2144.

**Conclusion:** `SOURCE_DATA_GAP=NO` for 2019. Counts were never ~7 in the
authoritative snapshot. Pass4 `YEAR_COUNT_MISMATCHES=0` compared UI to the same
filter function; Pass5 oracle confirms full catalog.

## RC-3 Oversized posters / low density

**Cause:** ЗОНА_СТИЛЬ grid uses 6 cols @1440 / 7 @1920 with fluid `1fr` tracks →
card ~205px.

**Fix:** 7 cols @1440, ≥8 @1920, `minmax(0, 180px)`, `justify-content:start`,
carousel basis ~150px.

## RC-4 Sparse cards

**Cause:** `плитка()` emits only `kind · year` + bare ratings.

**Fix:** year+country; kind+≤2 genres; optional 2-line description; sourced
ratings only; playable mark when confirmed.

## RC-5 Footer one vertical “Разделы” column

**Cause:** Help/docs omitted when config empty → only brand + one link column;
links stack vertically.

**Fix:** Split navigational links into two compact columns when contacts absent;
CSS 3-column fallback on desktop.

## RC-6 Detail facts composition

**Cause:** Core facts only in right rail; main column under-uses structured facts.

**Fix:** Compact `dl` of core facts under ratings/genres in main; rail keeps
secondary/ad only when filled.

## RC-7 PAGE_SIZE

Pass4 used 48. Pass5 adopts **28** (4×7 desktop rows) for denser paging while
keeping full-set totals.
