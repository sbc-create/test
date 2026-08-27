# Lords Reference Measurements

Полный подьюпортный дамп замеров трёх Lords-релевантных референсов.
Источник: `/tmp/refmeas/{lordfilm-hit,lordfilm-title,lordserials}/measurements.json` на control-host.
Вьюпорты: 390, 768, 1024, 1440, 1920. Поле `errors` пустое у всех трёх.

| Референс | URL | measured_at (UTC) |
|---|---|---|
| lordfilm-hit | https://lordfilm-hit.org/ | 2026-08-27T15:06:30.913Z |
| lordfilm-title | https://lordfilm-hit.org/3629-bunker-2023.html | 2026-08-27T15:06:47.910Z |
| lordserials | https://lordserials.fan/ | 2026-08-27T15:07:03.610Z |

---

# 1. lordfilm-hit — https://lordfilm-hit.org/

## 1.1 Геометрия

| Поле | 390 | 768 | 1024 | 1440 | 1920 |
|---|---|---|---|---|---|
| documentWidth | 390 px | 768 px | 1024 px | 1440 px | 1920 px |
| contentWidth | 380 px | 758 px | 1000 px | 1100 px | 1100 px |
| gutter | 5 px | 5 px | 12 px | 170 px | 410 px |
| scrollHeight | 4 555 px | 2 881 px | 1 851 px | 1 972 px | 1 972 px |
| horizontalOverflow | нет | нет | нет | нет | нет |
| httpStatus | 200 | 200 | 200 | 200 | 200 |

## 1.2 Шапка

| Поле | 390 | 768 | 1024 | 1440 | 1920 |
|---|---|---|---|---|---|
| header.height | 70 px | 70 px | 70 px | 70 px | 70 px |
| header.position | relative | relative | relative | relative | relative |
| header.sticky | false | false | false | false | false |

## 1.3 Типографика (одинакова на всех вьюпортах)

| Роль | fontSize | lineHeight | fontWeight |
|---|---|---|---|
| body | 14 px | normal | 400 |
| h1 | 18 px | normal | 600 |
| h2 | отсутствует | отсутствует | отсутствует |
| h3 | отсутствует | отсутствует | отсутствует |
| a | 14 px | normal | 400 |
| p | 14 px | normal | 400 |
| button | 16 px | 40 px | 600 |

## 1.4 Пропорции карточек

| Вьюпорт | cardAspectRatios (ratio × count) |
|---|---|
| 390 | 0.69 × 28; 0.68 × 2; 2.57 × 1 |
| 768 | 0.69 × 28; 0.68 × 2; 2.57 × 1 |
| 1024 | 0.69 × 26; 0.68 × 2; 2.57 × 1; 0.67 × 1; 0.63 × 1 |
| 1440 | 0.69 × 26; 0.68 × 2; 2.57 × 1; 0.67 × 1; 0.63 × 1 |
| 1920 | 0.69 × 26; 0.68 × 2; 2.57 × 1; 0.67 × 1; 0.63 × 1 |

## 1.5 Сетки

`grids = []` на всех пяти вьюпортах — CSS Grid не обнаружен, число колонок **не измерено**.

## 1.6 Плеер

`player = null` на всех пяти вьюпортах — **не измерено** (главная страница).

## 1.7 Структура и объём

| Поле | 390 | 768 | 1024 | 1440 | 1920 |
|---|---|---|---|---|---|
| sectionCount | 4 | 4 | 4 | 4 | 4 |
| linkCount | 128 | 123 | 128 | 128 | 128 |
| imageCount | 33 | 31 | 33 | 33 | 32 |
| paginationLinks | 0 | 0 | 0 | 0 | 0 |

## 1.8 topLevelSections (tag / height px / childCount)

| # | 390 | 768 | 1024 | 1440 | 1920 |
|---|---|---|---|---|---|
| 0 | h1 / 42 / 0 | h1 / 21 / 0 | h1 / 21 / 0 | h1 / 21 / 0 | h1 / 21 / 0 |
| 1 | div / 1676 / 2 | div / 860.8 / 2 | div / 509.59 / 2 | div / 557.91 / 2 | div / 557.91 / 2 |
| 2 | div / 1676 / 2 | div / 860.8 / 2 | div / 509.59 / 2 | div / 557.91 / 2 | div / 557.91 / 2 |
| 3 | div / 863 / 2 | div / 590.53 / 2 | div / 279.8 / 2 | div / 303.95 / 2 | div / 303.95 / 2 |

---

# 2. lordfilm-title — https://lordfilm-hit.org/3629-bunker-2023.html

## 2.1 Геометрия

| Поле | 390 | 768 | 1024 | 1440 | 1920 |
|---|---|---|---|---|---|
| documentWidth | 390 px | 768 px | 1024 px | 1440 px | 1920 px |
| contentWidth | 380 px | 758 px | 1000 px | 1100 px | 1100 px |
| gutter | 5 px | 5 px | 12 px | 170 px | 410 px |
| scrollHeight | 3 591 px | 3 206 px | 2 778 px | 2 860 px | 2 860 px |
| horizontalOverflow | нет | **да** | **да** | нет | нет |
| httpStatus | 200 | 200 | 200 | 200 | 200 |

