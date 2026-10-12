# Отчёт garden-season, вариант C «Дача по сезону» (my-plot)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `0b9f676d41333863a1ffdbe117ca9182ff0d9c3e`, ветка `claude/template-garden-season-c` (вариант A 18e1723).

## Как открыть

- Preview: `http://127.0.0.1:8868/` (loopback, `noindex, nofollow`).
- Отличие от A (8853) и B (8854): вход — форма «мой участок» (регион источника + культуры), итог — личный календарь на год только из нужных строк, с подписанным регионом у каждой, отметками и печатью. Свои CSS/JS, ключи gs-plot:*. Сравнение — docs/AUDIT.md.
- Скриншоты (390 и 1440 px): `docs/screenshots/0b9f676/` — мой участок (западный Орегон), главная, месяц, работа, культура, регион, подборка.
- Артефакт: `var/garden-season/build/0b9f676…/` — 61 файлов.

## Проверки на 0b9f676 (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/garden-season test` | 0 | 0 — 16 passed |
| `ruff check . + ruff format --check .` | 0 | 0 — чисто |
| `pytest tests/unit/test_permission_matrix.py` | 0 | 0 — 192 passed |
| `bash bin/garden-season build --commit HEAD` | 0 | 0 — 61 файл, var/garden-season/build/0b9f676… |
| `python3 -m sezon.qa …` | 0 | 0 — 37 действий PASS; axe 0 |
| `python3 qa/viewports.py 8868 …` | 0 | 0 — 59 URL × 4 ширины, 0 замечаний |
| `python3 -m sezon.qa --shots docs/screenshots/0b9f676 --out docs/verification-browser-qa.json …` | 0 | 37 действий PASS; axe 0 на 48 стр.×ширин |
| `python3 qa/viewports.py 8868 …` | 0 | 59 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback, без троттлинга) 44–260 мс. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: форма участка, личный календарь (отметки, прогресс, память выбора, печать, 400 и пустое состояние), а также всё из A — месяцы, культуры, регионы, работы, подборки, поиск, 404 |
| наполнение | тот же набор, что у A: 14 работ по календарям OSU Extension (Орегон) и RHS (Великобритания); сроков для России в источниках нет — не придуманы; тексты — manual_standin, не Qwen |
| внешние интеграции | нет (реклама и счётчики выключены) |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT) |
