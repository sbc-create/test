# Block 04 — Title layout audit

## Before
- 3-column `.ztitle` @≥1280: poster | main | 280px rail
- Rail held Серии / Статус / Возраст in `.ztitle__dl`
- `max-height:500px` on title grid risked clipping/empty band
- Expand script always injected (even without description)
- Genres duplicated as chips + fact row

## After
- 2-column layout: poster (220–240px) + main
- Rail/dl hidden; series/status/age/duration merged into `title-facts`
- Genres as chips only
- Description omitted entirely when source empty (no empty plot block)
- Expand script only when clamp control present
- Player markup untouched; tighter `.zpl{margin-top:18px}`

## Test titles covered
full-meta, no-desc, long-series, no-rating
