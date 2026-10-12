# Отчёт food-baking, вариант B «Тесто и десерты» (oven-bench)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `3f222ce7bf5edcda38109c9429b6bbca0c5ba6ce`, ветка `claude/template-food-baking-b` (вариант A 8a5cb1e).

## Как открыть

- Preview: `http://127.0.0.1:8864/` (loopback, `noindex, nofollow`).
- Отличие от A (8848): главная по температуре духовки, каталог — таблица сравнения с сортировкой, рецепт — рабочий лист (полоса духовки, «Отвесить» с пекарским процентом, шаги с отметками и таймером в своём шаге); свои CSS/JS, ключи fbb.*. Сравнение — docs/AUDIT.md.
- Скриншоты (390 и 1440 px): `docs/screenshots/3f222ce/` — главная, каталог, рецепт (кекс), рецепт с пекарским процентом, вид теста, разбор ошибок.
- Артефакт: `var/food-baking/build/3f222ce…/` — 31 файлов.

## Проверки на 3f222ce (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/food-baking test` | 0 | 0 — 26 passed |
| `ruff check . + ruff format --check .` | 0 | 0 — чисто |
| `pytest tests/unit/test_permission_matrix.py` | 0 | 0 — 192 passed |
| `bash bin/food-baking build --commit HEAD` | 0 | 0 — 31 файл, var/food-baking/build/3f222ce… |
| `python3 -m bakebook.qa …` | 0 | 0 — 33 действия PASS; axe 0 |
| `python3 qa/viewports.py 8864 …` | 0 | 0 — 29 URL × 4 ширины, 0 замечаний |
| `python3 -m bakebook.qa --shots docs/screenshots/3f222ce --out docs/verification-browser-qa.json …` | 0 | 33 действий PASS; axe 0 на 30 стр.×ширин |
| `python3 qa/viewports.py 8864 …` | 0 | 29 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback, без троттлинга) 48–256 мс. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: по температуре с якорями, таблица сравнения с фильтрами и сортировкой, рабочий лист (пекарский процент, отметки «отвешено» и шагов с сохранением и сбросом, таймеры из источника), виды теста, разборы ошибок, поиск, 404 |
| наполнение | тот же снимок, что у A: 13 рецептов (eda.rambler.ru, факты); тексты — manual_standin, не Qwen; редакция не проверяла и не пекла |
| внешние интеграции | нет (реклама и счётчики выключены) |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT) |
