# REFERENCE_MEASUREMENTS

Read-only reference: amd.online geometry from task brief + live AFTER measurements.

## Title card (target vs ours @1440)

| Metric | Reference (amd ~1363) | Ours AFTER (icu @1440) | Pass |
| --- | ---: | ---: | --- |
| Layout | poster \| content (2-col) | `.ztitle` 2-col, no rail | YES |
| Poster | ~240×351 | 240×360 (ratio 0.667) | YES |
| Shell radius | 28–32 | clamp 22–28 | YES |
| Score in header | right of H1 | `.ztitle__score` | YES |

## Episode feed (target vs ours @1440)

| Metric | Reference | Ours | Pass |
| --- | ---: | ---: | --- |
| Columns desktop | 2 | 2 (`episodeCols=2`) | YES |
| Row model | thumb + title + ep# | `.aeps__row` | YES |
| Native invented "Сегодня" | forbidden | absent | YES |

## Player (target vs ours)

| Metric | Target | Ours | Pass |
| --- | ---: | ---: | --- |
| Outer ratio | 1.777±0.03 | 1.7778 | YES |
| Host fill W/H | ≥0.99 | 1.0 / 1.0 | YES |
| Empty tail px | ≤2 | 0 | YES |
| Overlay over playing | 0 | 0 | YES |

## Container

| Viewport | Target gutter | Implementation |
| --- | --- | --- |
| desktop | min(1704, 100vw-80) | `.zwrap` same |
| ≤1439 | −48 | media query |
| ≤1023 | −40 | media query |
| ≤767 | −28 | media query |

## Catalog year=2026

| Check | Result |
| --- | --- |
| H1 | «Аниме 2026 года» |
| Card years | all 2026 in sample |
| Default sort | published_at DESC, slug DESC |
