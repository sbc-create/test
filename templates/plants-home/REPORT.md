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

## Обновление на 595c7d6 (13.10.2026)

Основной вариант (решение владельца 13.10.2026). Перенесено из B: «Что случилось?» (/chto-sluchilos/: симптом → виды → текст справочника вида) и таблица сравнения видов с сортировкой (порядок и вид не индексируются; «нет данных» о ядовитости не выдаётся за «не ядовито»). Улучшение против B: на телефоне строки таблицы — карточки с подписями, без прокрутки вбок.

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/plants-home test` | 0 | 18 passed in 0.62s |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m flora.qa --shots docs/screenshots/595c7d6 --out docs/verification-browser-qa.json` | 0 | 42 действий PASS, axe 0 |
| `python3 qa/viewports.py 8869 '/moi-rasteniya/?r=aloe-vera&r=krassula-ovalnaya&r=sansevieriya-tryohpolosnaya' '/katalog/?sort=uhod&vid=tablica' '/katalog/?svet=solnce&uhod=Medium' '/poisk/?q=Monstera' /nesushchestvuet/` | 0 | 48 URL × 4 ширины, 0 замечаний |
| `bash bin/plants-home build --commit HEAD` | 0 | собрано из 595c7d6 |

Лабораторный LCP (loopback, без троттлинга) — до 264 мс. Карта действий — `docs/ACTION-MAP.md`.

## Обновление на 163ff51 (13.10.2026)

Технический SEO (13.10.2026): описания списков (теги, подборки, разделы, типы работ, проблемы) собираются из названий материалов в пределах 160 знаков, длинные описания режутся по границе фразы; суффикс сайта в заголовке выводится, только если заголовок с ним не длиннее 70 знаков. Новый тест tests/test_snippets.py проверяет все URL sitemap (описание 20–160, суффикс — в пределах 70).

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/plants-home test` | 0 | 19 passed in 0.89s |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m flora.qa --shots docs/screenshots/163ff51 --out docs/verification-browser-qa.json` | 0 | 42 действий PASS, axe 0 |
| `python3 qa/viewports.py 8869 '/moi-rasteniya/?r=aloe-vera&r=krassula-ovalnaya&r=sansevieriya-tryohpolosnaya' '/katalog/?sort=uhod&vid=tablica' '/katalog/?svet=solnce&uhod=Medium' '/poisk/?q=Monstera' /nesushchestvuet/` | 0 | 48 URL × 4 ширины, 0 замечаний |
| `bash bin/plants-home build --commit HEAD` | 0 | собрано из 163ff51 |

Лабораторный LCP (loopback, без троттлинга) — до 164 мс. Карта действий — `docs/ACTION-MAP.md`.

## Обновление на ebae2af (13.10.2026)

Чистая копия: у сервера появился --port, у браузерной приёмки — QA_BASE (проверка рядом с действующим превью на 8901–8910, см. RUN-LOCAL.md в ветке claude/template-food-daily). Проверка контента моделью и скриптами (не человеком; статусы ai_draft не менялись). Контент: спатифиллум — ночной перепад 10 °F (около 5,6 °C), пересчёт в calc.

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/plants-home test` | 0 | 19 passed in 0.94s |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m flora.qa --shots docs/screenshots/ebae2af --out docs/verification-browser-qa.json` | 0 | 42 действий PASS, axe 0 |
| `python3 qa/viewports.py 8869 '/moi-rasteniya/?r=aloe-vera&r=krassula-ovalnaya&r=sansevieriya-tryohpolosnaya' '/katalog/?sort=uhod&vid=tablica' '/katalog/?svet=solnce&uhod=Medium' '/poisk/?q=Monstera' /nesushchestvuet/` | 0 | 48 URL × 4 ширины, 0 замечаний |
| `bash bin/plants-home build --commit HEAD` | 0 | собрано из ebae2af |

Лабораторный LCP (loopback, без троттлинга) — до 440 мс. Карта действий — `docs/ACTION-MAP.md`.

## Перенос и PR (13.10.2026)

- `origin/main` с исправлением lint (PR #71, 304c3d6) влит в ветку обычным merge; `ruff check .` по репозиторию — чисто.
- PR #117 перенацелен с `claude/template-plants-home` на `main`: на старой базе был конфликт слияния, и GitHub не запускал CI для PR.
  Слияния нет, PR остаётся черновиком; вернуть прежнюю базу — `gh pr edit 117 --base claude/template-plants-home`.
- Комплект переноса — `bash bin/plants-home kit build --out <каталог>` (состав и команды — в его `INSTALL.md`).
  Проверен в изолированном каталоге без git (`plants-home-8d7cfee`): `sha256sum -c` — 0, тесты — 21 passed in 1.27s,
  запуск на 8907 — `/healthz` за 0.25 с, главная 200 (`my-collection`),
  43 URL и 8 ресурсов — 0 ошибок.
