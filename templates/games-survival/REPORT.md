# Отчёт games-survival, вариант B «База выживания» (craft-planner)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `0bf2310d37d8442752c8e8914d5e050fbf080503`, ветка `claude/template-games-survival-b` (вариант A db40378).

## Как открыть

- Preview: `http://127.0.0.1:8862/` (loopback, `noindex, nofollow`).
- Отличие от A (craft-tree, 8861): форма «что и сколько» на главной, планировщик с шагами и базовыми ресурсами, табличный каталог, таблицы рецептов и «Куда идёт» с количествами. Своё CSS/JS, порт, хранилище gsv-plan.
- Скриншоты (390 и 1440 px): `docs/screenshots/0bf2310/` — главная, планировщик (факел × 16), игра, раздел, предмет, ресурс, биом.
- Артефакт: `var/games-survival/build/0bf2310…/` — 39 файлов.

## Проверки на 0bf2310 (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bin/games-survival test` | 0 | 0 — 17 passed |
| `ruff check . + ruff format --check .` | 0 | 0 — чисто |
| `pytest tests/unit/test_permission_matrix.py` | 0 | 0 — 192 passed |
| `bin/games-survival build --commit HEAD` | 0 | 0 — 39 файлов, var/games-survival/build/0bf2310… |
| `bin/games-survival qa …` | 0 | 0 — 27 действий PASS; axe 0 |
| `python3 qa/viewports.py 8862 …` | 0 | 0 — 38 URL × 4 ширины, 0 замечаний |
| `bin/games-survival qa --shots docs/screenshots/0bf2310 --out docs/verification-browser-qa.json …` | 0 | 27 действий PASS; axe 0 на 36 стр.×ширин |
| `python3 qa/viewports.py 8862 …` | 0 | 38 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback, без троттлинга) 44–136 мс. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: планировщик (выбор, количество 1–64, шаги с отметками и сбросом, базовые ресурсы, излишек, печать, 400 при неверном вводе; перебор уровней инструмента не считается), табличный каталог, предмет с рецептами и «Куда идёт», постройки, поиск, 404 |
| наполнение | как в A: Minecraft (Java Edition 26.3), 11 предметов/блоков (с киркой), 4 постройки, 4 ресурса, 4 биома; количества на крафт — по слотам сетки источника; тексты — manual_standin, не Qwen |
| внешние интеграции | нет (реклама и счётчики выключены) |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT) |
