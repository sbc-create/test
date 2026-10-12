# Отчёт games-rpg, вариант B «Гайды RPG: отряд» (party-planner)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `3daa6971d60cc8d95b52a5e6dec636710fcab1e9`, ветка `claude/template-games-rpg-b` (начата с 13b0901 варианта A).

## Как открыть

- Preview: `http://127.0.0.1:8860/` (loopback, `noindex, nofollow`). Вариант A — http://127.0.0.1:8859/; отличия — docs/VARIANTS.md.
- Скриншоты (390 и 1440 px): `docs/screenshots/3daa697/` — главная, отряд, таблица персонажей, персонаж, билд, квест.
- Артефакт: `var/games-rpg/build/3daa697…/` — 29 файлов.

## Проверки на 3daa697 (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bin/games-rpg test` | 0 | 11 passed |
| `ruff check . + ruff format --check .` | 0 | чисто |
| `bin/games-rpg build --commit HEAD` | 0 | 29 файлов |
| `bin/games-rpg qa …` | 0 | 25 действий PASS; axe 0 на 30 стр.×ширин |
| `python3 qa/viewports.py 8860 …` | 0 | 27 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback, без троттлинга) 40–140 мс. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: планировщик отряда без JS, сводка с равенствами, таблица персонажей с сортировкой, лист персонажа, билды, квесты с этапами, версия, поиск, печать, 404 |
| наполнение | тот же снимок, что в A (Baldurs Gate 3, Patch 8); тексты — manual_standin, не Qwen |
| внешние интеграции | нет (реклама и счётчики выключены) |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT) |