## 2.2 Шапка

| Поле | 390 | 768 | 1024 | 1440 | 1920 |
|---|---|---|---|---|---|
| header.height | 70 px | 70 px | 70 px | 70 px | 70 px |
| header.position | relative | relative | relative | relative | relative |
| header.sticky | false | false | false | false | false |

## 2.3 Типографика (одинакова на всех вьюпортах)

| Роль | fontSize | lineHeight | fontWeight |
|---|---|---|---|
| body | 14 px | normal | 400 |
| h1 | 18 px | normal | 600 |
| h2 | 16 px | normal | 600 |
| h3 | 16 px | normal | 600 |
| a | 14 px | normal | 400 |
| p | 14 px | normal | 400 |
| button | 16 px | 40 px | 600 |

## 2.4 Пропорции карточек

| Вьюпорт | cardAspectRatios (ratio × count) |
|---|---|
| 390 | 0.69 × 6; 2.57 × 1 |
| 768 | 0.69 × 6; 2.57 × 1 |
| 1024 | 0.69 × 6; 2.57 × 1 |
| 1440 | 0.69 × 6; 2.57 × 1 |
| 1920 | 0.69 × 6; 2.57 × 1 |

## 2.5 Сетки

`grids = []` на всех пяти вьюпортах — число колонок **не измерено**.

## 2.6 Плеер (единственная страница, где плеер измерен)

| Поле | 390 | 768 | 1024 | 1440 | 1920 |
|---|---|---|---|---|---|
| player.width | 390 px | 768 px | 1000 px | 1100 px | 1100 px |
| player.height | 300 px | 460 px | 460 px | 460 px | 460 px |
| player.aspectRatio | 1.30 | 1.67 | 2.17 | 2.39 | 2.39 |
| player.tag | video-player | video-player | video-player | video-player | video-player |

Ширина плеера на 390 (390 px) и на 768 (768 px) превышает contentWidth (380 px и 758 px) — этому соответствует `horizontalOverflow = да` на 768 и 1024.

## 2.7 Структура и объём

| Поле | 390 | 768 | 1024 | 1440 | 1920 |
|---|---|---|---|---|---|
| sectionCount | 2 | 2 | 2 | 2 | 2 |
| linkCount | 116 | 116 | 116 | 116 | 116 |
| imageCount | 10 | 10 | 10 | 10 | 11 |
| paginationLinks | 0 | 0 | 0 | 0 | 0 |

## 2.8 topLevelSections (tag / height px / childCount)

| # | 390 | 768 | 1024 | 1440 | 1920 |
|---|---|---|---|---|---|
| 0 | div / 14 / 1 | div / 14 / 1 | div / 14 / 1 | div / 14 / 1 | div / 14 / 1 |
| 1 | div / 3318.61 / 2 | div / 2683.66 / 2 | div / 2272.83 / 2 | div / 2355.39 / 2 | div / 2355.39 / 2 |

---

# 3. lordserials — https://lordserials.fan/

## 3.1 Геометрия

| Поле | 390 | 768 | 1024 | 1440 | 1920 |
|---|---|---|---|---|---|
| documentWidth | 390 px | 768 px | 1024 px | 1440 px | 1920 px |
| contentWidth | 380 px | 758 px | 1000 px | 1100 px | 1100 px |
| gutter | 5 px | 5 px | 12 px | 170 px | 410 px |
| scrollHeight | 12 756 px | 7 307 px | 4 955 px | 5 246 px | 5 246 px |
| horizontalOverflow | нет | нет | нет | нет | нет |
| httpStatus | 200 | 200 | 200 | 200 | 200 |

## 3.2 Шапка

| Поле | 390 | 768 | 1024 | 1440 | 1920 |
|---|---|---|---|---|---|
| header.height | 67 px | 67 px | 71 px | 71 px | 71 px |
| header.position | relative | relative | relative | relative | relative |
| header.sticky | false | false | false | false | false |

## 3.3 Типографика (одинакова на всех вьюпортах)

| Роль | fontSize | lineHeight | fontWeight |
|---|---|---|---|
| body | 14 px | normal | 400 |
| h1 | 18 px | normal | 600 |
| h2 | отсутствует | отсутствует | отсутствует |
| h3 | отсутствует | отсутствует | отсутствует |
| a | 14 px | normal | 400 |
| p | 13 px | 22.1 px | 400 |
| button | 15 px | normal | 400 |

## 3.4 Пропорции карточек

| Вьюпорт | cardAspectRatios (ratio × count) |
|---|---|
| 390 | 0.69 × 74; 0.67 × 22; 3.43 × 2; 2.07 × 1; 2.57 × 1 |
| 768 | 0.69 × 62; 0.67 × 34; 2.57 × 2; 2.72 × 2 |
| 1024 | 0.67 × 49; 0.69 × 47; 2.57 × 2; 3.13 × 2 |
| 1440 | 0.69 × 49; 0.67 × 47; 2.57 × 2; 3.48 × 2 |
| 1920 | 0.69 × 49; 0.67 × 47; 2.57 × 2; 3.48 × 2 |

