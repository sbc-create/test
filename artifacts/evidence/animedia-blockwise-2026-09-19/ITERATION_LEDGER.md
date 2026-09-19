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
