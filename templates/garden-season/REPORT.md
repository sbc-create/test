# Отчёт garden-season, вариант A «Дача по сезону» (month-calendar)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `2ba827da6c51f32a4ff785cb47025068138d05df`, ветка `claude/template-garden-season` (origin/main a7f7cb6).

## Как открыть

- Preview: `http://127.0.0.1:8853/` (loopback, `noindex, nofollow`).
- Скриншоты (390 и 1440 px): `docs/screenshots/2ba827d/` — главная, месяц, декабрь, работа, культура, регион.
- Артефакт: `var/garden-season/build/2ba827d…/` — 65 файлов.

## Проверки на 2ba827d (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/garden-season test` | 0 | 0 — 12 passed |
| `ruff check . + ruff format --check .` | 0 | 0 — чисто |
| `pytest tests/unit/test_permission_matrix.py` | 0 | 0 — 192 passed |
| `bash bin/garden-season build --commit HEAD` | 0 | 0 — var/garden-season/build/2ba827d… |
| `python3 -m sezon.qa …` | 0 | 0 — 29 действий PASS; axe 0 |
| `python3 qa/viewports.py 8853 …` | 0 | 0 — 61 URL × 4 ширины, 0 замечаний |
| `python3 -m sezon.qa --shots docs/screenshots/2ba827d --out docs/verification-browser-qa.json …` | 0 | 29 действий PASS; axe 0 на 46 стр.×ширин |
| `python3 qa/viewports.py 8853 …` | 0 | 61 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback, без троттлинга) 44–472 мс. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: год по месяцам, месяц с группами по регионам, работа со сроками и регионом, культуры с сеткой регион × месяц, регионы, подборки, поиск, 404 |
| наполнение | 18 работ по календарям OSU Extension (Орегон) и RHS (Великобритания), 4 добавлены ночью 13.10; сроков для России в источниках нет — не придуманы; тексты — manual_standin, не Qwen |
| внешние интеграции | нет (реклама и счётчики выключены) |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT) |
