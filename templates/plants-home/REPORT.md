# Отчёт plants-home, вариант A «Домашние растения» (plant-catalog)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `c32e8c20ff36f4a7dbe20549c65e2c443f57eabc`, ветка `claude/template-plants-home` (origin/main a7f7cb6).

## Как открыть

- Preview: `http://127.0.0.1:8855/` (loopback, `noindex, nofollow`).
- Скриншоты (390 и 1440 px): `docs/screenshots/c32e8c2/` — главная, каталог, вид, свет, проблема, подборка.
- Артефакт: `var/plants-home/build/c32e8c2…/` — 51 файл.

## Проверки на c32e8c2 (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/plants-home test` | 0 | 0 — 11 passed |
| `ruff check . + ruff format --check .` | 0 | 0 — чисто |
| `pytest tests/unit/test_permission_matrix.py` | 0 | 0 — 192 passed |
| `bash bin/plants-home build --commit HEAD` | 0 | 0 — var/plants-home/build/c32e8c2… |
| `python3 -m flora.qa …` | 0 | 0 — 24 действия PASS; axe 0 |
| `python3 qa/viewports.py 8855 …` | 0 | 0 — 43 URL × 4 ширины, 0 замечаний |
| `python3 -m flora.qa --shots docs/screenshots/c32e8c2 --out docs/verification-browser-qa.json …` | 0 | 24 действий PASS; axe 0 на 42 стр.×ширин |
| `python3 qa/viewports.py 8855 …` | 0 | 43 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback, без троттлинга) 52–204 мс. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: каталог с фильтрами по свету и уходу, карточка вида (условия, проблемы, чек-лист), свет, проблемы, подборки, поиск, 404 |
| наполнение | 19 видов по NC State Extension Plant Toolbox (5 добавлены ночью 13.10); ядовитость — только из источника («нет данных ≠ безопасно»); тексты — manual_standin, не Qwen |
| внешние интеграции | нет (реклама и счётчики выключены) |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT) |
