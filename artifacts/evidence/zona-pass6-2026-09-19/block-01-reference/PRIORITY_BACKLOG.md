# Block 01 — Priority backlog (work order for Blocks 02–11)

Only one block IN_PROGRESS at a time. Locked Pass5 catalog/year/cards/player stay untouched unless proven regression.

## P0 functional

_(none new vs Pass5 live)_ — catalog oracle, year facets, player golden remain green.

## P1 structural

| ID | Route | Defect | Owner mapping | Target block |
| --- | --- | --- | --- | --- |
| P1-01 | home/mobile | Header→content gap ≈49px empty strip @390/360 | «пустая полоса под шапкой» | Block 02 |
| P1-02 | shell | Nav link hit areas &lt;44×44 (8 links) | a11y / touch | Block 02 |
| P1-03 | title | Right «СЕРИИ» rail creates tall vertical column | «длинная вертикальная rail» | Block 04 |
| P1-04 | home | «Недавно в каталоге» may overlap «Добавленные недавно» / `/new/` | duplicate shelves | Block 03 |
| P1-05 | descriptions | SOURCE_AVAILABLE_NOT_RENDERED / coverage≈75% | SEO content | Blocks 07–08 |

## P2 visual

| ID | Route | Defect | Target block |
| --- | --- | --- | --- |
| P2-01 | shell@1440+ | `.zwrap` spans full viewport width (0 side gutter @1440) | Block 02 |
| P2-02 | home cards | Card meta denser than reference (year·country + type·genre lines); verify no plot snippets | Block 03 |
| P2-03 | home@1440 | Home shelf cards ≈180px / up to 8 visible vs catalog 7×175 — confirm intentional carousel | Block 03 |
| P2-04 | title | Dual rating UI (text line + badge) | Block 04 |
| P2-05 | title | Poster max / gap to player | Block 04 |
| P2-06 | footer mobile | Brand + links should read as 2 compact columns, not 3 full-bleed stacks | Block 06 |
| P2-07 | collections | Text tiles vs poster cards; related last-row stretch | Block 05 |

## P3 cosmetic

| ID | Defect | Target |
| --- | --- | --- |
| P3-01 | Legacy ref nav was only ФИЛЬМЫ/СЕРИАЛЫ | keep factory nav unless owner insists |
| P3-02 | SEO prose block before footer | keep; no mass SEO text generation |
| P3-03 | Footer version string verbosity | optional later |

## OWNER_DATA_BLOCKER

| Field | Status |
| --- | --- |
| LEGAL_OWNER_DISPLAY_NAME | missing |
| PUBLIC_CONTACT_EMAIL | missing |
| RIGHTSHOLDER_COMPLAINT_EMAIL | missing |
| PRIVACY_URL / TERMS_URL / RIGHTSHOLDER_URL | missing |

→ Block 06: `FOOTER_VISUAL_PASS` possible; `FOOTER_DATA_PASS=NO`.

## SOURCE_DATA_GAP

| Item | Status |
| --- | --- |
| Descriptions ~13316 missing | oracle in Block 07; repair only source-grounded in Block 08 |
| Invented contacts/legal | forbidden |

## Explicit non-goals this pass

- Do not change card grid 8/7/4/2 or densify below ≈175px@1440 without reference mismatch proof.
- Do not reopen year=2019≈7 hypothesis (oracle=2144).
- Do not mutate player state machine without failing golden.
- Do not invent descriptions or contacts.
