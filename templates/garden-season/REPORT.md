# Отчёт garden-season, вариант B «Дача по сезону» (region-timeline)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `410502a109e1127d748829469565d6fe12f7e434`, ветка `claude/template-garden-season-b` (вариант A 18e1723).

## Как открыть

- Preview: `http://127.0.0.1:8854/` (loopback, `noindex, nofollow`). Вариант A для сравнения — http://127.0.0.1:8853/; отличия — docs/VARIANTS.md.
- Скриншоты (390 и 1440 px): `docs/screenshots/410502a/` — главная, регион, регион с фильтром, работа, культура, декабрь.
- Артефакт: `var/garden-season/build/410502a…/` — 64 файлов.

## Проверки на 410502a (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/garden-season test` | 0 | 0 — 13 passed |
| `ruff check . + ruff format --check .` | 0 | 0 — чисто |
| `pytest tests/unit/test_permission_matrix.py` | 0 | 0 — 192 passed |
| `bash bin/garden-season build --commit HEAD` | 0 | 0 — 64 файла, var/garden-season/build/410502a… |
| `python3 -m sezon.qa …` | 0 | 0 — 29 действий PASS; axe 0 |
| `python3 qa/viewports.py 8854 …` | 0 | 0 — 60 URL × 4 ширины, 0 замечаний |
| `python3 -m sezon.qa --shots docs/screenshots/410502a --out docs/verification-browser-qa.json …` | 0 | 29 действий PASS; axe 0 на 44 стр.×ширин |
| `python3 qa/viewports.py 8854 …` | 0 | 60 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback, без троттлинга) 52–160 мс. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: сначала регион (запоминается), лента региона с фильтрами, месяцы, работы, культуры, поиск, 404 |
| наполнение | 17 работ по календарям OSU Extension и RHS (3 добавлены ночью 13.10); сроков для России нет — не придуманы; тексты — manual_standin, не Qwen |
| внешние интеграции | нет (реклама и счётчики выключены) |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT) |
