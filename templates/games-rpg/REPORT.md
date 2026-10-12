# Отчёт games-rpg, вариант A «Гайды RPG» (codex-sections)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `14d71926f97bd8ccd982ced1a168b63f1174b261`, ветка `claude/template-games-rpg` (origin/main a7f7cb6).

## Как открыть

- Preview: `http://127.0.0.1:8859/` (loopback, `noindex, nofollow`).
- Скриншоты (390 и 1440 px): `docs/screenshots/14d7192/` — главная, игра, раздел, персонаж, билд, квест.
- Артефакт: `var/games-rpg/build/14d7192…/` — 33 файлов.

## Проверки на 14d7192 (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bin/games-rpg test` | 0 | 0 — 11 passed |
| `ruff check . + ruff format --check .` | 0 | 0 — чисто |
| `pytest tests/unit/test_permission_matrix.py` | 0 | 0 — 192 passed |
| `bin/games-rpg build --commit HEAD` | 0 | 0 — 33 файла, var/games-rpg/build/14d7192… |
| `bin/games-rpg qa …` | 0 | 0 — 20 действий PASS; axe 0 |
| `python3 qa/viewports.py 8859 …` | 0 | 0 — 29 URL × 4 ширины, 0 замечаний |
| `bin/games-rpg qa --shots docs/screenshots/14d7192 --out docs/verification-browser-qa.json …` | 0 | 20 действий PASS; axe 0 на 30 стр.×ширин |
| `python3 qa/viewports.py 8859 …` | 0 | 29 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback, без троттлинга) 48–164 мс. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: игра, разделы (персонажи, билды, квесты, механики, предметы), материал с паспортом/прогрессией/этапами/паспортом предмета, версия игры, поиск, печать, 404 |
| наполнение | Baldurs Gate 3: 6 спутников, 3 основы билдов (у 2 кастеров таблица скрыта), 2 механики, 2 квеста, 4 предмета (без цены), версия Patch 8; тексты — manual_standin, не Qwen |
| внешние интеграции | нет (реклама и счётчики выключены) |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT) |
