# Отчёт food-daily, вариант B «Будни на кухне» (fridge-first)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `0f52eaf486f558bae56798a6d41e2c73cb9a2acf`, ветка `claude/template-food-daily-b` (вариант A 066688b).

## Как открыть

- Preview: `http://127.0.0.1:8863/` (loopback, `noindex, nofollow`).
- Отличие от A (8847): вход от продуктов («Что есть дома?» и /iz-holodilnika/ с перечнем недостающего), каталог-таблица с сортировкой, отметки шагов вместо модального режима готовки; свои CSS/JS, ключи fdb.*. Сравнение — docs/audit/variant-b.md.
- Скриншоты (390 и 1440 px): `docs/screenshots/0f52eaf/` — главная, каталог, рецепт, подбор (курица + рис), продукт, совет.
- Артефакт: `var/food-daily/build/0f52eaf…/` — 68 файлов.

## Проверки на 0f52eaf (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/food-daily test` | 0 | 0 — 123 passed |
| `ruff check . + ruff format --check .` | 0 | 0 — чисто |
| `pytest tests/unit/test_permission_matrix.py` | 0 | 0 — 192 passed |
| `bash bin/food-daily build --commit HEAD` | 0 | 0 — 68 файлов, var/food-daily/build/0f52eaf… |
| `python3 -m fooddaily.qa_browser …` | 0 | 0 — 31 действие PASS; axe 0; контраст 0 |
| `python3 qa/viewports.py 8863 …` | 0 | 0 — 57 URL × 4 ширины, 0 замечаний |
| `python3 -m fooddaily.qa_browser --shots docs/screenshots/0f52eaf --out docs/verification-browser-qa.json …` | 0 | 31 действий PASS; axe 0 на 38 стр.×ширин |
| `python3 qa/viewports.py 8863 …` | 0 | 57 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback, без троттлинга) 48–304 мс. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: подбор по продуктам (память выбора, сброс, пустой выбор блокируется, 400 на неизвестный продукт), «На сегодня», каталог-таблица с фильтрами и сортировкой, рецепт с порциями, покупками, избранным, отметками шагов, печать, поиск, 404 |
| наполнение | тот же снимок, что у A: 22 рецепта, 3 совета; тексты — черновики сессии Claude (manual_standin), не Qwen; редактор не проверял; рецепты не готовились |
| внешние интеграции | нет (реклама и счётчики выключены) |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT) |
