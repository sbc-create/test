# Отчёт games-survival, вариант A «База выживания» (craft-tree)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `865d7d2df4f5730c51ae6e5ce8914dba4675f1d1`, ветка `claude/template-games-survival` (origin/main a7f7cb6).

## Как открыть

- Preview: `http://127.0.0.1:8861/` (loopback, `noindex, nofollow`).
- Скриншоты (390 и 1440 px): `docs/screenshots/865d7d2/` — главная, игра, раздел, предмет, ресурс, биом.
- Артефакт: `var/games-survival/build/865d7d2…/` — 32 файлов.

## Проверки на 865d7d2 (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bin/games-survival test` | 0 | 0 — 11 passed |
| `ruff check . + ruff format --check .` | 0 | 0 — чисто |
| `pytest tests/unit/test_permission_matrix.py` | 0 | 0 — 192 passed |
| `bin/games-survival build --commit HEAD` | 0 | 0 — 32 файла, var/games-survival/build/865d7d2… |
| `bin/games-survival qa …` | 0 | 0 — 22 действия PASS; axe 0 |
| `python3 qa/viewports.py 8861 …` | 0 | 0 — 28 URL × 4 ширины, 0 замечаний |
| `bin/games-survival qa --shots docs/screenshots/865d7d2 --out docs/verification-browser-qa.json …` | 0 | 22 действий PASS; axe 0 на 30 стр.×ширин |
| `python3 qa/viewports.py 8861 …` | 0 | 28 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback, без троттлинга) 40–172 мс. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: игра, разделы (предметы и блоки, ресурсы, биомы), страница предмета с рецептами по сетке и связями в обе стороны, цепочка старта, версия игры, поиск, печать, 404 |
| наполнение | Minecraft (Java Edition 26.3): 10 предметов/блоков, 4 ресурса, 4 биома, страница версии; рецепты кирки и раздел построек не выпущены (GV-05, GV-06); тексты — manual_standin, не Qwen |
| внешние интеграции | нет (реклама и счётчики выключены) |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT) |
