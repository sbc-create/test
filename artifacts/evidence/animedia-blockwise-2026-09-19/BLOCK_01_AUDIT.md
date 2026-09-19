# BLOCK_01 — shell / header / theme — attempt 1

## Reference audit

- amd.online: compact top bar, centered content, light chrome (no dark theme on reference).
- Geometry target: header ~64–72 desktop / 52–58 mobile; content centered with gutters; no H1 overlap.

## Current defects (live 1.2.4)

1. Theme script runs after CSS → possible FOUC when stored theme is dark.
2. Mobile menu control measured ~32×44 (below 44×44 touch width) under flex squeeze.
3. Dark theme leaves several chrome surfaces on light literals (`#fff` title/card shells) — incomplete palette for shell.
4. No `color-scheme` hint; theme button `aria-pressed` not synced on load.
5. Header row: search can starve icon buttons on 390px.

## Root cause

Theme bootstrap order + flex shrinkage; dark tokens only partially override hardcoded light surfaces in shared chrome.

## Files allowed

- `automation/host/lords-frontend.py` (Animedia shell CSS, theme bootstrap, header markup only)
- Block 01 tests under `tests/unit/`

## Not changing

Player, shelves, episode feed, catalog grids, ratings mapping, footer data.