## 3.5 Сетки (columns × gap px, children) — по 9 сеток на каждом вьюпорте

| Сетка # | children | 390 | 768 | 1024 | 1440 | 1920 |
|---|---|---|---|---|---|---|
| 1 | 2 | 3 × 12 px | 3 × 12 px | 2 × 12 px | 2 × 12 px | 2 × 12 px |
| 2 | 4 | 4 × 16 px | 4 × 16 px | 4 × 16 px | 4 × 20 px | 4 × 20 px |
| 3 | 7 | 3 × 7 px | 3 × 7 px | 2 × 7 px | 2 × 7 px | 2 × 7 px |
| 4 | 19 | 3 × 7 px | 3 × 7 px | 2 × 7 px | 2 × 7 px | 2 × 7 px |
| 5 | 2 | 3 × 12 px | 3 × 12 px | 2 × 12 px | 2 × 12 px | 2 × 12 px |
| 6 | 2 | 3 × 28 px | 3 × 28 px | 2 × 28 px | 2 × 28 px | 2 × 28 px |
| 7 | 6 | 2 × 10 px | 2 × 10 px | 2 × 10 px | 2 × 10 px | 2 × 10 px |
| 8 | 2 | 1 × 8 px | 1 × 8 px | 1 × 8 px | 1 × 8 px | 1 × 8 px |
| 9 | 2 | 1 × 10 px | 2 × 12 px | 2 × 16 px | 2 × 16 px | 2 × 16 px |

Сетка #4 (19 детей) — крупнейшая контентная сетка: 3 колонки / gap 7 px на 390 и 768, 2 колонки / gap 7 px на 1024, 1440, 1920.

## 3.6 Плеер

`player = null` на всех пяти вьюпортах — **не измерено** (главная страница).

## 3.7 Структура и объём

| Поле | 390 | 768 | 1024 | 1440 | 1920 |
|---|---|---|---|---|---|
| sectionCount | 10 | 10 | 10 | 10 | 10 |
| linkCount | 257 | 257 | 257 | 257 | 257 |
| imageCount | 101 | 101 | 101 | 101 | 101 |
| paginationLinks | 0 | 0 | 0 | 0 | 0 |

## 3.8 topLevelSections (tag / height px / childCount)

Все секции имеют tag `div`. Индексы в JSON — 0, 1, 3, 5, 6, 7, 8, 9, 10, 11 (индексы 2 и 4 в дампе отсутствуют).

| index | childCount | 390 | 768 | 1024 | 1440 | 1920 |
|---|---|---|---|---|---|---|
| 0 | 2 | 305 px | 304.27 px | 310.8 px | 288.06 px | 288.06 px |
| 1 | 2 | 44.8 px | 26.39 px | 26.39 px | 26.39 px | 26.39 px |
| 3 | 1 | 246 px | 158 px | 181 px | 181 px | 181 px |
| 5 | 2 | 2 489 px | 1 401.33 px | 739.39 px | 811.86 px | 811.86 px |
| 6 | 2 | 1 676 px | 860.8 px | 509.59 px | 557.91 px | 557.91 px |
| 7 | 2 | 1 676 px | 860.8 px | 509.59 px | 557.91 px | 557.91 px |
| 8 | 2 | 1 676 px | 860.8 px | 509.59 px | 557.91 px | 557.91 px |
| 9 | 2 | 1 676 px | 860.8 px | 509.59 px | 557.91 px | 557.91 px |
| 10 | 2 | 1 676 px | 860.8 px | 509.59 px | 557.91 px | 557.91 px |
| 11 | 11 | 893.09 px | 495.41 px | 473.31 px | 473.31 px | 473.31 px |

Секции 6–10 — пять идентичных по высоте рядов карусельных блоков; их высота совпадает с высотой секций 1 и 2 у lordfilm-hit (1676 / 860.8 / 509.59 / 557.91 px) — то есть у обоих сайтов один и тот же блок ряда карточек.

---

# 4. Сводка совпадений между тремя референсами

| Метрика | Совпадение |
|---|---|
| contentWidth (все VP) | полное: 380 / 758 / 1000 / 1100 / 1100 px |
| gutter (все VP) | полное: 5 / 5 / 12 / 170 / 410 px |
| body fontSize | полное: 14 px / 400 |
| h1 | полное: 18 px / 600 |
| a fontSize | полное: 14 px / 400 |
| header.sticky | полное: false |
| header.position | полное: relative |
| header.height | 70 px (lordfilm-hit, lordfilm-title) vs 67–71 px (lordserials) |
| p fontSize | 14 px (hit, title) vs 13 px / lh 22.1 px (lordserials) |
| button | 16 px / lh 40 px / 600 (hit, title) vs 15 px / normal / 400 (lordserials) |
| доминирующее cardAspectRatio | 0.69 у всех трёх |
| широкий баннер | 2.57 у всех трёх |
| paginationLinks | 0 у всех трёх на всех VP |
| grids | измеримы только у lordserials |
