# Block 02 — shell / header / navigation

## Before (live Pass5)
- Mobile `@390/@360`: headerH≈68, bodyPadTop=117, unusedPad=49 (empty strip)
- Nav link hit area height 39px; menu button 40×40
- No sticky side genre rail (already hidden)
- Active «Обзор» visible; no horizontal overflow

## Root cause
`padding-top:117px` on `body` dated from when mobile nav was a second visible row.
Burger mode (`max-width:767px`) collapses nav, so reserved space exceeded real header.

## After (source)
- `padding-top:72px` mobile; 138 tablet; 69 desktop (≥1280)
- `.zhd__n a`, `.zhd__menu`, search controls: min 44×44
- `:focus-visible` outlines on logo/nav/search/menu
- Card grid / player CSS not modified

## Gates
See GATES.json. Live re-measure after deploy batch.
