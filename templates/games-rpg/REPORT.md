# Отчёт games-rpg, вариант A «Гайды RPG» (codex-sections)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `c71fd635f84ba06cbc37583ee5dc838101a05677`, ветка `claude/template-games-rpg` (origin/main a7f7cb6).

## Как открыть

- Preview: `http://127.0.0.1:8859/` (loopback, `noindex, nofollow`).
- Скриншоты (390 и 1440 px): `docs/screenshots/c71fd63/` — главная, игра, раздел, персонаж, билд, квест.
- Артефакт: `var/games-rpg/build/c71fd63…/` — 37 файлов.

## Проверки на c71fd63 (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bin/games-rpg test` | 0 | 0 — 11 passed |
| `ruff check . + ruff format --check .` | 0 | 0 — чисто |
| `pytest tests/unit/test_permission_matrix.py` | 0 | 0 — 192 passed |
| `bin/games-rpg build --commit HEAD` | 0 | 0 — 37 файлов, var/games-rpg/build/c71fd63… |
| `bin/games-rpg qa …` | 0 | 0 — 20 действий PASS; axe 0 |
| `python3 qa/viewports.py 8859 …` | 0 | 0 — 33 URL × 4 ширины, 0 замечаний |
| `bin/games-rpg qa --shots docs/screenshots/c71fd63 --out docs/verification-browser-qa.json …` | 0 | 20 действий PASS; axe 0 на 30 стр.×ширин |
| `python3 qa/viewports.py 8859 …` | 0 | 33 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback, без троттлинга) 48–144 мс. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: игра, разделы (персонажи, билды, квесты, механики, предметы), материал с паспортом/прогрессией/этапами/паспортом предмета, версия игры, поиск, печать, 404 |
| наполнение | Baldurs Gate 3: 6 спутников, 3 основы билдов (у 2 кастеров таблица скрыта), 2 механики, 2 квеста, 8 предметов (без цены), версия Patch 8; тексты — manual_standin, не Qwen |
| внешние интеграции | нет (реклама и счётчики выключены) |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT) |
