# Отчёт plants-home, вариант A «Домашние растения» (plant-catalog)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `f034b3f77003a54ce9588c5421625ba3a53be601`, ветка `claude/template-plants-home`, база origin/main `a7f7cb6`.

## Как открыть

- Preview: `http://127.0.0.1:8855/` (loopback, noindex). Запуск: `bin/plants-home start`.
- Скриншоты (390 и 1440 px): `docs/screenshots/f034b3f/` — главная, каталог с фильтром, карточка, категория света, проблема, пустой фильтр.
- Артефакт: `var/plants-home/build/f034b3f…/` — 46 файлов.

## Проверки на f034b3f (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bin/plants-home test` | 0 | 11 passed |
| `ruff check .` + `ruff format --check .` | 0 | чисто |
| `pytest tests/unit/test_permission_matrix.py` | 0 | 192 passed |
| `bin/plants-home content validate` | 0 | 14/14 |
| `bin/plants-home build --commit HEAD` | 0 | 46 файлов |
| `bin/plants-home qa …` | 0 | 24 действий PASS, axe 0 на 42 стр.×ширин |
| `python3 qa/viewports.py 8855 …` | 0 | 40 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback) 48–148 мс, CLS 0. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: каталог с фильтрами, карточка вида, освещение, проблемы, подборки, поиск по-русски и по латыни, чек-лист, печать, 404 |
| наполнение | 14 видов по NC State Extension; 2 вида без текста ухода не опубликованы; изображений растений нет (свои значки света); тексты — `manual_standin`, не Qwen, без редакторской проверки |
| production | заблокирован: нет домена и `production_authorized` |
