# Отчёт garden-season, вариант A «Дача по сезону» (month-calendar)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `31fec6c3d1e232a126a8f113cfde154ffc31592c`, ветка `claude/template-garden-season`, база origin/main `a7f7cb6`.

## Как открыть

- Preview: `http://127.0.0.1:8853/` (loopback, noindex). Запуск: `bin/garden-season start`.
- Скриншоты (390 и 1440 px): `docs/screenshots/31fec6c/` — главная, октябрь, календарь с фильтром, работа, культура, пустой декабрь.
- Артефакт: `var/garden-season/build/31fec6c…/` — 60 файлов.

## Проверки на 31fec6c (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bin/garden-season test` | 0 | 12 passed |
| `ruff check .` + `ruff format --check .` | 0 | чисто |
| `pytest tests/unit/test_permission_matrix.py` | 0 | 192 passed |
| `bin/garden-season content validate` | 0 | 14/14 |
| `bin/garden-season build --commit HEAD` | 0 | 60 файлов, все URL sitemap 200 |
| `bin/garden-season qa …` | 0 | 29 действий PASS, axe 0 на 23 стр. × 2 |
| `python3 qa/viewports.py 8853 …` | 0 | 58 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback) 36–116 мс, CLS 0. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: лента месяцев, календарь с фильтрами, месяц по регионам, культуры «регион × месяц», регионы, типы работ, подборки, поиск, чек-лист, печать, 404 |
| наполнение | 14 работ, 11 из 12 месяцев, 8 культур; регионы — Орегон (весь штат, западный, центральный и восточный) и Великобритания; **сроков для России нет** — источников с ними не найдено, они не придуманы; тексты — `manual_standin`, не Qwen, без редакторской проверки |
| внешние интеграции | нет |
| production | заблокирован: нет домена и `production_authorized`; для русскоязычной аудитории нужны региональные источники по России — решение владельца |
