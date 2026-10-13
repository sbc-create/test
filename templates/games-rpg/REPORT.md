# Отчёт games-rpg, вариант B «Гайды RPG: отряд» (party-planner)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `8403a5a92bf53c8aa76ac76af598f8dc6b458e85`, ветка `claude/template-games-rpg-b` (начата с 13b0901 варианта A).

## Как открыть

- Preview: `http://127.0.0.1:8860/` (loopback, `noindex, nofollow`). Вариант A — http://127.0.0.1:8859/; отличия — docs/VARIANTS.md.
- Скриншоты (390 и 1440 px): `docs/screenshots/8403a5a/` — главная, отряд, таблица персонажей, персонаж, билд, квест.
- Артефакт: `var/games-rpg/build/8403a5a…/` — 38 файлов.

## Проверки на 8403a5a (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bin/games-rpg test` | 0 | 0 — 13 passed |
| `ruff check . + ruff format --check .` | 0 | 0 — чисто |
| `pytest tests/unit/test_permission_matrix.py` | 0 | 0 — 192 passed |
| `bin/games-rpg build --commit HEAD` | 0 | 0 — 38 файлов, var/games-rpg/build/8403a5a… |
| `bin/games-rpg qa …` | 0 | 0 — 25 действий PASS; axe 0 |
| `python3 qa/viewports.py 8860 …` | 0 | 0 — 35 URL × 4 ширины, 0 замечаний |
| `bin/games-rpg qa --shots docs/screenshots/8403a5a --out docs/verification-browser-qa.json …` | 0 | 25 действий PASS; axe 0 на 30 стр.×ширин |
| `python3 qa/viewports.py 8860 …` | 0 | 35 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback, без троттлинга) 48–380 мс. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: планировщик отряда (до 4, сводка лучших характеристик с равенствами), сортируемая таблица персонажей, разделы, предметы с паспортом, версия, поиск, печать, 404 |
| наполнение | как в A: Baldurs Gate 3 — 6 спутников, 3 основы билдов, 2 механики, 2 квеста, 8 предметов (без цены), Patch 8; тексты — manual_standin, не Qwen |
| внешние интеграции | нет (реклама и счётчики выключены) |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT) |
