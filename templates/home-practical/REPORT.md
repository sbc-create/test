# Отчёт home-practical, вариант C «Удобный дом» (home-audit)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `d0bd2dc793e6f37b60da5de650a1757c9d8ac0de`, ветка `claude/template-home-practical-c` (вариант A 19fb887).

## Как открыть

- Preview: `http://127.0.0.1:8867/` (loopback, `noindex, nofollow`).
- Отличие от A (8851) и B (8852): вход — обход квартиры по шести помещениям, ключевой итог — личный план (инструкции по комнатам, общий список «Что понадобится», прогресс, печать); выбор в адресе, без JS тоже. Свои CSS/JS, ключи hp-audit:*. Сравнение — docs/AUDIT.md.
- Скриншоты (390 и 1440 px): `docs/screenshots/d0bd2dc/` — главная, помещение, инструкция, подборка, каталог, поиск, шаг обхода, план.
- Артефакт: `var/home-practical/build/d0bd2dc…/` — 56 файлов.

## Проверки на d0bd2dc (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/home-practical test` | 0 | 0 — 17 passed |
| `ruff check . + ruff format --check .` | 0 | 0 — чисто |
| `pytest tests/unit/test_permission_matrix.py` | 0 | 0 — 192 passed |
| `bash bin/home-practical build --commit HEAD` | 0 | 0 — 56 файлов, var/home-practical/build/d0bd2dc… |
| `python3 -m udobdom.qa …` | 0 | 0 — 44 действия PASS; axe 0 |
| `python3 qa/viewports.py 8867 …` | 0 | 0 — 48 URL × 4 ширины, 0 замечаний |
| `python3 -m udobdom.qa --shots docs/screenshots/d0bd2dc --out docs/verification-browser-qa.json …` | 0 | 44 действий PASS; axe 0 на 40 стр.×ширин |
| `python3 qa/viewports.py 8867 …` | 0 | 48 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback, без троттлинга) 56–148 мс. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: обход (6 шагов, перенос выбора, восстановление), план с прогрессом и печатью, а также всё из A — помещения, задачи с фильтрами, инструкции с оглавлением и чек-листом, подборки, теги, поиск, сохранённое, 404 |
| наполнение | тот же набор, что у A: 13 инструкций по 15 источникам (IKEA, CPSC Anchor It); тексты — manual_standin, не Qwen; редакция не проверяла |
| внешние интеграции | нет (реклама и счётчики выключены) |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT) |

## Обновление на f2dc0bf (13.10.2026)

Основной вариант (решение владельца 13.10.2026). Перенесено из B: вход «Что мешает дома» (/problemy/ и 6 страниц проблем из config/problems.yaml варианта B; инструкции по порядку с прогрессом по отметкам чек-листа; ссылки из шапки, меню, главной, инструкции «Решает:» и 404). Сценарий приёмки на 381cccb упал (ссылка в скрытой на телефоне панели) — исправлен в f2dc0bf: на телефоне переход через «Меню».

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/home-practical test` | 0 | 20 passed in 0.80s |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m udobdom.qa --shots docs/screenshots/f2dc0bf --out docs/verification-browser-qa.json` | 0 | 49 действий PASS, axe 0 |
| `python3 qa/viewports.py 8867 '/obhod/plan/?m=aksessuary-na-odnoj-veshalke' '/zadachi/?pomeshchenie=kuhnya&zadacha=mebel' '/poisk/?q=полка' /nesushchestvuet/` | 0 | 55 URL × 4 ширины, 0 замечаний |
| `bash bin/home-practical build --commit HEAD` | 0 | собрано из f2dc0bf |

Лабораторный LCP (loopback, без троттлинга) — до 268 мс. Карта действий — `docs/ACTION-MAP.md`.

## Обновление на 9194af9 (13.10.2026)

Технический SEO (13.10.2026): описания списков (теги, подборки, разделы, типы работ, проблемы) собираются из названий материалов в пределах 160 знаков, длинные описания режутся по границе фразы; суффикс сайта в заголовке выводится, только если заголовок с ним не длиннее 70 знаков. Новый тест tests/test_snippets.py проверяет все URL sitemap (описание 20–160, суффикс — в пределах 70).

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/home-practical test` | 0 | 21 passed in 0.97s |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m udobdom.qa --shots docs/screenshots/9194af9 --out docs/verification-browser-qa.json` | 0 | 49 действий PASS, axe 0 |
| `python3 qa/viewports.py 8867 '/obhod/plan/?m=aksessuary-na-odnoj-veshalke' '/zadachi/?pomeshchenie=kuhnya&zadacha=mebel' '/poisk/?q=полка' /nesushchestvuet/` | 0 | 55 URL × 4 ширины, 0 замечаний |
| `bash bin/home-practical build --commit HEAD` | 0 | собрано из 9194af9 |

Лабораторный LCP (loopback, без троттлинга) — до 128 мс. Карта действий — `docs/ACTION-MAP.md`.
