# Current vs Reference

Сравнение наших сайтов с референсами по инструментальным замерам.
Источник: `/tmp/refmeas/<name>/measurements.json` на control-host.

| Сайт | URL | Замер (UTC) | HTTP |
|---|---|---|---|
| ours-lords (наш) | https://lordfilm47.space/ | 2026-08-27T13:44:15.662Z | 200 |
| lordfilm-hit (референс) | https://lordfilm-hit.org/ | 2026-08-27T15:06:30.913Z | 200 |
| lordserials (референс) | https://lordserials.fan/ | 2026-08-27T15:07:03.610Z | 200 |
| ours-yummy (наш) | https://yummyani.site/ | 2026-08-27T13:44:01.244Z | 200 |
| old.yummyani.me (референс) | https://old.yummyani.me/ | 2026-08-27T13:43:46.138Z | 200 |

`Gap` = наше значение − значение референса.

---

## A. ours-lords vs lordfilm-hit — вьюпорт 390

| Метрика | ours-lords | lordfilm-hit | Gap |
|---|---|---|---|
| documentWidth | 390 px | 390 px | 0 |
| contentWidth | 342 px | 380 px | **−38 px** |
| gutter | 24 px | 5 px | **+19 px** |
| scrollHeight | 2 746 542 px | 4 555 px | **+2 741 987 px** (×603) |
| horizontalOverflow | нет | нет | — |
| header.height | отсутствует (`header = null`) | 70 px | **−70 px** |
| header.sticky | — (шапки нет) | false | — |
| sectionCount | 2 | 4 | **−2** |
| linkCount | 4 316 | 128 | **+4 188** |
| imageCount | 4 316 | 33 | **+4 283** |
| paginationLinks | 0 | 0 | 0 |
| body fontSize | 16 px | 14 px | **+2 px** |
| h1 fontSize / weight | 32 px / 700 | 18 px / 600 | **+14 px / +100** |
| h2 fontSize | 24 px | отсутствует | не сопоставимо |
| a fontSize | 16 px | 14 px | **+2 px** |
| p fontSize | 16 px | 14 px | **+2 px** |
| button | отсутствует | 16 px / lh 40 px / 600 | **кнопка не измерена у нас** |
| доминирующее cardAspectRatio | 0.67 (200 шт.) | 0.69 (28 шт.) | **−0.02** |
| grid: columns × gap | 1 × 18 px (4 316 детей) | `grids = []` | колонки референса не измерены |

## B. ours-lords vs lordfilm-hit — вьюпорт 1440

| Метрика | ours-lords | lordfilm-hit | Gap |
|---|---|---|---|
| documentWidth | 1440 px | 1440 px | 0 |
| contentWidth | 1 148 px | 1 100 px | **+48 px** |
| gutter | 146 px | 170 px | **−24 px** |
| scrollHeight | 425 738 px | 1 972 px | **+423 766 px** (×216) |
| horizontalOverflow | нет | нет | — |
| header.height | отсутствует | 70 px | **−70 px** |
| sectionCount | 2 | 4 | **−2** |
| linkCount | 4 316 | 128 | **+4 188** |
| imageCount | 4 316 | 33 | **+4 283** |
| paginationLinks | 0 | 0 | 0 |
| body fontSize | 16 px | 14 px | **+2 px** |
| h1 fontSize | 32 px | 18 px | **+14 px** |
| a fontSize | 16 px | 14 px | **+2 px** |
| p fontSize | 16 px | 14 px | **+2 px** |
| доминирующее cardAspectRatio | 0.67 (200) | 0.69 (26) | **−0.02** |
| grid: columns × gap | 5 × 18 px | `grids = []` | колонки референса не измерены |

---

## C. ours-lords vs lordserials — вьюпорт 390

| Метрика | ours-lords | lordserials | Gap |
|---|---|---|---|
| contentWidth | 342 px | 380 px | **−38 px** |
| gutter | 24 px | 5 px | **+19 px** |
| scrollHeight | 2 746 542 px | 12 756 px | **+2 733 786 px** (×215) |
| horizontalOverflow | нет | нет | — |
| header.height | отсутствует | 67 px | **−67 px** |
| sectionCount | 2 | 10 | **−8** |
| linkCount | 4 316 | 257 | **+4 059** |
| imageCount | 4 316 | 101 | **+4 215** |
| paginationLinks | 0 | 0 | 0 |
| body fontSize | 16 px | 14 px | **+2 px** |
| h1 fontSize / weight | 32 px / 700 | 18 px / 600 | **+14 px / +100** |
| p fontSize / lineHeight | 16 px / normal | 13 px / 22.1 px | **+3 px** |
| button fontSize | отсутствует | 15 px | **кнопка не измерена у нас** |
| доминирующее cardAspectRatio | 0.67 (200) | 0.69 (74) | **−0.02** |
| основная сетка (columns × gap) | 1 × 18 px | 3 × 7 px | **−2 колонки / +11 px gap** |
| число измеренных сеток | 1 | 9 | **−8** |

