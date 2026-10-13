# Отчёт garden-season, вариант C «Дача по сезону» (my-plot)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `70b57c09d349b0b5343a78d2cf214ac983830d54`, ветка `claude/template-garden-season-c` (вариант A 18e1723).

## Как открыть

- Preview: `http://127.0.0.1:8868/` (loopback, `noindex, nofollow`).
- Отличие от A (8853) и B (8854): вход — форма «мой участок» (регион источника + культуры), итог — личный календарь на год только из нужных строк, с подписанным регионом у каждой, отметками и печатью. Свои CSS/JS, ключи gs-plot:*. Сравнение — docs/AUDIT.md.
- Скриншоты (390 и 1440 px): `docs/screenshots/70b57c0/` — мой участок (западный Орегон), главная, месяц, декабрь, работа, культура, регион.
- Артефакт: `var/garden-season/build/70b57c0…/` — 66 файлов.

## Проверки на 70b57c0 (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/garden-season test` | 0 | 0 — 16 passed |
| `ruff check . + ruff format --check .` | 0 | 0 — чисто |
| `pytest tests/unit/test_permission_matrix.py` | 0 | 0 — 192 passed |
| `bash bin/garden-season build --commit HEAD` | 0 | 0 — var/garden-season/build/70b57c0… |
| `python3 -m sezon.qa …` | 0 | 0 — 37 действий PASS; axe 0 |
| `python3 qa/viewports.py 8868 …` | 0 | 0 — 64 URL × 4 ширины, 0 замечаний |
| `python3 -m sezon.qa --shots docs/screenshots/70b57c0 --out docs/verification-browser-qa.json …` | 0 | 37 действий PASS; axe 0 на 48 стр.×ширин |
| `python3 qa/viewports.py 8868 …` | 0 | 64 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback, без троттлинга) 44–192 мс. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: форма участка, личный календарь (отметки, прогресс, память выбора, печать, 400 и пустое состояние), а также всё из A — месяцы, культуры, регионы, работы, подборки, поиск, 404 |
| наполнение | 18 работ по календарям OSU Extension (Орегон) и RHS (Великобритания), 4 добавлены ночью 13.10; сроков для России нет — не придуманы; тексты — manual_standin, не Qwen |
| внешние интеграции | нет (реклама и счётчики выключены) |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT) |
