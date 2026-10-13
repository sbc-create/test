# Отчёт games-survival, вариант C «База выживания» (inventory-first)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `90475abeb75c5c142433275242a9eae4776135d9`, ветка `claude/template-games-survival-c` (вариант B 978d803).

## Как открыть

- Preview: `http://127.0.0.1:8872/` (loopback, `noindex, nofollow`).
- Отличие от A (8861) и B (8862): главная — отметки инвентаря; итог — «можно сделать сейчас» и «не хватает одного» с количествами по слотам сетки; планировщик B сохранён. Свои CSS/JS, ключи gsv-inv:*. Сравнение — docs/AUDIT.md.
- Скриншоты (390 и 1440 px): `docs/screenshots/90475ab/` — инвентарь (доски, палка, уголь), главная, планировщик, игра, раздел, предмет, ресурс, биом.
- Артефакт: `var/games-survival/build/90475ab…/` — 39 файлов.

## Проверки на 90475ab (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bin/games-survival test` | 0 | 0 — 21 passed |
| `ruff check . + ruff format --check .` | 0 | 0 — чисто |
| `pytest tests/unit/test_permission_matrix.py` | 0 | 0 — 192 passed |
| `bin/games-survival build --commit HEAD` | 0 | 0 — 39 файлов, var/games-survival/build/90475ab… |
| `bin/games-survival qa …` | 0 | 0 — 36 действий PASS; axe 0 |
| `python3 qa/viewports.py 8872 …` | 0 | 0 — 37 URL × 4 ширины, 0 замечаний |
| `bin/games-survival qa --shots docs/screenshots/90475ab --out docs/verification-browser-qa.json …` | 0 | 36 действий PASS; axe 0 на 38 стр.×ширин |
| `python3 qa/viewports.py 8872 …` | 0 | 37 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback, без троттлинга) 40–164 мс. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: инвентарь (память выбора, блок пустой отправки, 400), «можно сейчас» и «не хватает одного», планировщик из B, каталог, предметы, постройки, поиск, 404 |
| наполнение | как в A/B: Minecraft (Java Edition 26.3), 10 предметов/блоков, 4 постройки, 4 ресурса, 4 биома; тексты — manual_standin, не Qwen |
| внешние интеграции | нет (реклама и счётчики выключены) |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT) |
