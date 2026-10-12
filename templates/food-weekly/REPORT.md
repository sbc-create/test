# Отчёт food-weekly, вариант B «Меню на неделю» (agenda-trips)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `96c0c983b8dd4975c929ddc81551495376825ea5`, ветка `claude/template-food-weekly-b` (вариант A 734c07e).

## Как открыть

- Preview: `http://127.0.0.1:8865/` (loopback, `noindex, nofollow`).
- Отличие от A (8849): таблица сравнения планов вместо карточек, неделя повесткой по дням вместо сетки 7×3, покупки двумя закупками (пн–ср, чт–вс) со своими отметками; свои CSS/JS, ключи fwb.*. Сравнение — docs/AUDIT.md.
- Скриншоты (390 и 1440 px): `docs/screenshots/96c0c98/` — главная, каталог планов, неделя, день, покупки.
- Артефакт: `var/food-weekly/build/96c0c98…/` — 39 файлов.

## Проверки на 96c0c98 (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/food-weekly test` | 0 | 0 — 18 passed |
| `ruff check . + ruff format --check .` | 0 | 0 — чисто |
| `pytest tests/unit/test_permission_matrix.py` | 0 | 0 — 192 passed |
| `bash bin/food-weekly build --commit HEAD` | 0 | 0 — 39 файлов, var/food-weekly/build/96c0c98… |
| `python3 -m weekplan.qa …` | 0 | 0 — 26 действий PASS; axe 0 |
| `python3 qa/viewports.py 8865 …` | 0 | 0 — 36 URL × 4 ширины, 0 замечаний |
| `python3 -m weekplan.qa --shots docs/screenshots/96c0c98 --out docs/verification-browser-qa.json …` | 0 | 26 действий PASS; axe 0 на 20 стр.×ширин |
| `python3 qa/viewports.py 8865 …` | 0 | 36 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback, без троттлинга) 52–492 мс. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: сравнение планов, повестка с переходом по дням и заменами (без JS тоже), две закупки с сохраняемыми отметками и счётчиком, полный список, печать, подборки, 404 |
| наполнение | те же 3 плана и снимок каталога food-daily, что у A; планы — manual_standin, не Qwen; рецепты не проверены редакцией |
| внешние интеграции | каталог рецептов food-daily — снимок от 2026-10-12 (preview_adapter); реклама и счётчики выключены |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT) |
