# Block 01 — header / shell

Status: **BLOCK_01_PASS** (LOCAL_FIXTURE_ONLY geometry; not live)

## Contract vs lordfilm-hit tokens

| Check | Result |
| --- | --- |
| container max 1100 | PASS (sheet max-width:1100) |
| header position relative | PASS |
| header height ~70 | PASS |
| desktop single row | PASS |
| page overflow 0 | PASS |
| touch 44×44 menu/search | PASS |
| search capped desktop | PASS max-width 200px |

## Root cause

Header was `position:sticky` with desktop height 62px and `flex-wrap:wrap` on nav,
diverging from reference (relative, 70px, single row).

## Scope

Only `.hd*` / sheet width tokens in `ЛОРДС_СТИЛЬ`. Cards/title/player untouched.
