# Отчёт food-weekly, вариант C «Меню на неделю» (own-week)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `a613ec99c41567f1b5bad4f726c288d9450f3af0`, ветка `claude/template-food-weekly-c` (вариант A 1c18349).

## Как открыть

- Preview: `http://127.0.0.1:8873/` (loopback, `noindex, nofollow`).
- Отличие от A (8849) и B (8865): своя неделя с нуля или от плана (21 поле по приёмам пищи), покупки на 1–8 чел. Свои CSS/JS, ключи fwc.*. Сравнение — docs/AUDIT.md.
- Скриншоты (390 и 1440 px): `docs/screenshots/a613ec9/` — своя неделя, главная, каталог планов, неделя плана, день, покупки.
- Артефакт: `var/food-weekly/build/a613ec9…/` — 40 файлов.

## Проверки на a613ec9 (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/food-weekly test` | 0 | 0 — 18 passed |
| `ruff check . + ruff format --check .` | 0 | 0 — чисто |
| `pytest tests/unit/test_permission_matrix.py` | 0 | 0 — 192 passed |
| `bash bin/food-weekly build --commit HEAD` | 0 | 0 — 40 файлов, var/food-weekly/build/a613ec9… |
| `python3 -m weekplan.qa …` | 0 | 0 — 31 действие PASS; axe 0 |
| `python3 qa/viewports.py 8873 …` | 0 | 0 — 38 URL × 4 ширины, 0 замечаний |
| `python3 -m weekplan.qa --shots docs/screenshots/a613ec9 --out docs/verification-browser-qa.json …` | 0 | 31 действий PASS; axe 0 на 20 стр.×ширин |
| `python3 qa/viewports.py 8873 …` | 0 | 38 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback, без троттлинга) 48–636 мс. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: своя неделя (21 поле, план как основа, 1–8 чел., 400), покупки с отметками и печатью, память последней недели, а также всё из A — планы, замены, дни, покупки, подборки, 404 |
| наполнение | те же 3 плана и снимок каталога food-daily, что у A; планы — manual_standin, не Qwen |
| внешние интеграции | каталог рецептов food-daily — снимок от 2026-10-12 (preview_adapter); реклама и счётчики выключены |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT) |

## Обновление на 8397dc4 (13.10.2026)

Основной вариант (решение владельца 13.10.2026). Перенесено из B: покупки плана двумя закупками (пн–ср, чт–вс) и одним списком; у каждой закупки свой счётчик «осталось купить» и свои отметки; ссылки на закупки из недели сохраняют замены. Своя неделя не менялась.

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/food-weekly test` | 0 | 22 passed in 0.63s |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m weekplan.qa --shots docs/screenshots/8397dc4 --out docs/verification-browser-qa.json` | 0 | 35 действий PASS, axe 0 |
| `python3 qa/viewports.py 8873 '/menyu/bystraya-nedelya-dlya-dvoih/pokupki/?s=d1-breakfast-0:lenivye-vareniki' '/svoya-nedelya/?d1-breakfast=lenivye-vareniki&lyudi=4' '/svoya-nedelya/?lyudi=50' /nesushchestvuet/` | 0 | 39 URL × 4 ширины, 0 замечаний |
| `bash bin/food-weekly build --commit HEAD` | 0 | собрано из 8397dc4 |

Лабораторный LCP (loopback, без троттлинга) — до 172 мс. Карта действий — `docs/ACTION-MAP.md`.

## Обновление на 2ffc38f (13.10.2026)

Технический SEO (13.10.2026): описания списков (теги, подборки, разделы, типы работ, проблемы) собираются из названий материалов в пределах 160 знаков, длинные описания режутся по границе фразы; суффикс сайта в заголовке выводится, только если заголовок с ним не длиннее 70 знаков. Новый тест tests/test_snippets.py проверяет все URL sitemap (описание 20–160, суффикс — в пределах 70).

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/food-weekly test` | 0 | 23 passed in 0.77s |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m weekplan.qa --shots docs/screenshots/2ffc38f --out docs/verification-browser-qa.json` | 0 | 35 действий PASS, axe 0 |
| `python3 qa/viewports.py 8873 '/menyu/bystraya-nedelya-dlya-dvoih/pokupki/?s=d1-breakfast-0:lenivye-vareniki' '/svoya-nedelya/?d1-breakfast=lenivye-vareniki&lyudi=4' '/svoya-nedelya/?lyudi=50' /nesushchestvuet/` | 0 | 39 URL × 4 ширины, 0 замечаний |
| `bash bin/food-weekly build --commit HEAD` | 0 | собрано из 2ffc38f |

Лабораторный LCP (loopback, без троттлинга) — до 208 мс. Карта действий — `docs/ACTION-MAP.md`.
