# Отчёт games-rpg, вариант A «Гайды RPG» (codex-sections)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `125d8842a6bdc162acf94e073953ed1c9bace2bb`, ветка `claude/template-games-rpg` (база origin/main a7f7cb6).

## Как открыть

- Preview: `http://127.0.0.1:8859/` (loopback, `noindex, nofollow`).
- Скриншоты (390 и 1440 px): `docs/screenshots/125d884/` — главная, игра, раздел, персонаж, билд, квест.
- Артефакт: `var/games-rpg/build/125d884…/` — 28 файлов.

## Проверки на 125d884 (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bin/games-rpg test` | 0 | 9 passed |
| `ruff check . + ruff format --check .` | 0 | чисто |
| `pytest tests/unit/test_permission_matrix.py` | 0 | 192 passed |
| `bin/games-rpg build --commit HEAD` | 0 | см. var/games-rpg/build |
| `bin/games-rpg qa …` | 0 | 20 действий PASS; axe 0 на 30 стр.×ширин |
| `python3 qa/viewports.py 8859 …` | 0 | 24 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback, без троттлинга) 40–132 мс. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: игра, разделы (персонажи, билды, квесты, механики), материал с паспортом/прогрессией/этапами, версия игры, поиск, печать, 404 |
| наполнение | Baldurs Gate 3: 6 спутников, 3 основы билдов (у 2 кастеров таблица скрыта), 2 механики, 2 квеста, версия Patch 8; раздел предметов не опубликован — нет проверенных фактов; тексты — `manual_standin`, не Qwen |
| внешние интеграции | нет (реклама и счётчики выключены) |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT) |
