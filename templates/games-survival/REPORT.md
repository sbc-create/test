# Отчёт games-survival, вариант B «База выживания» (craft-planner)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `9e5892bbae9d9a113bdee1e1315cf6b0bc5b166f`, ветка `claude/template-games-survival-b` (вариант A db40378).

## Как открыть

- Preview: `http://127.0.0.1:8862/` (loopback, `noindex, nofollow`).
- Отличие от A (craft-tree, 8861): форма «что и сколько» на главной, планировщик с шагами и базовыми ресурсами, табличный каталог, таблицы рецептов и «Куда идёт» с количествами. Своё CSS/JS, порт, хранилище gsv-plan.
- Скриншоты (390 и 1440 px): `docs/screenshots/9e5892b/` — главная, планировщик (факел × 16), игра, раздел, предмет, ресурс, биом.
- Артефакт: `var/games-survival/build/9e5892b…/` — 38 файлов.

## Проверки на 9e5892b (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bin/games-survival test` | 0 | 0 — 16 passed |
| `ruff check . + ruff format --check .` | 0 | 0 — чисто |
| `pytest tests/unit/test_permission_matrix.py` | 0 | 0 — 192 passed |
| `bin/games-survival build --commit HEAD` | 0 | 0 — 38 файлов, var/games-survival/build/9e5892b… |
| `bin/games-survival qa …` | 0 | 0 — 27 действий PASS; axe 0 |
| `python3 qa/viewports.py 8862 …` | 0 | 0 — 37 URL × 4 ширины, 0 замечаний |
| `bin/games-survival qa --shots docs/screenshots/9e5892b --out docs/verification-browser-qa.json …` | 0 | 27 действий PASS; axe 0 на 36 стр.×ширин |
| `python3 qa/viewports.py 8862 …` | 0 | 37 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback, без троттлинга) 36–192 мс. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: планировщик (выбор, количество 1–64, шаги с отметками и сбросом, базовые ресурсы, излишек, печать, 400 при неверном вводе), табличный каталог, предмет с рецептами и «Куда идёт», постройки, поиск, 404 |
| наполнение | как в A: Minecraft (Java Edition 26.3), 10 предметов/блоков, 4 постройки (забор и ступеньки — в планировщике; кровать — нет, шерсти на сайте нет; дверь без рецепта), 4 ресурса, 4 биома; количества на крафт — по слотам сетки источника; тексты — manual_standin, не Qwen |
| внешние интеграции | нет (реклама и счётчики выключены) |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT) |
