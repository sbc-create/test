# Отчёт plants-home, вариант C «Домашние растения» (my-collection)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `e6408ee9cc3ecc98d324c419b32b992b987910b5`, ветка `claude/template-plants-home-c` (вариант A f0f5251).

## Как открыть

- Preview: `http://127.0.0.1:8869/` (loopback, `noindex, nofollow`).
- Отличие от A (8855) и B (8856): вход — отметить свои растения; итог — сводка ядовитости (три группы строго по источнику), группы по свету и этикетки ухода для печати. Свои CSS/JS, ключи ph-mine:*. Сравнение — docs/AUDIT.md.
- Скриншоты (390 и 1440 px): `docs/screenshots/e6408ee/` — мои растения (3 вида), главная, каталог, вид, свет, проблема, подборка.
- Артефакт: `var/plants-home/build/e6408ee…/` — 52 файлов.

## Проверки на e6408ee (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/plants-home test` | 0 | 0 — 15 passed |
| `ruff check . + ruff format --check .` | 0 | 0 — чисто |
| `pytest tests/unit/test_permission_matrix.py` | 0 | 0 — 192 passed |
| `bash bin/plants-home build --commit HEAD` | 0 | 0 — 52 файла, var/plants-home/build/e6408ee… |
| `python3 -m flora.qa …` | 0 | 0 — 34 действия PASS; axe 0 |
| `python3 qa/viewports.py 8869 …` | 0 | 0 — 45 URL × 4 ширины, 0 замечаний |
| `python3 -m flora.qa --shots docs/screenshots/e6408ee --out docs/verification-browser-qa.json …` | 0 | 34 действий PASS; axe 0 на 44 стр.×ширин |
| `python3 qa/viewports.py 8869 …` | 0 | 45 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback, без троттлинга) 48–384 мс. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: выбор коллекции (память, блок пустой отправки), сводка ядовитости и света, этикетки и печать, а также всё из A — каталог с фильтрами, свет, проблемы, подборки, поиск, 404 |
| наполнение | 19 видов по NC State Extension Plant Toolbox (5 добавлены ночью 13.10); тексты — manual_standin, не Qwen; редакция не проверяла |
| внешние интеграции | нет (реклама и счётчики выключены) |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT) |
