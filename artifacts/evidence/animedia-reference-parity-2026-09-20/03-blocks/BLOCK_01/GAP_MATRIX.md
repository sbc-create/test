# BLOCK_01 GAP_MATRIX — reference + data oracle

| ID | Area | Reference | Ours before | Gap class | Notes |
| --- | --- | --- | --- | --- | --- |
| G01 | Header height @1440 | 90px | 69px | CSS_GEOMETRY_BUG | Flat bar vs denser IA on reference |
| G02 | Header @390 | 126px (wrap) | ~57–69 | CSS_GEOMETRY_BUG / PROJECTION_GAP | Reference grows for search+nav; ours stays flat |
| G03 | Top shelf poster | ~163×228 | ~152×214 (prior) | CSS_GEOMETRY_BUG | Close but density/IA differ |
| G04 | Home sections | Diaries, Collections, Top10 week, … | domain shelves + honest feed | PROJECTION_GAP | Social/diaries not supported — must stay absent, not fake |
| G05 | Title page depth | bodyH≈6035 | problem title bodyH≈1929 | TEMPLATE_RENDER_BUG / CSS_GEOMETRY_BUG | Missing secondary modules vs reference composition |
| G06 | Episode deep-link | n/a (title-centric ref) | bodyH≈1498, thin context | TEMPLATE_RENDER_BUG | BLOCK_10 critical |
| G07 | Side taxonomy drawer | present on reference | absent/weak | PROJECTION_GAP | BLOCK_02 |
| G08 | Data join posters | — | available→rendered | OK | gates 0 |
| G09 | master-lda description | — | source length 0 | SOURCE_DATA_GAP | cannot invent |
| G10 | AMD ratings | — | 0 rows | SOURCE_DATA_GAP / prior | BLOCK_09 |

## Critical gates (measured)

```text
REFERENCE_ACCESS_FAILURES=0
SOURCE_AVAILABLE_NOT_RENDERED=0
SOURCE_POSTER_AVAILABLE_BUT_NOT_RENDERED=0
SOURCE_DESCRIPTION_AVAILABLE_BUT_NOT_RENDERED=0
WRONG_TITLE_ID_MAPPINGS=0
AMBIGUOUS_AUTO_MAPPINGS=0
```

BLOCK_01 is oracle/baseline only — no template repair in this block.
