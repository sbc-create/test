# Отчёт games-rpg, вариант B «Гайды RPG: отряд» (party-planner)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `94e6dfb96c7ecf77243b9e8be051ede16cf91d0c`, ветка `claude/template-games-rpg-b` (начата с 13b0901 варианта A).

## Как открыть

- Preview: `http://127.0.0.1:8860/` (loopback, `noindex, nofollow`). Вариант A — http://127.0.0.1:8859/; отличия — docs/VARIANTS.md.
- Скриншоты (390 и 1440 px): `docs/screenshots/94e6dfb/` — главная, отряд, таблица персонажей, персонаж, билд, квест.
- Артефакт: `var/games-rpg/build/94e6dfb…/` — 34 файлов.

## Проверки на 94e6dfb (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bin/games-rpg test` | 0 | 0 — 13 passed |
| `ruff check . + ruff format --check .` | 0 | 0 — чисто |
| `pytest tests/unit/test_permission_matrix.py` | 0 | 0 — 192 passed |
| `bin/games-rpg build --commit HEAD` | 0 | 0 — 34 файла, var/games-rpg/build/94e6dfb… |
| `bin/games-rpg qa …` | 0 | 0 — 25 действий PASS; axe 0 |
| `python3 qa/viewports.py 8860 …` | 0 | 0 — 31 URL × 4 ширины, 0 замечаний |
| `bin/games-rpg qa --shots docs/screenshots/94e6dfb --out docs/verification-browser-qa.json …` | 0 | 25 действий PASS; axe 0 на 30 стр.×ширин |
| `python3 qa/viewports.py 8860 …` | 0 | 31 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback, без троттлинга) 32–200 мс. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: планировщик отряда (до 4, сводка лучших характеристик с равенствами), сортируемая таблица персонажей, разделы, предметы с паспортом, версия, поиск, печать, 404 |
| наполнение | как в A: Baldurs Gate 3 — 6 спутников, 3 основы билдов, 2 механики, 2 квеста, 4 предмета (без цены), Patch 8; тексты — manual_standin, не Qwen |
| внешние интеграции | нет (реклама и счётчики выключены) |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT) |
