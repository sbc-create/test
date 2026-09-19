# ITERATION_LEDGER

## BLOCK_01 attempt 1 → PASS

| Step | Result |
| --- | --- |
| reference audit | amd.online light chrome; no dark theme on reference |
| before screenshots | `screenshots/block-01/*-before-*` |
| defects | FOUC risk; mobile touch squeeze; incomplete dark chrome; aria not synced |
| repair | theme boot before CSS; DOMContentLoaded aria sync; 44px actions; overlay mobile nav; color-scheme; no media filters |
| unit tests | `test_animedia_block_01_shell_theme.py` + regression: 54 related passed |
| local browser | all Block 01 gates true (see `raw/BLOCK_01_AFTER_LOCAL_GEOMETRY.json`) |
| scores | HEADER_SCORE=94 THEME_SCORE=93 |
| commit | pending |

### Scores rationale (measurements)

- HEADER: desktop 69px in 64–72; mobile 57 in 52–58; overlap 0; overflow 0; touch 44×44; menu overlay keeps bar ≤58 → 94
- THEME: early theme=dark before paint; persistence light across reload; prefers-color-scheme boot; no invert filters; distinct dark palette → 93

## BLOCK_02 attempt 1 → PASS

| Step | Result |
| --- | --- |
| reference audit | amd.online top carousel ~153×214; compact band |
| before geometry | `raw/BLOCK_02_BEFORE_GEOMETRY.json` + live/local/reference crops |
| defects | theoretical flex stretch; need min-width lock |
| repair | `.ahero` track `align-items:flex-start`; card `min-width:152px`; `.zt` fixed width desktop/mobile |
| unit tests | `test_animedia_block_02_top_shelf.py` + related: 13 passed |
| local browser | all 15 gates true (`raw/BLOCK_02_AFTER_LOCAL_GEOMETRY.json`) |
| scores | TOP_SHELF_SCORE=96 |
| commit | `d76ee94` |

## BLOCK_03 attempt 1 → PASS

| Step | Result |
| --- | --- |
| semantics audit | 0 episode-air timestamps; catalog.published_at only → EPISODE_EVENT_DATA_GAP=1 |
| repair | rename «Недавно добавленные»; meta «Добавлено ·»; CTA `/new/?page=1`; denser rows |
| unit tests | home_pagination + visual_finalization: 22 passed |
| local QA | all gates true; pagination 5495 events; dups=0; beyond=404 |
| scores | EPISODE_FEED_SCORE=96 |
| commit | `f5ac02e` |

## BLOCK_04 attempt 1 → PASS

| Step | Result |
| --- | --- |
| section inventory | ICU 7 / SPACE 6 distinct algorithms; height delta explained |
| repair | 7/10-col denser cards; hero refill; drop SPACE video_available |
| local QA | poster 169@1363 / 163@1920; exact dup shelves 0 |
| scores | HOME_LOWER_SECTIONS_SCORE=96 |
| commit | `18cd7d7` |
