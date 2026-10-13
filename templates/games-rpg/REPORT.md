# Отчёт games-rpg, вариант C «Гайды RPG» (index-compare)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `c656d3e8dd25975db4d0423ac115a521f73fb03d`, ветка `claude/template-games-rpg-c` (вариант A 0e68f8a (с предметами)).

## Как открыть

- Preview: `http://127.0.0.1:8871/` (loopback, `noindex, nofollow`).
- Отличие от A (8859) и B (8860): главная — указатель А–Я по всем материалам с фильтром по типу; сравнение предметов по полям инфобокса. Свои CSS/JS, ключи grpg-index:*. Сравнение — docs/AUDIT.md.
- Скриншоты (390 и 1440 px): `docs/screenshots/c656d3e/` — сравнение предметов, главная-указатель, игра, раздел, персонаж, билд, квест.
- Артефакт: `var/games-rpg/build/c656d3e…/` — 34 файлов.

## Проверки на c656d3e (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/games-rpg test` | 0 | 0 — 15 passed |
| `ruff check . + ruff format --check .` | 0 | 0 — чисто |
| `pytest tests/unit/test_permission_matrix.py` | 0 | 0 — 192 passed |
| `bash bin/games-rpg build --commit HEAD` | 0 | 0 — 34 файла, var/games-rpg/build/c656d3e… |
| `python3 -m quest.qa …` | 0 | 0 — 27 действий PASS; axe 0 |
| `python3 qa/viewports.py 8871 …` | 0 | 0 — 32 URL × 4 ширины, 0 замечаний |
| `python3 -m quest.qa --shots docs/screenshots/c656d3e --out docs/verification-browser-qa.json …` | 0 | 27 действий PASS; axe 0 на 32 стр.×ширин |
| `python3 qa/viewports.py 8871 …` | 0 | 32 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback, без троттлинга) 52–340 мс. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: указатель А–Я (фильтр по типу, переход по буквам, 400 на неизвестный тип), сравнение предметов, а также всё из A — разделы, материалы с паспортами, версия, поиск, печать, 404 |
| наполнение | как в A: Baldurs Gate 3 — 6 спутников, 3 основы билдов, 2 механики, 2 квеста, 4 предмета (без цены), Patch 8; тексты — manual_standin, не Qwen |
| внешние интеграции | нет (реклама и счётчики выключены) |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT) |
