# Отчёт food-baking, вариант C «Тесто и десерты» (bake-batch)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `ff617d03e8c56ffdd6068da2d7c41261d6b6d3f9`, ветка `claude/template-food-baking-c` (вариант A 79bf0b8).

## Как открыть

- Preview: `http://127.0.0.1:8875/` (loopback, `noindex, nofollow`).
- Отличие от A (8848) и B (8864): вход — отметить несколько рецептов; итог — общий список продуктов с отметками и группы духовки по температурам. Свои CSS/JS, ключи fbc.*. Сравнение — docs/AUDIT.md.
- Скриншоты (390 и 1440 px): `docs/screenshots/ff617d0/` — пеку несколько (3 рецепта), главная, оглавление, рецепт, вид теста, разбор ошибок.
- Артефакт: `var/food-baking/build/ff617d0…/` — 32 файлов.

## Проверки на ff617d0 (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/food-baking test` | 0 | 0 — 25 passed |
| `ruff check . + ruff format --check .` | 0 | 0 — чисто |
| `pytest tests/unit/test_permission_matrix.py` | 0 | 0 — 192 passed |
| `bash bin/food-baking build --commit HEAD` | 0 | 0 — 32 файла, var/food-baking/build/ff617d0… |
| `python3 -m bakebook.qa …` | 0 | 0 — 32 действия PASS; axe 0 |
| `python3 qa/viewports.py 8875 …` | 0 | 0 — 30 URL × 4 ширины, 0 замечаний |
| `python3 -m bakebook.qa --shots docs/screenshots/ff617d0 --out docs/verification-browser-qa.json …` | 0 | 32 действий PASS; axe 0 на 26 стр.×ширин |
| `python3 qa/viewports.py 8875 …` | 0 | 30 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback, без троттлинга) 48–212 мс. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: выбор рецептов (память, блок пустой отправки, 400), группы духовки, общий список с отметками и печатью, а также всё из A — оглавление, рецепт-разворот с таймерами, виды теста, разборы ошибок, поиск, 404 |
| наполнение | тот же снимок, что у A: 13 рецептов (eda.rambler.ru, факты); тексты — manual_standin, не Qwen; редакция не проверяла и не пекла |
| внешние интеграции | нет (реклама и счётчики выключены) |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT) |