## D. ours-lords vs lordserials — вьюпорт 1440

| Метрика | ours-lords | lordserials | Gap |
|---|---|---|---|
| contentWidth | 1 148 px | 1 100 px | **+48 px** |
| gutter | 146 px | 170 px | **−24 px** |
| scrollHeight | 425 738 px | 5 246 px | **+420 492 px** (×81) |
| horizontalOverflow | нет | нет | — |
| header.height | отсутствует | 71 px | **−71 px** |
| sectionCount | 2 | 10 | **−8** |
| linkCount | 4 316 | 257 | **+4 059** |
| imageCount | 4 316 | 101 | **+4 215** |
| body fontSize | 16 px | 14 px | **+2 px** |
| h1 fontSize | 32 px | 18 px | **+14 px** |
| p fontSize | 16 px | 13 px | **+3 px** |
| доминирующее cardAspectRatio | 0.67 (200) | 0.69 (49) | **−0.02** |
| основная сетка (columns × gap) | 5 × 18 px | 2 × 7 px | **+3 колонки / +11 px gap** |
| число измеренных сеток | 1 | 9 | **−8** |

---

## E. ours-lords — остальные вьюпорты (768 / 1024 / 1920)

| Метрика | VP | ours-lords | lordfilm-hit | Gap | lordserials | Gap |
|---|---|---|---|---|---|---|
| contentWidth | 768 | 720 px | 758 px | **−38 px** | 758 px | **−38 px** |
| contentWidth | 1024 | 976 px | 1 000 px | **−24 px** | 1 000 px | **−24 px** |
| contentWidth | 1920 | 1 148 px | 1 100 px | **+48 px** | 1 100 px | **+48 px** |
| gutter | 768 | 24 px | 5 px | **+19 px** | 5 px | **+19 px** |
| gutter | 1024 | 24 px | 12 px | **+12 px** | 12 px | **+12 px** |
| gutter | 1920 | 386 px | 410 px | **−24 px** | 410 px | **−24 px** |
| scrollHeight | 768 | 730 772 px | 2 881 px | **+727 891 px** | 7 307 px | **+723 465 px** |
| scrollHeight | 1024 | 401 839 px | 1 851 px | **+399 988 px** | 4 955 px | **+396 884 px** |
| scrollHeight | 1920 | 425 738 px | 1 972 px | **+423 766 px** | 5 246 px | **+420 492 px** |
| horizontalOverflow | 768 | **да** | нет | **регресс** | нет | **регресс** |
| horizontalOverflow | 1024 | **да** | нет | **регресс** | нет | **регресс** |
| horizontalOverflow | 1920 | нет | нет | — | нет | — |
| grid columns | 768 | 3 | не измерено | — | 3 (осн. сетка) | 0 |
| grid columns | 1024 | 5 | не измерено | — | 2 (осн. сетка) | **+3** |

Горизонтальный оверфлоу у нас возникает на **768 и 1024** — оба Lords-референса на этих вьюпортах оверфлоу не дают.

---

## F. ours-yummy vs old.yummyani.me — вьюпорт 390

| Метрика | ours-yummy | old.yummyani.me | Gap |
|---|---|---|---|
| documentWidth | 390 px | 390 px | 0 |
| contentWidth | 378 px | 388 px | **−10 px** |
| gutter | 6 px | 1 px | **+5 px** |
| scrollHeight | 7 525 px | 7 591 px | **−66 px** |
| horizontalOverflow | нет | нет | — |
| header.height | 3 px | 3 px | 0 |
| header.position | static | static | — |
| sectionCount | 1 | 2 | **−1** |
| linkCount | 89 | 245 | **−156** |
| imageCount | 44 | 93 | **−49** |
| paginationLinks | 6 | 5 | **+1** |
| body fontSize / lineHeight | 14 px / 18.9 px | 14 px / normal | 0 px |
| h1 | 20 px / 28 px / 600 | отсутствует | не сопоставимо |
| a fontSize | 14 px | 14 px | 0 |
| p fontSize / lineHeight | 14 px / 22.75 px | 14 px / normal | 0 px |
| button fontSize | 14 px | 14 px | 0 |
| доминирующее cardAspectRatio | 0.71 (24) | 0.71 (30) | **0.00** |
| второе соотношение | 1.45 (18) | 0.68 (18) / 2.10 (10) | различается |

## G. ours-yummy vs old.yummyani.me — вьюпорт 1440

