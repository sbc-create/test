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

## Обновление на 1a9ce80 (13.10.2026)

Meta description длиннее одного предложения теперь режется по запятой или тире (а не посреди фразы, как «…с которыми нельзя…»); у garden-season описания работ были до 263 символов — теперь ≤160. Тест проверяет все URL sitemap (20–160 символов) и случай с запятой.

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/garden-season test` | 0 | 17 passed in 0.84s |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m sezon.qa --shots docs/screenshots/1a9ce80 --out docs/verification-browser-qa.json` | 0 | 37 действий PASS, axe 0 |
| `python3 qa/viewports.py 8868 '/moj-uchastok/?region=or-west&k=chesnok&k=tomaty&obshchie=1' '/moj-uchastok/?region=moskva&k=chesnok' '/moj-uchastok/?region=uk&k=golubika' /nesushchestvuet/` | 0 | 64 URL × 4 ширины, 0 замечаний |
| `bash bin/garden-season build --commit HEAD` | 0 | собрано из 1a9ce80 |

Лабораторный LCP (loopback, без троттлинга) — до 376 мс. Карта действий — `docs/ACTION-MAP.md`.

## Обновление на aae3ff2 (13.10.2026)

Основной вариант (решение владельца 13.10.2026). Идея из B: в шапке «Мой участок: <регион>» — ссылка на последний показанный участок (без JS — на форму). Исправлено: неизвестный регион (400) и выбор без работ больше не перезаписывают запомненный участок. Дополнительно: шапка с заполненным хранилищем на 320/390/768/1440 px (/, /kalendar/, /kultury/) — без горизонтального скролла (scratchpad hdr_check.py, exit 0).

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/garden-season test` | 0 | 18 passed in 1.12s |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m sezon.qa --shots docs/screenshots/aae3ff2 --out docs/verification-browser-qa.json` | 0 | 40 действий PASS, axe 0 |
| `python3 qa/viewports.py 8868 '/moj-uchastok/?region=or-west&k=chesnok&k=tomaty&obshchie=1' '/moj-uchastok/?region=moskva&k=chesnok' '/moj-uchastok/?region=uk&k=golubika' /nesushchestvuet/` | 0 | 64 URL × 4 ширины, 0 замечаний |
| `bash bin/garden-season build --commit HEAD` | 0 | собрано из aae3ff2 |

Лабораторный LCP (loopback, без троттлинга) — до 304 мс. Карта действий — `docs/ACTION-MAP.md`.

## Обновление на ceb8900 (13.10.2026)

Технический SEO (13.10.2026): описания списков (теги, подборки, разделы, типы работ, проблемы) собираются из названий материалов в пределах 160 знаков, длинные описания режутся по границе фразы; суффикс сайта в заголовке выводится, только если заголовок с ним не длиннее 70 знаков. Новый тест tests/test_snippets.py проверяет все URL sitemap (описание 20–160, суффикс — в пределах 70).

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/garden-season test` | 0 | 19 passed in 1.10s |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m sezon.qa --shots docs/screenshots/ceb8900 --out docs/verification-browser-qa.json` | 0 | 40 действий PASS, axe 0 |
| `python3 qa/viewports.py 8868 '/moj-uchastok/?region=or-west&k=chesnok&k=tomaty&obshchie=1' '/moj-uchastok/?region=moskva&k=chesnok' '/moj-uchastok/?region=uk&k=golubika' /nesushchestvuet/` | 0 | 64 URL × 4 ширины, 0 замечаний |
| `bash bin/garden-season build --commit HEAD` | 0 | собрано из ceb8900 |

Лабораторный LCP (loopback, без троттлинга) — до 188 мс. Карта действий — `docs/ACTION-MAP.md`.
