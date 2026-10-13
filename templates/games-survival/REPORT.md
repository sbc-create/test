# Отчёт games-survival, вариант A «База выживания» (craft-tree)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `7965fdf76ddaecd45818c73bd1ea9e4963f06fa8`, ветка `claude/template-games-survival` (origin/main a7f7cb6).

## Как открыть

- Preview: `http://127.0.0.1:8861/` (loopback, `noindex, nofollow`).
- Скриншоты (390 и 1440 px): `docs/screenshots/7965fdf/` — главная, игра, раздел, предмет, ресурс, биом.
- Артефакт: `var/games-survival/build/7965fdf…/` — 38 файлов.

## Проверки на 7965fdf (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bin/games-survival test` | 0 | 0 — 14 passed |
| `ruff check . + ruff format --check .` | 0 | 0 — чисто |
| `pytest tests/unit/test_permission_matrix.py` | 0 | 0 — 192 passed |
| `bin/games-survival build --commit HEAD` | 0 | 0 — 38 файлов, var/games-survival/build/7965fdf… |
| `bin/games-survival qa …` | 0 | 0 — 22 действия PASS; axe 0 |
| `python3 qa/viewports.py 8861 …` | 0 | 0 — 34 URL × 4 ширины, 0 замечаний |
| `bin/games-survival qa --shots docs/screenshots/7965fdf --out docs/verification-browser-qa.json …` | 0 | 22 действий PASS; axe 0 на 30 стр.×ширин |
| `python3 qa/viewports.py 8861 …` | 0 | 34 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback, без троттлинга) 48–160 мс. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: игра, разделы (предметы и блоки, постройки, ресурсы, биомы), страница с рецептами по сетке (в том числе анимированной) и связями в обе стороны, цепочка старта, версия игры, поиск, печать, 404 |
| наполнение | Minecraft (Java Edition 26.3): 11 предметов/блоков (с киркой), 4 постройки (рецепт двери не разобран — не показан), 4 ресурса, 4 биома, версия; тексты — manual_standin, не Qwen |
| внешние интеграции | нет (реклама и счётчики выключены) |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT) |
