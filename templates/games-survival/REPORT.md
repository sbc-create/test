# Отчёт games-survival, вариант A «База выживания» (craft-tree)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `a14b00d6327bf4522ecfb5d8767f056f50b81916`, ветка `claude/template-games-survival` (origin/main a7f7cb6).

## Как открыть

- Preview: `http://127.0.0.1:8861/` (loopback, `noindex, nofollow`).
- Скриншоты (390 и 1440 px): `docs/screenshots/a14b00d/` — главная, игра, раздел, предмет, ресурс, биом.
- Артефакт: `var/games-survival/build/a14b00d…/` — 41 файлов.

## Проверки на a14b00d (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bin/games-survival test` | 0 | 0 — 15 passed |
| `ruff check . + ruff format --check .` | 0 | 0 — чисто |
| `pytest tests/unit/test_permission_matrix.py` | 0 | 0 — 192 passed |
| `bin/games-survival build --commit HEAD` | 0 | 0 — 41 файл, var/games-survival/build/a14b00d… |
| `bin/games-survival qa …` | 0 | 0 — 22 действия PASS; axe 0 |
| `python3 qa/viewports.py 8861 …` | 0 | 0 — 37 URL × 4 ширины, 0 замечаний |
| `bin/games-survival qa --shots docs/screenshots/a14b00d --out docs/verification-browser-qa.json …` | 0 | 22 действий PASS; axe 0 на 30 стр.×ширин |
| `python3 qa/viewports.py 8861 …` | 0 | 37 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback, без троттлинга) 40–156 мс. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: игра, разделы (предметы и блоки, постройки, ресурсы, биомы), страница с рецептами по сетке (в том числе анимированной) и связями в обе стороны, цепочка старта, версия игры, поиск, печать, 404 |
| наполнение | Minecraft (Java Edition 26.3): 14 предметов/блоков (кирка, топор, лопата, меч), 4 постройки (рецепт двери не разобран — не показан), 4 ресурса, 4 биома, версия; тексты — manual_standin, не Qwen |
| внешние интеграции | нет (реклама и счётчики выключены) |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT) |
