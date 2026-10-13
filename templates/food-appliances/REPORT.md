# Отчёт food-appliances, вариант C «Готовим в технике» (device-queue)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `bb5a44db441d2562ffcc1ce426142445de8005af`, ветка `claude/template-food-appliances-c` (вариант A 7575262).

## Как открыть

- Preview: `http://127.0.0.1:8874/` (loopback, `noindex, nofollow`).
- Отличие от A (8850) и B (8866): вход — отметить несколько рецептов; итог — очередь по приборам и температуре с суммой времени в приборе, отметки «готово». Свои CSS/JS, ключи fac.*. Сравнение — docs/AUDIT.md.
- Скриншоты (390 и 1440 px): `docs/screenshots/bb5a44d/` — очередь (3 рецепта), главная, прибор, категория, рецепт, режим, справка.
- Артефакт: `var/food-appliances/build/bb5a44d…/` — 31 файлов.

## Проверки на bb5a44d (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/food-appliances test` | 0 | 0 — 16 passed |
| `ruff check . + ruff format --check .` | 0 | 0 — чисто |
| `pytest tests/unit/test_permission_matrix.py` | 0 | 0 — 192 passed |
| `bash bin/food-appliances build --commit HEAD` | 0 | 0 — 31 файл, var/food-appliances/build/bb5a44d… |
| `python3 -m techkitchen.qa …` | 0 | 0 — 28 действий PASS; axe 0 |
| `python3 qa/viewports.py 8874 …` | 0 | 0 — 30 URL × 4 ширины, 0 замечаний |
| `python3 -m techkitchen.qa --shots docs/screenshots/bb5a44d --out docs/verification-browser-qa.json …` | 0 | 28 действий PASS; axe 0 на 22 стр.×ширин |
| `python3 qa/viewports.py 8874 …` | 0 | 30 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback, без троттлинга) 44–168 мс. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: выбор рецептов (память, блок пустой отправки, 400), очередь по приборам и температуре, сумма времени, отметки «готово», печать, а также всё из A — приборы, рецепты с табло, режимы, поиск, 404 |
| наполнение | тот же снимок, что у A: 12 рецептов (6 мультиварка, 6 аэрогриль); тексты — manual_standin, не Qwen; редакция не проверяла и не готовила |
| внешние интеграции | нет (реклама и счётчики выключены) |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT) |