| Метрика | ours-yummy | old.yummyani.me | Gap |
|---|---|---|---|
| documentWidth | 1440 px | 1440 px | 0 |
| contentWidth | 1 308 px | 1 308 px | **0** |
| gutter | 66 px | 66 px | **0** |
| scrollHeight | 4 101 px | 4 555 px | **−454 px** |
| horizontalOverflow | нет | нет | — |
| header.height | 69 px | 69 px | **0** |
| sectionCount | 1 | 2 | **−1** |
| linkCount | 89 | 245 | **−156** |
| imageCount | 44 | 93 | **−49** |
| paginationLinks | 6 | 5 | **+1** |
| body fontSize | 14 px | 14 px | 0 |
| a fontSize | 14 px | 14 px | 0 |
| p fontSize | 14 px | 14 px | 0 |
| button fontSize | 14 px | 14 px | 0 |
| доминирующее cardAspectRatio | 0.71 (42) | 0.71 (48) | **0.00** |
| широкий блок | 2.86 (1) | 1.79 (10) | **+1.07 / −9 шт.** |

### ours-yummy — остальные вьюпорты

| Метрика | VP | ours-yummy | old.yummyani.me | Gap |
|---|---|---|---|---|
| contentWidth | 768 | 756 px | 756 px | 0 |
| contentWidth | 1024 | 1 012 px | 1 012 px | 0 |
| contentWidth | 1920 | 1 308 px | 1 308 px | 0 |
| gutter | 768 | 6 px | 6 px | 0 |
| gutter | 1024 | 6 px | 6 px | 0 |
| gutter | 1920 | 306 px | 306 px | 0 |
| scrollHeight | 768 | 7 411 px | 8 045 px | **−634 px** |
| scrollHeight | 1024 | 6 934 px | 8 063 px | **−1 129 px** |
| scrollHeight | 1920 | 4 101 px | 4 555 px | **−454 px** |
| header.height | 768 | 3 px | 3 px | 0 |
| header.height | 1024 / 1920 | 69 px | 69 px | 0 |

Геометрия Yummy совпадает с референсом полностью (contentWidth, gutter, header — Gap 0 на всех вьюпортах). Расхождения только в объёме контента.

---

## H. Крупнейшие расхождения (ours-lords)

Отсортировано по абсолютной величине измеренного расхождения.

| # | Метрика | Наше | Референс | Gap |
|---|---|---|---|---|
| 1 | scrollHeight @390 | 2 746 542 px | 4 555 px (lordfilm-hit) | **+2 741 987 px**, ×603 |
| 2 | scrollHeight @1440 | 425 738 px | 1 972 px (lordfilm-hit) | **+423 766 px**, ×216 |
| 3 | imageCount (все VP) | 4 316 | 33 (lordfilm-hit) / 101 (lordserials) | **+4 283 / +4 215** |
| 4 | linkCount (все VP) | 4 316 | 128 (lordfilm-hit) / 257 (lordserials) | **+4 188 / +4 059** |
| 5 | sectionCount (все VP) | 2 | 10 (lordserials) | **−8** |
| 6 | header.height (все VP) | отсутствует (`null`) | 70 px / 67–71 px | **−70 px** |
| 7 | h1 fontSize (все VP) | 32 px | 18 px | **+14 px** |
| 8 | grid gap (все VP) | 18 px | 7 px (осн. сетка lordserials) | **+11 px** |
| 9 | contentWidth @1440/1920 | 1 148 px | 1 100 px | **+48 px** |
| 10 | contentWidth @390 | 342 px | 380 px | **−38 px** |
| 11 | grid columns @1024/1440 | 5 | 2 (lordserials) | **+3** |
| 12 | gutter @390 | 24 px | 5 px | **+19 px** |
| 13 | horizontalOverflow @768/@1024 | да | нет | **регресс** |
| 14 | body / a / p fontSize | 16 px | 14 px | **+2 px** |
| 15 | cardAspectRatio | 0.67 | 0.69 | **−0.02** |

Отдельно: у нас **отсутствует шапка** (`header = null` на всех пяти вьюпортах) и **отсутствует элемент `button`** (`typography.button = ABSENT`) — оба присутствуют во всех трёх Lords-референсах.

## I. Крупнейшие расхождения (ours-yummy)

| # | Метрика | Наше | old.yummyani.me | Gap |
|---|---|---|---|---|
| 1 | linkCount | 89 | 245 | **−156** |
| 2 | imageCount | 44 | 93 | **−49** |
| 3 | scrollHeight @1024 | 6 934 px | 8 063 px | **−1 129 px** |
| 4 | scrollHeight @768 | 7 411 px | 8 045 px | **−634 px** |
| 5 | scrollHeight @1440/1920 | 4 101 px | 4 555 px | **−454 px** |
| 6 | sectionCount | 1 | 2 | **−1** |
| 7 | contentWidth @390 | 378 px | 388 px | **−10 px** |
