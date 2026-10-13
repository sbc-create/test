# Отчёт games-rpg, вариант B «Гайды RPG: отряд» (party-planner)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `d46a9b80a5dba3d6edf87fc15ebf039ac3ff2469`, ветка `claude/template-games-rpg-b` (начата с 13b0901 варианта A).

## Как открыть

- Preview: `http://127.0.0.1:8860/` (loopback, `noindex, nofollow`). Вариант A — http://127.0.0.1:8859/; отличия — docs/VARIANTS.md.
- Скриншоты (390 и 1440 px): `docs/screenshots/d46a9b8/` — главная, отряд, таблица персонажей, персонаж, билд, квест.
- Артефакт: `var/games-rpg/build/d46a9b8…/` — 41 файлов.

## Проверки на d46a9b8 (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bin/games-rpg test` | 0 | 0 — 13 passed |
| `ruff check . + ruff format --check .` | 0 | 0 — чисто |
| `pytest tests/unit/test_permission_matrix.py` | 0 | 0 — 192 passed |
| `bin/games-rpg build --commit HEAD` | 0 | 0 — 41 файл, var/games-rpg/build/d46a9b8… |
| `bin/games-rpg qa …` | 0 | 0 — 25 действий PASS; axe 0 |
| `python3 qa/viewports.py 8860 …` | 0 | 0 — 38 URL × 4 ширины, 0 замечаний |
| `bin/games-rpg qa --shots docs/screenshots/d46a9b8 --out docs/verification-browser-qa.json …` | 0 | 25 действий PASS; axe 0 на 30 стр.×ширин |
| `python3 qa/viewports.py 8860 …` | 0 | 38 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback, без троттлинга) 44–140 мс. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: планировщик отряда (до 4, сводка лучших характеристик с равенствами), сортируемая таблица персонажей, разделы, предметы с паспортом, версия, поиск, печать, 404 |
| наполнение | как в A: Baldurs Gate 3 — 9 спутников, 3 основы билдов, 2 механики, 2 квеста, 8 предметов (без цены), Patch 8; тексты — manual_standin, не Qwen |
| внешние интеграции | нет (реклама и счётчики выключены) |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT) |
