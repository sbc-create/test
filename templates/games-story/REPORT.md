# Отчёт games-story, вариант C «Сюжет пройден» (atlas)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `34fc4b9afe38285b8efeb65be3e5aa358b9fe901`, ветка `claude/template-games-story-c` (вариант A a45135b).

## Как открыть

- Preview: `http://127.0.0.1:8870/` (loopback, `noindex, nofollow`).
- Отличие от A (8857) и B (8858): вход — «Где я?» по чекпоинтам, персонажи по главам, указатель механик; светлая тема. Свои CSS/JS, ключи gst-atlas:*. Сравнение — docs/AUDIT.md.
- Скриншоты (390 и 1440 px): `docs/screenshots/34fc4b9/` — «Где я?», персонаж, главная, игра, глава, коллекции, видео.
- Артефакт: `var/games-story/build/34fc4b9…/` — 32 файлов.

## Проверки на 34fc4b9 (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/games-story test` | 0 | 0 — 15 passed |
| `ruff check . + ruff format --check .` | 0 | 0 — чисто |
| `pytest tests/unit/test_permission_matrix.py` | 0 | 0 — 192 passed |
| `bash bin/games-story build --commit HEAD` | 0 | 0 — 32 файла, var/games-story/build/34fc4b9… |
| `python3 -m saga.qa …` | 0 | 0 — 31 действие PASS; axe 0 |
| `python3 qa/viewports.py 8870 …` | 0 | 0 — 29 URL × 4 ширины, 0 замечаний |
| `python3 -m saga.qa --shots docs/screenshots/34fc4b9 --out docs/verification-browser-qa.json …` | 0 | 31 действий PASS; axe 0 на 32 стр.×ширин |
| `python3 qa/viewports.py 8870 …` | 0 | 29 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback, без троттлинга) 44–152 мс. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: «Где я?» (поиск и фильтр на лету, что дальше), персонажи и их главы, указатель механик, а также всё из A — главы, коллекции, видео-фасад, отметки, поиск, 404 |
| наполнение | тот же набор, что у A: Celeste — 11 материалов глав по celeste.ink, 2 видео (проверены по oEmbed); тексты — manual_standin, не Qwen |
| внешние интеграции | нет (реклама и счётчики выключены) |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT) |

## Обновление на 8664df8 (13.10.2026)

Meta description глав ≤160 символов: целые предложения, иначе по запятой или тире (было до 204 символов, обрезалось в выдаче). Тест проверяет все URL sitemap (20–160 символов).

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/games-story test` | 0 | 16 passed in 0.51s |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m saga.qa --shots docs/screenshots/8664df8 --out docs/verification-browser-qa.json` | 0 | 31 действий PASS, axe 0 |
| `python3 qa/viewports.py 8870 '/igra/celeste/gde-ya/?q=mess' '/igra/celeste/gde-ya/?q=zzzz' /nesushchestvuet/` | 0 | 29 URL × 4 ширины, 0 замечаний |
| `bash bin/games-story build --commit HEAD` | 0 | собрано из 8664df8 |

Лабораторный LCP (loopback, без троттлинга) — до 128 мс. Карта действий — `docs/ACTION-MAP.md`.

## Обновление на 3174e66 (13.10.2026)

Основной вариант (решение владельца 13.10.2026). Идея из B: общий счётчик на главной — клубники (число из источника главы при отметке «все клубники собраны»), стороны, главы целиком — по отметкам чек-листов глав. Прогон на 8a1fc82 дал FAIL video_external_request_only_after_click: проверка шла сразу после нажатия, а iframe с loading=lazy запрашивает не мгновенно (на прошлом прогоне прошло). В 3174e66 приёмка ждёт запрос до 3 с; условие (запрос есть и только к youtube-nocookie.com) не ослаблено.

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/games-story test` | 0 | 18 passed in 0.67s |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m saga.qa --shots docs/screenshots/3174e66 --out docs/verification-browser-qa.json` | 0 | 34 действий PASS, axe 0 |
| `python3 qa/viewports.py 8870 '/igra/celeste/gde-ya/?q=mess' '/igra/celeste/gde-ya/?q=zzzz' /nesushchestvuet/` | 0 | 29 URL × 4 ширины, 0 замечаний |
| `bash bin/games-story build --commit HEAD` | 0 | собрано из 3174e66 |

Лабораторный LCP (loopback, без троттлинга) — до 176 мс. Карта действий — `docs/ACTION-MAP.md`.

## Обновление на 3ca1947 (13.10.2026)

Технический SEO (13.10.2026): описания списков (теги, подборки, разделы, типы работ, проблемы) собираются из названий материалов в пределах 160 знаков, длинные описания режутся по границе фразы; суффикс сайта в заголовке выводится, только если заголовок с ним не длиннее 70 знаков. Новый тест tests/test_snippets.py проверяет все URL sitemap (описание 20–160, суффикс — в пределах 70).

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/games-story test` | 0 | 19 passed in 0.64s |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m saga.qa --shots docs/screenshots/3ca1947 --out docs/verification-browser-qa.json` | 0 | 34 действий PASS, axe 0 |
| `python3 qa/viewports.py 8870 '/igra/celeste/gde-ya/?q=mess' '/igra/celeste/gde-ya/?q=zzzz' /nesushchestvuet/` | 0 | 29 URL × 4 ширины, 0 замечаний |
| `bash bin/games-story build --commit HEAD` | 0 | собрано из 3ca1947 |

Лабораторный LCP (loopback, без троттлинга) — до 140 мс. Карта действий — `docs/ACTION-MAP.md`.

## Обновление на 08a4d44 (13.10.2026)

Чистая копия: у сервера появился --port, у браузерной приёмки — QA_BASE (проверка рядом с действующим превью на 8901–8910, см. RUN-LOCAL.md в ветке claude/template-food-daily). Проверка контента моделью и скриптами (не человеком; статусы ai_draft не менялись).

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/games-story test` | 0 | 19 passed in 0.69s |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m saga.qa --shots docs/screenshots/08a4d44 --out docs/verification-browser-qa.json` | 0 | 34 действий PASS, axe 0 |
| `python3 qa/viewports.py 8870 '/igra/celeste/gde-ya/?q=mess' '/igra/celeste/gde-ya/?q=zzzz' /nesushchestvuet/` | 0 | 29 URL × 4 ширины, 0 замечаний |
| `bash bin/games-story build --commit HEAD` | 0 | собрано из 08a4d44 |

Лабораторный LCP (loopback, без троттлинга) — до 120 мс. Карта действий — `docs/ACTION-MAP.md`.

## Обновление на 852774a (13.10.2026)

VideoObject выводится только при всех обязательных полях (название, превью, дата загрузки из источника); сейчас ни у одного видео даты нет — разметки нет, видео на страницах остаются.

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/games-story test` | 0 | 19 passed in 0.72s |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m saga.qa --shots docs/screenshots/852774a --out docs/verification-browser-qa.json` | 0 | 34 действий PASS, axe 0 |
| `python3 qa/viewports.py 8870 '/igra/celeste/gde-ya/?q=mess' '/igra/celeste/gde-ya/?q=zzzz' /nesushchestvuet/` | 0 | 29 URL × 4 ширины, 0 замечаний |
| `bash bin/games-story build --commit HEAD` | 0 | собрано из 852774a |

Лабораторный LCP (loopback, без троттлинга) — до 216 мс. Карта действий — `docs/ACTION-MAP.md`.
