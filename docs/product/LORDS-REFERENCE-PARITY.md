# Сверка Lords с настоящим эталоном

Эталон: `https://lordfilm-hit.org`, снят 2026-09-13T08:16:55.814Z.
Витрина: `http://127.0.0.1:39609`, замер 2026-09-13T08:17:03.125Z.

Сопоставление архетипов задано явно, а не по совпадению названий:

- эталон `home` ↔ слот витрины `home`
- эталон `catalog` ↔ слот витрины `catalog`
- эталон `genre` ↔ слот витрины `genres`
- эталон `search` ↔ слот витрины `search`
- эталон `not_found` ↔ слот витрины `not-found`

| Проверок | BLOCKED_REFERENCE | FAIL | NOT_COMPARABLE_BY_SELECTOR | PASS |
| ---: | ---: | ---: | ---: | ---: |
| 350 | 7 | 13 | 35 | 295 |

ΔE (CIE76) по измеренным цветам: медиана 0.0, p95 0.0; порог медианы 3.0, p95 6.0.

SSIM и наложение не вычислялись: в окружении нет библиотек обработки
изображений, а установка потребовала бы сетевого доступа, которого
владелец не разрешал. Снимки эталона сняты и сохранены — посчитать
можно будет, не переснимая.

| Архетип | Вьюпорт | Поле | Эталон | Наше | Вердикт |
| --- | ---: | --- | --- | --- | --- |
| home | 360 | ширина контейнера | 350.0 | 350.0 | PASS |
| home | 360 | высота шапки | 70 | 71 | PASS |
| home | 360 | положение шапки | relative | relative | PASS |
| home | 360 | кегль body | 14px/400 | 14px/400 | PASS |
| home | 360 | кегль h1 | 18px/600 | 18px/600 | PASS |
| home | 360 | кегль a | 14px/400 | 14px/400 | PASS |
| home | 360 | кегль p | 14px/400 | 14px/400 | PASS |
| home | 360 | ΔE фона | rgb(17, 17, 17) | rgb(17, 17, 17) | PASS |
| home | 360 | ΔE текста | rgb(68, 68, 68) | rgb(230, 230, 230) | NOT_COMPARABLE_BY_SELECTOR |
| home | 360 | горизонтальная прокрутка | False | False | PASS |
| home | 390 | ширина контейнера | 380.0 | 380.0 | PASS |
| home | 390 | высота шапки | 70 | 71 | PASS |
| home | 390 | положение шапки | relative | relative | PASS |
| home | 390 | кегль body | 14px/400 | 14px/400 | PASS |
| home | 390 | кегль h1 | 18px/600 | 18px/600 | PASS |
| home | 390 | кегль a | 14px/400 | 14px/400 | PASS |
| home | 390 | кегль p | 14px/400 | 14px/400 | PASS |
| home | 390 | ΔE фона | rgb(17, 17, 17) | rgb(17, 17, 17) | PASS |
| home | 390 | ΔE текста | rgb(68, 68, 68) | rgb(230, 230, 230) | NOT_COMPARABLE_BY_SELECTOR |
| home | 390 | горизонтальная прокрутка | False | False | PASS |
| home | 768 | ширина контейнера | 758.0 | 758.0 | PASS |
| home | 768 | высота шапки | 70 | 71 | PASS |
| home | 768 | положение шапки | relative | relative | PASS |
| home | 768 | кегль body | 14px/400 | 14px/400 | PASS |
| home | 768 | кегль h1 | 18px/600 | 18px/600 | PASS |
| home | 768 | кегль a | 14px/400 | 14px/400 | PASS |
| home | 768 | кегль p | 14px/400 | 14px/400 | PASS |
| home | 768 | ΔE фона | rgb(17, 17, 17) | rgb(17, 17, 17) | PASS |
| home | 768 | ΔE текста | rgb(68, 68, 68) | rgb(230, 230, 230) | NOT_COMPARABLE_BY_SELECTOR |
| home | 768 | горизонтальная прокрутка | False | False | PASS |
| home | 1024 | ширина контейнера | 1000.0 | 1000.0 | PASS |
| home | 1024 | высота шапки | 70 | 71 | PASS |
| home | 1024 | положение шапки | relative | relative | PASS |
| home | 1024 | кегль body | 14px/400 | 14px/400 | PASS |
| home | 1024 | кегль h1 | 18px/600 | 18px/600 | PASS |
| home | 1024 | кегль a | 14px/400 | 14px/400 | PASS |
| home | 1024 | кегль p | 14px/400 | 14px/400 | PASS |
| home | 1024 | ΔE фона | rgb(17, 17, 17) | rgb(17, 17, 17) | PASS |
| home | 1024 | ΔE текста | rgb(68, 68, 68) | rgb(230, 230, 230) | NOT_COMPARABLE_BY_SELECTOR |
| home | 1024 | горизонтальная прокрутка | False | False | PASS |
| home | 1366 | ширина контейнера | 1100.0 | 1100.0 | PASS |
| home | 1366 | высота шапки | 70 | 71 | PASS |
| home | 1366 | положение шапки | relative | relative | PASS |
| home | 1366 | кегль body | 14px/400 | 14px/400 | PASS |
| home | 1366 | кегль h1 | 18px/600 | 18px/600 | PASS |
| home | 1366 | кегль a | 14px/400 | 14px/400 | PASS |
| home | 1366 | кегль p | 14px/400 | 14px/400 | PASS |
| home | 1366 | ΔE фона | rgb(17, 17, 17) | rgb(17, 17, 17) | PASS |
| home | 1366 | ΔE текста | rgb(68, 68, 68) | rgb(230, 230, 230) | NOT_COMPARABLE_BY_SELECTOR |
| home | 1366 | горизонтальная прокрутка | False | False | PASS |
| home | 1440 | ширина контейнера | 1100.0 | 1100.0 | PASS |
| home | 1440 | высота шапки | 70 | 71 | PASS |
| home | 1440 | положение шапки | relative | relative | PASS |
| home | 1440 | кегль body | 14px/400 | 14px/400 | PASS |
| home | 1440 | кегль h1 | 18px/600 | 18px/600 | PASS |
| home | 1440 | кегль a | 14px/400 | 14px/400 | PASS |
| home | 1440 | кегль p | 14px/400 | 14px/400 | PASS |
| home | 1440 | ΔE фона | rgb(17, 17, 17) | rgb(17, 17, 17) | PASS |
| home | 1440 | ΔE текста | rgb(68, 68, 68) | rgb(230, 230, 230) | NOT_COMPARABLE_BY_SELECTOR |
| home | 1440 | горизонтальная прокрутка | False | False | PASS |
| home | 1920 | ширина контейнера | 1100.0 | 1100.0 | PASS |
| home | 1920 | высота шапки | 70 | 71 | PASS |
| home | 1920 | положение шапки | relative | relative | PASS |
| home | 1920 | кегль body | 14px/400 | 14px/400 | PASS |
| home | 1920 | кегль h1 | 18px/600 | 18px/600 | PASS |
| home | 1920 | кегль a | 14px/400 | 14px/400 | PASS |
| home | 1920 | кегль p | 14px/400 | 14px/400 | PASS |
| home | 1920 | ΔE фона | rgb(17, 17, 17) | rgb(17, 17, 17) | PASS |
| home | 1920 | ΔE текста | rgb(68, 68, 68) | rgb(230, 230, 230) | NOT_COMPARABLE_BY_SELECTOR |
| home | 1920 | горизонтальная прокрутка | False | False | PASS |
| catalog | 360 | ширина контейнера | 350.0 | 350.0 | PASS |
| catalog | 360 | высота шапки | 70 | 71 | PASS |
| catalog | 360 | положение шапки | relative | relative | PASS |
| catalog | 360 | кегль body | 14px/400 | 14px/400 | PASS |
| catalog | 360 | кегль h1 | 18px/600 | 18px/600 | PASS |
| catalog | 360 | кегль a | 14px/400 | 14px/400 | PASS |
| catalog | 360 | кегль p | 14px/400 | 13.6px/400 | PASS |
| catalog | 360 | ΔE фона | rgb(17, 17, 17) | rgb(17, 17, 17) | PASS |
| catalog | 360 | ΔE текста | rgb(68, 68, 68) | rgb(230, 230, 230) | NOT_COMPARABLE_BY_SELECTOR |
| catalog | 360 | горизонтальная прокрутка | False | False | PASS |
| catalog | 390 | ширина контейнера | 380.0 | 380.0 | PASS |
| catalog | 390 | высота шапки | 70 | 71 | PASS |
| catalog | 390 | положение шапки | relative | relative | PASS |
| catalog | 390 | кегль body | 14px/400 | 14px/400 | PASS |
| catalog | 390 | кегль h1 | 18px/600 | 18px/600 | PASS |
| catalog | 390 | кегль a | 14px/400 | 14px/400 | PASS |
| catalog | 390 | кегль p | 14px/400 | 13.6px/400 | PASS |
| catalog | 390 | ΔE фона | rgb(17, 17, 17) | rgb(17, 17, 17) | PASS |
| catalog | 390 | ΔE текста | rgb(68, 68, 68) | rgb(230, 230, 230) | NOT_COMPARABLE_BY_SELECTOR |
| catalog | 390 | горизонтальная прокрутка | False | False | PASS |
| catalog | 768 | ширина контейнера | 758.0 | 758.0 | PASS |
| catalog | 768 | высота шапки | 70 | 71 | PASS |
| catalog | 768 | положение шапки | relative | relative | PASS |
| catalog | 768 | кегль body | 14px/400 | 14px/400 | PASS |
| catalog | 768 | кегль h1 | 18px/600 | 18px/600 | PASS |
| catalog | 768 | кегль a | 14px/400 | 14px/400 | PASS |
| catalog | 768 | кегль p | 14px/400 | 13.6px/400 | PASS |
| catalog | 768 | ΔE фона | rgb(17, 17, 17) | rgb(17, 17, 17) | PASS |
| catalog | 768 | ΔE текста | rgb(68, 68, 68) | rgb(230, 230, 230) | NOT_COMPARABLE_BY_SELECTOR |
| catalog | 768 | горизонтальная прокрутка | False | False | PASS |
| catalog | 1024 | ширина контейнера | 1000.0 | 1000.0 | PASS |
| catalog | 1024 | высота шапки | 70 | 71 | PASS |
| catalog | 1024 | положение шапки | relative | relative | PASS |
| catalog | 1024 | кегль body | 14px/400 | 14px/400 | PASS |
| catalog | 1024 | кегль h1 | 18px/600 | 18px/600 | PASS |
| catalog | 1024 | кегль a | 14px/400 | 14px/400 | PASS |
| catalog | 1024 | кегль p | 14px/400 | 13.6px/400 | PASS |
| catalog | 1024 | ΔE фона | rgb(17, 17, 17) | rgb(17, 17, 17) | PASS |
| catalog | 1024 | ΔE текста | rgb(68, 68, 68) | rgb(230, 230, 230) | NOT_COMPARABLE_BY_SELECTOR |
| catalog | 1024 | горизонтальная прокрутка | False | False | PASS |
| catalog | 1366 | ширина контейнера | 1100.0 | 1100.0 | PASS |
| catalog | 1366 | высота шапки | 70 | 71 | PASS |
| catalog | 1366 | положение шапки | relative | relative | PASS |
| catalog | 1366 | кегль body | 14px/400 | 14px/400 | PASS |
| catalog | 1366 | кегль h1 | 18px/600 | 18px/600 | PASS |
| catalog | 1366 | кегль a | 14px/400 | 14px/400 | PASS |
| catalog | 1366 | кегль p | 14px/400 | 13.6px/400 | PASS |
| catalog | 1366 | ΔE фона | rgb(17, 17, 17) | rgb(17, 17, 17) | PASS |
| catalog | 1366 | ΔE текста | rgb(68, 68, 68) | rgb(230, 230, 230) | NOT_COMPARABLE_BY_SELECTOR |
| catalog | 1366 | горизонтальная прокрутка | False | False | PASS |
| catalog | 1440 | ширина контейнера | 1100.0 | 1100.0 | PASS |
| catalog | 1440 | высота шапки | 70 | 71 | PASS |
| catalog | 1440 | положение шапки | relative | relative | PASS |
| catalog | 1440 | кегль body | 14px/400 | 14px/400 | PASS |
| catalog | 1440 | кегль h1 | 18px/600 | 18px/600 | PASS |
| catalog | 1440 | кегль a | 14px/400 | 14px/400 | PASS |
| catalog | 1440 | кегль p | 14px/400 | 13.6px/400 | PASS |
| catalog | 1440 | ΔE фона | rgb(17, 17, 17) | rgb(17, 17, 17) | PASS |
| catalog | 1440 | ΔE текста | rgb(68, 68, 68) | rgb(230, 230, 230) | NOT_COMPARABLE_BY_SELECTOR |
| catalog | 1440 | горизонтальная прокрутка | False | False | PASS |
| catalog | 1920 | ширина контейнера | 1100.0 | 1100.0 | PASS |
| catalog | 1920 | высота шапки | 70 | 71 | PASS |
| catalog | 1920 | положение шапки | relative | relative | PASS |
| catalog | 1920 | кегль body | 14px/400 | 14px/400 | PASS |
| catalog | 1920 | кегль h1 | 18px/600 | 18px/600 | PASS |
| catalog | 1920 | кегль a | 14px/400 | 14px/400 | PASS |
| catalog | 1920 | кегль p | 14px/400 | 13.6px/400 | PASS |
| catalog | 1920 | ΔE фона | rgb(17, 17, 17) | rgb(17, 17, 17) | PASS |
| catalog | 1920 | ΔE текста | rgb(68, 68, 68) | rgb(230, 230, 230) | NOT_COMPARABLE_BY_SELECTOR |
| catalog | 1920 | горизонтальная прокрутка | False | False | PASS |
| genre | 360 | ширина контейнера | 350.0 | 350.0 | PASS |
| genre | 360 | высота шапки | 70 | 71 | PASS |
| genre | 360 | положение шапки | relative | relative | PASS |
| genre | 360 | кегль body | 14px/400 | 14px/400 | PASS |
| genre | 360 | кегль h1 | 18px/600 | 18px/600 | PASS |
| genre | 360 | кегль a | 14px/400 | 14px/400 | PASS |
| genre | 360 | кегль p | 14px/400 | 13.6px/400 | PASS |
| genre | 360 | ΔE фона | rgb(17, 17, 17) | rgb(17, 17, 17) | PASS |
| genre | 360 | ΔE текста | rgb(68, 68, 68) | rgb(230, 230, 230) | NOT_COMPARABLE_BY_SELECTOR |
| genre | 360 | горизонтальная прокрутка | False | False | PASS |
| genre | 390 | ширина контейнера | 380.0 | 380.0 | PASS |
| genre | 390 | высота шапки | 70 | 71 | PASS |
| genre | 390 | положение шапки | relative | relative | PASS |
| genre | 390 | кегль body | 14px/400 | 14px/400 | PASS |
| genre | 390 | кегль h1 | 18px/600 | 18px/600 | PASS |
| genre | 390 | кегль a | 14px/400 | 14px/400 | PASS |
| genre | 390 | кегль p | 14px/400 | 13.6px/400 | PASS |
| genre | 390 | ΔE фона | rgb(17, 17, 17) | rgb(17, 17, 17) | PASS |
| genre | 390 | ΔE текста | rgb(68, 68, 68) | rgb(230, 230, 230) | NOT_COMPARABLE_BY_SELECTOR |
| genre | 390 | горизонтальная прокрутка | False | False | PASS |
| genre | 768 | ширина контейнера | 758.0 | 758.0 | PASS |
| genre | 768 | высота шапки | 70 | 71 | PASS |
| genre | 768 | положение шапки | relative | relative | PASS |
| genre | 768 | кегль body | 14px/400 | 14px/400 | PASS |
| genre | 768 | кегль h1 | 18px/600 | 18px/600 | PASS |
| genre | 768 | кегль a | 14px/400 | 14px/400 | PASS |
| genre | 768 | кегль p | 14px/400 | 13.6px/400 | PASS |
| genre | 768 | ΔE фона | rgb(17, 17, 17) | rgb(17, 17, 17) | PASS |
| genre | 768 | ΔE текста | rgb(68, 68, 68) | rgb(230, 230, 230) | NOT_COMPARABLE_BY_SELECTOR |
| genre | 768 | горизонтальная прокрутка | False | False | PASS |
| genre | 1024 | ширина контейнера | 1000.0 | 1000.0 | PASS |
| genre | 1024 | высота шапки | 70 | 71 | PASS |
| genre | 1024 | положение шапки | relative | relative | PASS |
| genre | 1024 | кегль body | 14px/400 | 14px/400 | PASS |
| genre | 1024 | кегль h1 | 18px/600 | 18px/600 | PASS |
| genre | 1024 | кегль a | 14px/400 | 14px/400 | PASS |
| genre | 1024 | кегль p | 14px/400 | 13.6px/400 | PASS |
| genre | 1024 | ΔE фона | rgb(17, 17, 17) | rgb(17, 17, 17) | PASS |
| genre | 1024 | ΔE текста | rgb(68, 68, 68) | rgb(230, 230, 230) | NOT_COMPARABLE_BY_SELECTOR |
| genre | 1024 | горизонтальная прокрутка | False | False | PASS |
| genre | 1366 | ширина контейнера | 1100.0 | 1100.0 | PASS |
| genre | 1366 | высота шапки | 70 | 71 | PASS |
| genre | 1366 | положение шапки | relative | relative | PASS |
| genre | 1366 | кегль body | 14px/400 | 14px/400 | PASS |
| genre | 1366 | кегль h1 | 18px/600 | 18px/600 | PASS |
| genre | 1366 | кегль a | 14px/400 | 14px/400 | PASS |
| genre | 1366 | кегль p | 14px/400 | 13.6px/400 | PASS |
| genre | 1366 | ΔE фона | rgb(17, 17, 17) | rgb(17, 17, 17) | PASS |
| genre | 1366 | ΔE текста | rgb(68, 68, 68) | rgb(230, 230, 230) | NOT_COMPARABLE_BY_SELECTOR |
| genre | 1366 | горизонтальная прокрутка | False | False | PASS |
| genre | 1440 | ширина контейнера | 1100.0 | 1100.0 | PASS |
| genre | 1440 | высота шапки | 70 | 71 | PASS |
| genre | 1440 | положение шапки | relative | relative | PASS |
| genre | 1440 | кегль body | 14px/400 | 14px/400 | PASS |
| genre | 1440 | кегль h1 | 18px/600 | 18px/600 | PASS |
| genre | 1440 | кегль a | 14px/400 | 14px/400 | PASS |
| genre | 1440 | кегль p | 14px/400 | 13.6px/400 | PASS |
| genre | 1440 | ΔE фона | rgb(17, 17, 17) | rgb(17, 17, 17) | PASS |
| genre | 1440 | ΔE текста | rgb(68, 68, 68) | rgb(230, 230, 230) | NOT_COMPARABLE_BY_SELECTOR |
| genre | 1440 | горизонтальная прокрутка | False | False | PASS |
| genre | 1920 | ширина контейнера | 1100.0 | 1100.0 | PASS |
| genre | 1920 | высота шапки | 70 | 71 | PASS |
| genre | 1920 | положение шапки | relative | relative | PASS |
| genre | 1920 | кегль body | 14px/400 | 14px/400 | PASS |
| genre | 1920 | кегль h1 | 18px/600 | 18px/600 | PASS |
| genre | 1920 | кегль a | 14px/400 | 14px/400 | PASS |
| genre | 1920 | кегль p | 14px/400 | 13.6px/400 | PASS |
| genre | 1920 | ΔE фона | rgb(17, 17, 17) | rgb(17, 17, 17) | PASS |
| genre | 1920 | ΔE текста | rgb(68, 68, 68) | rgb(230, 230, 230) | NOT_COMPARABLE_BY_SELECTOR |
| genre | 1920 | горизонтальная прокрутка | False | False | PASS |
| search | 360 | ширина контейнера | 340.0 | 350.0 | FAIL |
| search | 360 | высота шапки | 70 | 71 | PASS |
| search | 360 | положение шапки | relative | relative | PASS |
| search | 360 | кегль body | 14px/400 | 14px/400 | PASS |
| search | 360 | кегль h1 | 24px/600 | 18px/600 | FAIL |
| search | 360 | кегль a | 14px/400 | 14px/400 | PASS |
| search | 360 | кегль p | 14px/400 | 14px/400 | PASS |
| search | 360 | ΔE фона | rgb(17, 17, 17) | rgb(17, 17, 17) | PASS |
| search | 360 | ΔE текста | rgb(68, 68, 68) | rgb(230, 230, 230) | NOT_COMPARABLE_BY_SELECTOR |
| search | 360 | горизонтальная прокрутка | False | False | PASS |
| search | 390 | ширина контейнера | 370.0 | 380.0 | FAIL |
| search | 390 | высота шапки | 70 | 71 | PASS |
| search | 390 | положение шапки | relative | relative | PASS |
| search | 390 | кегль body | 14px/400 | 14px/400 | PASS |
| search | 390 | кегль h1 | 24px/600 | 18px/600 | FAIL |
| search | 390 | кегль a | 14px/400 | 14px/400 | PASS |
| search | 390 | кегль p | 14px/400 | 14px/400 | PASS |
| search | 390 | ΔE фона | rgb(17, 17, 17) | rgb(17, 17, 17) | PASS |
| search | 390 | ΔE текста | rgb(68, 68, 68) | rgb(230, 230, 230) | NOT_COMPARABLE_BY_SELECTOR |
| search | 390 | горизонтальная прокрутка | False | False | PASS |
| search | 768 | ширина контейнера | 748.0 | 758.0 | FAIL |
| search | 768 | высота шапки | 70 | 71 | PASS |
| search | 768 | положение шапки | relative | relative | PASS |
| search | 768 | кегль body | 14px/400 | 14px/400 | PASS |
| search | 768 | кегль h1 | 24px/600 | 18px/600 | FAIL |
| search | 768 | кегль a | 14px/400 | 14px/400 | PASS |
| search | 768 | кегль p | 14px/400 | 14px/400 | PASS |
| search | 768 | ΔE фона | rgb(17, 17, 17) | rgb(17, 17, 17) | PASS |
| search | 768 | ΔE текста | rgb(68, 68, 68) | rgb(230, 230, 230) | NOT_COMPARABLE_BY_SELECTOR |
| search | 768 | горизонтальная прокрутка | False | False | PASS |
| search | 1024 | ширина контейнера | 1000.0 | 1000.0 | PASS |
| search | 1024 | высота шапки | 70 | 71 | PASS |
| search | 1024 | положение шапки | relative | relative | PASS |
| search | 1024 | кегль body | 14px/400 | 14px/400 | PASS |
| search | 1024 | кегль h1 | 24px/600 | 18px/600 | FAIL |
| search | 1024 | кегль a | 14px/400 | 14px/400 | PASS |
| search | 1024 | кегль p | 14px/400 | 14px/400 | PASS |
| search | 1024 | ΔE фона | rgb(17, 17, 17) | rgb(17, 17, 17) | PASS |
| search | 1024 | ΔE текста | rgb(68, 68, 68) | rgb(230, 230, 230) | NOT_COMPARABLE_BY_SELECTOR |
| search | 1024 | горизонтальная прокрутка | False | False | PASS |
| search | 1366 | ширина контейнера | 1100.0 | 1100.0 | PASS |
| search | 1366 | высота шапки | 70 | 71 | PASS |
| search | 1366 | положение шапки | relative | relative | PASS |
| search | 1366 | кегль body | 14px/400 | 14px/400 | PASS |
| search | 1366 | кегль h1 | 24px/600 | 18px/600 | FAIL |
| search | 1366 | кегль a | 14px/400 | 14px/400 | PASS |
| search | 1366 | кегль p | 14px/400 | 14px/400 | PASS |
| search | 1366 | ΔE фона | rgb(17, 17, 17) | rgb(17, 17, 17) | PASS |
| search | 1366 | ΔE текста | rgb(68, 68, 68) | rgb(230, 230, 230) | NOT_COMPARABLE_BY_SELECTOR |
| search | 1366 | горизонтальная прокрутка | False | False | PASS |
| search | 1440 | ширина контейнера | 1100.0 | 1100.0 | PASS |
| search | 1440 | высота шапки | 70 | 71 | PASS |
| search | 1440 | положение шапки | relative | relative | PASS |
| search | 1440 | кегль body | 14px/400 | 14px/400 | PASS |
| search | 1440 | кегль h1 | 24px/600 | 18px/600 | FAIL |
| search | 1440 | кегль a | 14px/400 | 14px/400 | PASS |
| search | 1440 | кегль p | 14px/400 | 14px/400 | PASS |
| search | 1440 | ΔE фона | rgb(17, 17, 17) | rgb(17, 17, 17) | PASS |
| search | 1440 | ΔE текста | rgb(68, 68, 68) | rgb(230, 230, 230) | NOT_COMPARABLE_BY_SELECTOR |
| search | 1440 | горизонтальная прокрутка | False | False | PASS |
| search | 1920 | ширина контейнера | 1100.0 | 1100.0 | PASS |
| search | 1920 | высота шапки | 70 | 71 | PASS |
| search | 1920 | положение шапки | relative | relative | PASS |
| search | 1920 | кегль body | 14px/400 | 14px/400 | PASS |
| search | 1920 | кегль h1 | 24px/600 | 18px/600 | FAIL |
| search | 1920 | кегль a | 14px/400 | 14px/400 | PASS |
| search | 1920 | кегль p | 14px/400 | 14px/400 | PASS |
| search | 1920 | ΔE фона | rgb(17, 17, 17) | rgb(17, 17, 17) | PASS |
| search | 1920 | ΔE текста | rgb(68, 68, 68) | rgb(230, 230, 230) | NOT_COMPARABLE_BY_SELECTOR |
| search | 1920 | горизонтальная прокрутка | False | False | PASS |
| not_found | 360 | ширина контейнера | 280.0 | 350.0 | FAIL |
| not_found | 360 | высота шапки | 70 | 71 | PASS |
| not_found | 360 | положение шапки | relative | relative | PASS |
| not_found | 360 | кегль body | 14px/400 | 14px/400 | PASS |
| not_found | 360 | кегль h1 | роли нет у эталона | — | BLOCKED_REFERENCE |
| not_found | 360 | кегль a | 14px/400 | 14px/400 | PASS |
| not_found | 360 | кегль p | 14px/400 | 14px/400 | PASS |
| not_found | 360 | ΔE фона | rgb(17, 17, 17) | rgb(17, 17, 17) | PASS |
| not_found | 360 | ΔE текста | rgb(68, 68, 68) | rgb(230, 230, 230) | NOT_COMPARABLE_BY_SELECTOR |
| not_found | 360 | горизонтальная прокрутка | False | False | PASS |
| not_found | 390 | ширина контейнера | 280.0 | 380.0 | FAIL |
| not_found | 390 | высота шапки | 70 | 71 | PASS |
| not_found | 390 | положение шапки | relative | relative | PASS |
| not_found | 390 | кегль body | 14px/400 | 14px/400 | PASS |
| not_found | 390 | кегль h1 | роли нет у эталона | — | BLOCKED_REFERENCE |
| not_found | 390 | кегль a | 14px/400 | 14px/400 | PASS |
| not_found | 390 | кегль p | 14px/400 | 14px/400 | PASS |
| not_found | 390 | ΔE фона | rgb(17, 17, 17) | rgb(17, 17, 17) | PASS |
| not_found | 390 | ΔE текста | rgb(68, 68, 68) | rgb(230, 230, 230) | NOT_COMPARABLE_BY_SELECTOR |
| not_found | 390 | горизонтальная прокрутка | False | False | PASS |
| not_found | 768 | ширина контейнера | 280.0 | 758.0 | FAIL |
| not_found | 768 | высота шапки | 70 | 71 | PASS |
| not_found | 768 | положение шапки | relative | relative | PASS |
| not_found | 768 | кегль body | 14px/400 | 14px/400 | PASS |
| not_found | 768 | кегль h1 | роли нет у эталона | — | BLOCKED_REFERENCE |
| not_found | 768 | кегль a | 14px/400 | 14px/400 | PASS |
| not_found | 768 | кегль p | 14px/400 | 14px/400 | PASS |
| not_found | 768 | ΔE фона | rgb(17, 17, 17) | rgb(17, 17, 17) | PASS |
| not_found | 768 | ΔE текста | rgb(68, 68, 68) | rgb(230, 230, 230) | NOT_COMPARABLE_BY_SELECTOR |
| not_found | 768 | горизонтальная прокрутка | False | False | PASS |
| not_found | 1024 | ширина контейнера | 1000.0 | 1000.0 | PASS |
| not_found | 1024 | высота шапки | 70 | 71 | PASS |
| not_found | 1024 | положение шапки | relative | relative | PASS |
| not_found | 1024 | кегль body | 14px/400 | 14px/400 | PASS |
| not_found | 1024 | кегль h1 | роли нет у эталона | — | BLOCKED_REFERENCE |
| not_found | 1024 | кегль a | 14px/400 | 14px/400 | PASS |
| not_found | 1024 | кегль p | 14px/400 | 14px/400 | PASS |
| not_found | 1024 | ΔE фона | rgb(17, 17, 17) | rgb(17, 17, 17) | PASS |
| not_found | 1024 | ΔE текста | rgb(68, 68, 68) | rgb(230, 230, 230) | NOT_COMPARABLE_BY_SELECTOR |
| not_found | 1024 | горизонтальная прокрутка | False | False | PASS |
| not_found | 1366 | ширина контейнера | 1100.0 | 1100.0 | PASS |
| not_found | 1366 | высота шапки | 70 | 71 | PASS |
| not_found | 1366 | положение шапки | relative | relative | PASS |
| not_found | 1366 | кегль body | 14px/400 | 14px/400 | PASS |
| not_found | 1366 | кегль h1 | роли нет у эталона | — | BLOCKED_REFERENCE |
| not_found | 1366 | кегль a | 14px/400 | 14px/400 | PASS |
| not_found | 1366 | кегль p | 14px/400 | 14px/400 | PASS |
| not_found | 1366 | ΔE фона | rgb(17, 17, 17) | rgb(17, 17, 17) | PASS |
| not_found | 1366 | ΔE текста | rgb(68, 68, 68) | rgb(230, 230, 230) | NOT_COMPARABLE_BY_SELECTOR |
| not_found | 1366 | горизонтальная прокрутка | False | False | PASS |
| not_found | 1440 | ширина контейнера | 1100.0 | 1100.0 | PASS |
| not_found | 1440 | высота шапки | 70 | 71 | PASS |
| not_found | 1440 | положение шапки | relative | relative | PASS |
| not_found | 1440 | кегль body | 14px/400 | 14px/400 | PASS |
| not_found | 1440 | кегль h1 | роли нет у эталона | — | BLOCKED_REFERENCE |
| not_found | 1440 | кегль a | 14px/400 | 14px/400 | PASS |
| not_found | 1440 | кегль p | 14px/400 | 14px/400 | PASS |
| not_found | 1440 | ΔE фона | rgb(17, 17, 17) | rgb(17, 17, 17) | PASS |
| not_found | 1440 | ΔE текста | rgb(68, 68, 68) | rgb(230, 230, 230) | NOT_COMPARABLE_BY_SELECTOR |
| not_found | 1440 | горизонтальная прокрутка | False | False | PASS |
| not_found | 1920 | ширина контейнера | 1100.0 | 1100.0 | PASS |
| not_found | 1920 | высота шапки | 70 | 71 | PASS |
| not_found | 1920 | положение шапки | relative | relative | PASS |
| not_found | 1920 | кегль body | 14px/400 | 14px/400 | PASS |
| not_found | 1920 | кегль h1 | роли нет у эталона | — | BLOCKED_REFERENCE |
| not_found | 1920 | кегль a | 14px/400 | 14px/400 | PASS |
| not_found | 1920 | кегль p | 14px/400 | 14px/400 | PASS |
| not_found | 1920 | ΔE фона | rgb(17, 17, 17) | rgb(17, 17, 17) | PASS |
| not_found | 1920 | ΔE текста | rgb(68, 68, 68) | rgb(230, 230, 230) | NOT_COMPARABLE_BY_SELECTOR |
| not_found | 1920 | горизонтальная прокрутка | False | False | PASS |
