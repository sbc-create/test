# Отчёт games-survival, вариант B «База выживания» (craft-planner)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `58136675f553ef46a815d52a81b8bb910b1214aa`, ветка `claude/template-games-survival-b` (вариант A db40378).

## Как открыть

- Preview: `http://127.0.0.1:8862/` (loopback, `noindex, nofollow`).
- Отличие от A (craft-tree, 8861): форма «что и сколько» на главной, планировщик с шагами и базовыми ресурсами, табличный каталог, таблицы рецептов и «Куда идёт» с количествами. Своё CSS/JS, порт, хранилище gsv-plan.
- Скриншоты (390 и 1440 px): `docs/screenshots/5813667/` — главная, планировщик (факел × 16), игра, раздел, предмет, ресурс, биом.
- Артефакт: `var/games-survival/build/5813667…/` — 42 файлов.

## Проверки на 5813667 (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bin/games-survival test` | 0 | 0 — 17 passed |
| `ruff check . + ruff format --check .` | 0 | 0 — чисто |
| `pytest tests/unit/test_permission_matrix.py` | 0 | 0 — 192 passed |
| `bin/games-survival build --commit HEAD` | 0 | 0 — 42 файла, var/games-survival/build/5813667… |
| `bin/games-survival qa …` | 0 | 0 — 27 действий PASS; axe 0 |
| `python3 qa/viewports.py 8862 …` | 0 | 0 — 41 URL × 4 ширины, 0 замечаний |
| `bin/games-survival qa --shots docs/screenshots/5813667 --out docs/verification-browser-qa.json …` | 0 | 27 действий PASS; axe 0 на 36 стр.×ширин |
| `python3 qa/viewports.py 8862 …` | 0 | 41 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback, без троттлинга) 36–148 мс. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: планировщик (выбор, количество 1–64, шаги с отметками и сбросом, базовые ресурсы, излишек, печать, 400 при неверном вводе; перебор уровней инструмента не считается), табличный каталог, предмет с рецептами и «Куда идёт», постройки, поиск, 404 |
| наполнение | как в A: Minecraft (Java Edition 26.3), 14 предметов/блоков (с инструментами), 4 постройки, 4 ресурса, 4 биома; количества на крафт — по слотам сетки источника; тексты — manual_standin, не Qwen |
| внешние интеграции | нет (реклама и счётчики выключены) |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT) |
