# Отчёт games-rpg, вариант C «Гайды RPG» (index-compare)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `f5eb3d471bb8fa7ab9e43f64bdf176aacba69ce5`, ветка `claude/template-games-rpg-c` (вариант A 0e68f8a (с предметами)).

## Как открыть

- Preview: `http://127.0.0.1:8871/` (loopback, `noindex, nofollow`).
- Отличие от A (8859) и B (8860): главная — указатель А–Я по всем материалам с фильтром по типу; сравнение предметов по полям инфобокса. Свои CSS/JS, ключи grpg-index:*. Сравнение — docs/AUDIT.md.
- Скриншоты (390 и 1440 px): `docs/screenshots/f5eb3d4/` — сравнение предметов, главная-указатель, игра, раздел, персонаж, билд, квест.
- Артефакт: `var/games-rpg/build/f5eb3d4…/` — 41 файлов.

## Проверки на f5eb3d4 (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/games-rpg test` | 0 | 0 — 15 passed |
| `ruff check . + ruff format --check .` | 0 | 0 — чисто |
| `pytest tests/unit/test_permission_matrix.py` | 0 | 0 — 192 passed |
| `bash bin/games-rpg build --commit HEAD` | 0 | 0 — 41 файл, var/games-rpg/build/f5eb3d4… |
| `python3 -m quest.qa …` | 0 | 0 — 27 действий PASS; axe 0 |
| `python3 qa/viewports.py 8871 …` | 0 | 0 — 39 URL × 4 ширины, 0 замечаний |
| `python3 -m quest.qa --shots docs/screenshots/f5eb3d4 --out docs/verification-browser-qa.json …` | 0 | 27 действий PASS; axe 0 на 32 стр.×ширин |
| `python3 qa/viewports.py 8871 …` | 0 | 39 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback, без троттлинга) 40–168 мс. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: указатель А–Я (фильтр по типу, переход по буквам, 400 на неизвестный тип), сравнение предметов, а также всё из A — разделы, материалы с паспортами, версия, поиск, печать, 404 |
| наполнение | как в A: Baldurs Gate 3 — 9 спутников, 3 основы билдов, 2 механики, 2 квеста, 8 предметов (без цены), Patch 8; тексты — manual_standin, не Qwen |
| внешние интеграции | нет (реклама и счётчики выключены) |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT) |

## Обновление на 5227702 (13.10.2026)

Meta description: у разделов — из данных (число материалов, вики-источник, версия игры) вместо «Раздел — Игра.» (22–29 символов); у материалов — целые предложения до 160 символов (было до 263 и обрезалось в выдаче посреди фразы). Новый тест проверяет все URL sitemap: 20–160 символов.

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/games-rpg test` | 0 | 16 passed in 0.68s |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m quest.qa --shots docs/screenshots/5227702 --out docs/verification-browser-qa.json` | 0 | 27 действий PASS, axe 0 |
| `python3 qa/viewports.py 8871 '/?tip=item' '/?tip=xx' '/poisk/?q=Gale' /nesushchestvuet/` | 0 | 39 URL × 4 ширины, 0 замечаний |
| `bash bin/games-rpg build --commit HEAD` | 0 | собрано из 5227702 |

Лабораторный LCP (loopback, без троттлинга) — до 136 мс. Карта действий — `docs/ACTION-MAP.md`.

## Обновление на 3a559de (13.10.2026)

Meta description длиннее одного предложения теперь режется по запятой или тире (а не посреди фразы, как «…с которыми нельзя…»); у garden-season описания работ были до 263 символов — теперь ≤160. Тест проверяет все URL sitemap (20–160 символов) и случай с запятой.

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/games-rpg test` | 0 | 16 passed in 0.71s |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m quest.qa --shots docs/screenshots/3a559de --out docs/verification-browser-qa.json` | 0 | 27 действий PASS, axe 0 |
| `python3 qa/viewports.py 8871 '/?tip=item' '/?tip=xx' '/poisk/?q=Gale' /nesushchestvuet/` | 0 | 39 URL × 4 ширины, 0 замечаний |
| `bash bin/games-rpg build --commit HEAD` | 0 | собрано из 3a559de |

Лабораторный LCP (loopback, без троттлинга) — до 180 мс. Карта действий — `docs/ACTION-MAP.md`.

## Обновление на 307c3e7 (13.10.2026)

Основной вариант (решение владельца 13.10.2026). Перенесено из B: планировщик отряда (/otryad/, работает без JS; классы и наибольшее значение каждой характеристики с учётом равенства — по данным вики). Улучшения против B: любой выбор — noindex без canonical; неизвестные имена — предупреждение role=status. По ходу: 2493c5c — приёмка упала (вторая кнопка в .more ломала выбор кнопки сравнения; ссылка вынесена в 133f8ab); 133f8ab — axe color-contrast у отмеченного спутника (исправлено в 2e8185b, цвета из палитры — 307c3e7). Лабораторный LCP mobile:compare 1260 мс — страница не менялась, desktop 220 мс, load average машины около 7: шум замера, не регрессия кода.

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/games-rpg test` | 0 | 18 passed in 0.71s |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m quest.qa --shots docs/screenshots/307c3e7 --out docs/verification-browser-qa.json` | 0 | 33 действий PASS, axe 0 |
| `python3 qa/viewports.py 8871 '/?tip=item' '/?tip=xx' '/poisk/?q=Gale' '/otryad/?p=gale&p=karlach&p=shadowheart' '/otryad/?p=nikto' /nesushchestvuet/` | 0 | 42 URL × 4 ширины, 0 замечаний |
| `bash bin/games-rpg build --commit HEAD` | 0 | собрано из 307c3e7 |

Лабораторный LCP (loopback, без троттлинга) — до 1260 мс. Карта действий — `docs/ACTION-MAP.md`.

## Обновление на 7f8d1b1 (13.10.2026)

Технический SEO (13.10.2026): описания списков (теги, подборки, разделы, типы работ, проблемы) собираются из названий материалов в пределах 160 знаков, длинные описания режутся по границе фразы; суффикс сайта в заголовке выводится, только если заголовок с ним не длиннее 70 знаков. Новый тест tests/test_snippets.py проверяет все URL sitemap (описание 20–160, суффикс — в пределах 70).

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/games-rpg test` | 0 | 19 passed in 1.00s |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m quest.qa --shots docs/screenshots/7f8d1b1 --out docs/verification-browser-qa.json` | 0 | 33 действий PASS, axe 0 |
| `python3 qa/viewports.py 8871 '/?tip=item' '/?tip=xx' '/poisk/?q=Gale' '/otryad/?p=gale&p=karlach&p=shadowheart' '/otryad/?p=nikto' /nesushchestvuet/` | 0 | 42 URL × 4 ширины, 0 замечаний |
| `bash bin/games-rpg build --commit HEAD` | 0 | собрано из 7f8d1b1 |

Лабораторный LCP (loopback, без троттлинга) — до 180 мс. Карта действий — `docs/ACTION-MAP.md`.
