# Отчёт food-daily, вариант C «Будни на кухне» (party-list)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `ff00cede66c2b2d471fecc6bb62afed37b2e98b5`, ветка `claude/template-food-daily-c` (вариант A aab3470).

## Как открыть

- Preview: `http://127.0.0.1:8876/` (loopback, `noindex, nofollow`).
- Отличие от A (8847) и B (8863): вход — несколько блюд и число гостей; итог — общий пересчитанный список продуктов с отметками. Свои CSS/JS, ключи fdc.*. Сравнение — docs/audit/variant-c.md.
- Скриншоты (390 и 1440 px): `docs/screenshots/ff00ced/` — на компанию (8 гостей), главная, каталог, рецепт, продукт, совет.
- Артефакт: `var/food-daily/build/ff00ced…/` — 68 файлов.

## Проверки на ff00ced (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/food-daily test` | 0 | 0 — 122 passed |
| `ruff check . + ruff format --check .` | 0 | 0 — чисто |
| `pytest tests/unit/test_permission_matrix.py` | 0 | 0 — 192 passed |
| `bash bin/food-daily build --commit HEAD` | 0 | 0 — 68 файлов, var/food-daily/build/ff00ced… |
| `python3 -m fooddaily.qa_browser …` | 0 | 0 — 36 действий PASS; axe 0; контраст 0 |
| `python3 qa/viewports.py 8876 …` | 0 | 0 — 56 URL × 4 ширины, 0 замечаний |
| `python3 -m fooddaily.qa_browser --shots docs/screenshots/ff00ced --out docs/verification-browser-qa.json …` | 0 | 36 действий PASS; axe 0 на 30 стр.×ширин |
| `python3 qa/viewports.py 8876 …` | 0 | 56 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback, без троттлинга) 60–232 мс. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: выбор блюд и гостей (память, блок пустой отправки, 400), общий пересчитанный список с отметками и печатью, а также всё из A — каталог, рецепты с порциями и режимом готовки, покупки, избранное, поиск, 404 |
| наполнение | тот же снимок, что у A: 22 рецепта, 3 совета; тексты — черновики сессии Claude (manual_standin), не Qwen; редакция не проверяла |
| внешние интеграции | нет (реклама и счётчики выключены) |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT) |
