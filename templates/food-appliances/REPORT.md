# Отчёт food-appliances, вариант B «Готовим в технике» (step-console)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `a9c3ec0e6b949d9750b02fb048a23176236bb704`, ветка `claude/template-food-appliances-b` (вариант A 979df30).

## Как открыть

- Preview: `http://127.0.0.1:8866/` (loopback, `noindex, nofollow`).
- Отличие от A (8850): таблица сравнения рецептов на главной и страницах приборов вместо плиток; в рецепте настройки прибора стоят прямо в шагах источника с таймером и отметкой вместо табло сверху; у A нет JS, у B — свой console.js (ключи fab.*). Сравнение — docs/AUDIT.md.
- Скриншоты (390 и 1440 px): `docs/screenshots/a9c3ec0/` — главная, прибор, категория, рецепт (плов), рецепт с пультом (жаркое), режим, справка.
- Артефакт: `var/food-appliances/build/a9c3ec0…/` — 30 файлов.

## Проверки на a9c3ec0 (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/food-appliances test` | 0 | 0 — 16 passed |
| `ruff check . + ruff format --check .` | 0 | 0 — чисто |
| `pytest tests/unit/test_permission_matrix.py` | 0 | 0 — 192 passed |
| `bash bin/food-appliances build --commit HEAD` | 0 | 0 — 30 файлов, var/food-appliances/build/a9c3ec0… |
| `python3 -m techkitchen.qa …` | 0 | 0 — 30 действий PASS; axe 0 |
| `python3 qa/viewports.py 8866 …` | 0 | 0 — 27 URL × 4 ширины, 0 замечаний |
| `python3 -m techkitchen.qa --shots docs/screenshots/a9c3ec0 --out docs/verification-browser-qa.json …` | 0 | 30 действий PASS; axe 0 на 22 стр.×ширин |
| `python3 qa/viewports.py 8866 …` | 0 | 27 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback, без троттлинга) 36–160 мс. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: таблицы сравнения, пульт по шагам (настройки из источника, таймеры, отметки с сохранением и сбросом), режимы, справка, поиск, 404 |
| наполнение | тот же снимок, что у A: 12 рецептов (6 мультиварка, 6 аэрогриль, факты eda.rambler.ru); тексты — manual_standin, не Qwen; редакция не проверяла и не готовила |
| внешние интеграции | нет (реклама и счётчики выключены) |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT) |

## Обновление на 838da4a (13.10.2026)

Основной вариант (решение владельца 13.10.2026). Перенесено из A: табло «прибор / режим / °C / время» со ссылками на шаги (пульт в шагах сохранён; тест варианта, запрещавший табло, обновлён). Перенесено из C: очередь на прибор (/ochered/: по приборам и температуре, сумма времени в приборе, отметки «готово», память выбора, пустой выбор блокируется, неизвестный рецепт — 400).

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/food-appliances test` | 0 | 20 passed in 0.78s |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m techkitchen.qa --shots docs/screenshots/838da4a --out docs/verification-browser-qa.json` | 0 | 42 действий PASS, axe 0 |
| `python3 qa/viewports.py 8866 '/ochered/?r=syrniki-v-aerogrile&r=semga-v-aerogrile&r=plov-v-multivarke' '/ochered/?r=neizvestno' '/poisk/?q=тушение' /nesushchestvuet/` | 0 | 30 URL × 4 ширины, 0 замечаний |
| `bash bin/food-appliances build --commit HEAD` | 0 | собрано из 838da4a |

Лабораторный LCP (loopback, без троттлинга) — до 160 мс. Карта действий — `docs/ACTION-MAP.md`.

## Обновление на 5d5aee3 (13.10.2026)

Технический SEO (13.10.2026): описания списков (теги, подборки, разделы, типы работ, проблемы) собираются из названий материалов в пределах 160 знаков, длинные описания режутся по границе фразы; суффикс сайта в заголовке выводится, только если заголовок с ним не длиннее 70 знаков. Новый тест tests/test_snippets.py проверяет все URL sitemap (описание 20–160, суффикс — в пределах 70).

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/food-appliances test` | 0 | 21 passed in 0.75s |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m techkitchen.qa --shots docs/screenshots/5d5aee3 --out docs/verification-browser-qa.json` | 0 | 42 действий PASS, axe 0 |
| `python3 qa/viewports.py 8866 '/ochered/?r=syrniki-v-aerogrile&r=semga-v-aerogrile&r=plov-v-multivarke' '/ochered/?r=neizvestno' '/poisk/?q=тушение' /nesushchestvuet/` | 0 | 30 URL × 4 ширины, 0 замечаний |
| `bash bin/food-appliances build --commit HEAD` | 0 | собрано из 5d5aee3 |

Лабораторный LCP (loopback, без троттлинга) — до 164 мс. Карта действий — `docs/ACTION-MAP.md`.

## Обновление на 1973778 (13.10.2026)

Чистая копия: у сервера появился --port, у браузерной приёмки — QA_BASE (проверка рядом с действующим превью на 8901–8910, см. RUN-LOCAL.md в ветке claude/template-food-daily). Проверка контента моделью и скриптами (не человеком; статусы ai_draft не менялись). Тест сверки черновиков без закрытых снимков — SKIPPED с причиной (здесь выполнен).

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/food-appliances test` | 0 | 21 passed in 0.66s |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m techkitchen.qa --shots docs/screenshots/1973778 --out docs/verification-browser-qa.json` | 0 | 42 действий PASS, axe 0 |
| `python3 qa/viewports.py 8866 '/ochered/?r=syrniki-v-aerogrile&r=semga-v-aerogrile&r=plov-v-multivarke' '/ochered/?r=neizvestno' '/poisk/?q=тушение' /nesushchestvuet/` | 0 | 30 URL × 4 ширины, 0 замечаний |
| `bash bin/food-appliances build --commit HEAD` | 0 | собрано из 1973778 |

Лабораторный LCP (loopback, без троттлинга) — до 432 мс. Карта действий — `docs/ACTION-MAP.md`.
