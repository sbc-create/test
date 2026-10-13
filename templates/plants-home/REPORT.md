# Отчёт plants-home, вариант B «Домашние растения» (pick-and-diagnose)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `e73b076f53825963b3862ad143b221340a3fbf12`, ветка `claude/template-plants-home-b` (вариант A f0f5251).

## Как открыть

- Preview: `http://127.0.0.1:8856/` (loopback, `noindex, nofollow`). Вариант A для сравнения — http://127.0.0.1:8855/; отличия — docs/VARIANTS.md.
- Скриншоты (390 и 1440 px): `docs/screenshots/e73b076/` — главная, результат подбора, сравнение, карточка, диагностика, пустой подбор.
- Артефакт: `var/plants-home/build/e73b076…/` — 53 файлов.

## Проверки на e73b076 (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/plants-home test` | 0 | 0 — 13 passed |
| `ruff check . + ruff format --check .` | 0 | 0 — чисто |
| `pytest tests/unit/test_permission_matrix.py` | 0 | 0 — 192 passed |
| `bash bin/plants-home build --commit HEAD` | 0 | 0 — 53 файла, var/plants-home/build/e73b076… |
| `python3 -m flora.qa …` | 0 | 0 — 25 действий PASS; axe 0 |
| `python3 qa/viewports.py 8856 …` | 0 | 0 — 45 URL × 4 ширины, 0 замечаний |
| `python3 -m flora.qa --shots docs/screenshots/e73b076 --out docs/verification-browser-qa.json …` | 0 | 25 действий PASS; axe 0 на 44 стр.×ширин |
| `python3 qa/viewports.py 8856 …` | 0 | 45 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback, без троттлинга) 52–260 мс. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: подбор по условиям с тремя группами ядовитости, сравнение, «что случилось», карточки видов, поиск, 404 |
| наполнение | 19 видов по NC State Extension Plant Toolbox (5 добавлены ночью 13.10); «нет данных ≠ безопасно»; тексты — manual_standin, не Qwen |
| внешние интеграции | нет (реклама и счётчики выключены) |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT) |
