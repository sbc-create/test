# BLOCK_04 — home lower sections

## Status

`BLOCK_04_PASS`

## Section inventory

### ICU (7 shelves)
Сериалы с сериями → Аниме-фильмы → Дунхуа → Короткие сериалы → Топ по оценкам → Классика → Романтика

### SPACE (6 shelves)
Новые аниме на сайте → Топ по оценкам → Экшен → Классика → Аниме-фильмы → Дунхуа

Removed SPACE `video_available` (near-duplicate of recently_added on this catalog).

## Repairs

1. Grid: 7 cols @1200 (~169px @1363), 10 cols @1800 (~163px @1920)
2. Compact `.zt` (max-height 320, tighter text chrome)
3. Hero refill: shelves keep ≤48 pool; render excludes hero + cross-dedup so first shelf cannot vanish
4. `romance` title in ПРИЧИНЫ

## Measurements

| Viewport | Poster width |
| --- | --- |
| 1363 | **169px** (target 160–180) |
| 1920 | **163.4px** |
| 390 | 2-col fluid |

```text
HOME_LOWER_SECTIONS_SCORE=96
EXACT_DUPLICATE_SHELVES=0
ICU_BODY_HEIGHT≈6459
SPACE_BODY_HEIGHT≈5722
BODY_HEIGHT_DIFFERENCE_EXPLAINED=different home_shelves counts (7 vs 6) + content, not min-height
```

Evidence: `HOME_SECTION_AUDIT.md`, `DOMAIN_SECTION_MATRIX.csv`, `raw/BLOCK_04_AFTER_LOCAL_GEOMETRY.json`, `screenshots/block-04/`.
