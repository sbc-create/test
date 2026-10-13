# Отчёт food-daily, вариант C «Будни на кухне» (party-list)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `e0130d50c506f400230963874b0c32bb224ad747`, ветка `claude/template-food-daily-c` (вариант A aab3470).

## Как открыть

- Preview: `http://127.0.0.1:8876/` (loopback, `noindex, nofollow`).
- Отличие от A (8847) и B (8863): вход — несколько блюд и число гостей; итог — общий пересчитанный список продуктов с отметками. Свои CSS/JS, ключи fdc.*. Сравнение — docs/audit/variant-c.md.
- Скриншоты (390 и 1440 px): `docs/screenshots/e0130d5/` — на компанию (8 гостей), главная, каталог, рецепт, продукт, совет.
- Артефакт: `var/food-daily/build/e0130d5…/` — 68 файлов.

## Проверки на e0130d5 (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/food-daily test` | 0 | 0 — 122 passed |
| `ruff check . + ruff format --check .` | 0 | 0 — чисто |
| `pytest tests/unit/test_permission_matrix.py` | 0 | 0 — 192 passed |
| `bash bin/food-daily build --commit HEAD` | 0 | 0 — var/food-daily/build/e0130d5… |
| `python3 -m fooddaily.qa_browser …` | 0 | 0 — 36 действий PASS; axe 0; контраст 0 |
| `python3 qa/viewports.py 8876 …` | 0 | 0 — 56 URL × 4 ширины, 0 замечаний |
| `python3 -m fooddaily.qa_browser --shots docs/screenshots/e0130d5 --out docs/verification-browser-qa.json …` | 0 | 36 действий PASS; axe 0 на 30 стр.×ширин |
| `python3 qa/viewports.py 8876 …` | 0 | 56 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback, без троттлинга) 60–212 мс. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: выбор блюд и гостей (память, блок пустой отправки, 400), общий пересчитанный список с отметками и печатью, а также всё из A — каталог, рецепты с порциями и режимом готовки, покупки, избранное, поиск, 404 |
| наполнение | тот же снимок, что у A: 22 рецепта, 3 совета; тексты — черновики сессии Claude (manual_standin), не Qwen; редакция не проверяла |
| внешние интеграции | нет (реклама и счётчики выключены) |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT) |

## Обновление на fff36e7 (13.10.2026): редактор

Исправлено: на 390 px таблица редактора давала горизонтальный скролл, `<pre>` не был доступен с клавиатуры, поля diff и выбор решения были без подписей (axe: label, select-name, scrollable-region-focusable).

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/food-daily test` | 0 | PASS |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m fooddaily.qa_browser --shots docs/screenshots/fff36e7 --out docs/verification-browser-qa.json` | 0 | 36 действий PASS, axe 0 |
| `python3 qa/viewports.py 8876 …` | 0 | 56 URL × 4 ширины, 0 замечаний |
| `bash bin/food-daily build --commit HEAD` | 0 | собрано из fff36e7 |
| приёмка редактора (scratchpad `ed_qa.py`) | 0 | 26 проверок PASS — `docs/verification-editor.json` |

Редактор: было NOT_RUN (секрет не создавался), теперь проверен на изолированной копии этого коммита; способ и
ограничения — в `docs/verification-editor.json`. Решение «editor_rejected» записывалось только в копию БД.

## Обновление на 2f441f3 (13.10.2026)

Основной вариант (решение владельца 13.10.2026). Перенесено из B: подбор «Что есть дома» (/iz-holodilnika/: выбор, результаты с «есть / ещё нужно», память выбора, пустой выбор блокируется, неизвестный продукт — 400), в каталоге — порядок и вид-таблица (не индексируются). Редактор не менялся — его проверка остаётся в docs/verification-editor.json.

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/food-daily test` | 0 | 128 passed in 12.96s |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m fooddaily.qa_browser --shots docs/screenshots/2f441f3 --out docs/verification-browser-qa.json` | 0 | 51 действий PASS, axe 0 |
| `python3 qa/viewports.py 8876 '/na-kompaniyu/?r=plov-s-kuricej&r=grecheskij-salat&gosti=8' '/iz-holodilnika/?est=kurica&est=ris' '/iz-holodilnika/?est=kvantovyj' '/recepty/?sort=vremya&vid=tablica' '/poisk/?q=творог' /nesushchestvuet/` | 0 | 59 URL × 4 ширины, 0 замечаний |
| `bash bin/food-daily build --commit HEAD` | 0 | собрано из 2f441f3 |

Лабораторный LCP (loopback, без троттлинга) — до 504 мс. Карта действий — `docs/ACTION-MAP.md`.

## Обновление на 043e2f5 (13.10.2026)

Технический SEO (13.10.2026): описания списков (теги, подборки, разделы, типы работ, проблемы) собираются из названий материалов в пределах 160 знаков, длинные описания режутся по границе фразы; суффикс сайта в заголовке выводится, только если заголовок с ним не длиннее 70 знаков. Новый тест tests/test_snippets.py проверяет все URL sitemap (описание 20–160, суффикс — в пределах 70).

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/food-daily test` | 0 | 129 passed in 11.72s |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m fooddaily.qa_browser --shots docs/screenshots/043e2f5 --out docs/verification-browser-qa.json` | 0 | 51 действий PASS, axe 0 |
| `python3 qa/viewports.py 8876 '/na-kompaniyu/?r=plov-s-kuricej&r=grecheskij-salat&gosti=8' '/iz-holodilnika/?est=kurica&est=ris' '/iz-holodilnika/?est=kvantovyj' '/recepty/?sort=vremya&vid=tablica' '/poisk/?q=творог' /nesushchestvuet/` | 0 | 59 URL × 4 ширины, 0 замечаний |
| `bash bin/food-daily build --commit HEAD` | 0 | собрано из 043e2f5 |

Лабораторный LCP (loopback, без троттлинга) — до 164 мс. Карта действий — `docs/ACTION-MAP.md`.

## Обновление на 7e7fb52 (13.10.2026)

Чистая копия: у сервера появился --port, у браузерной приёмки — QA_BASE (проверка рядом с действующим превью на 8901–8910, см. RUN-LOCAL.md в ветке claude/template-food-daily). Проверка контента моделью и скриптами (не человеком; статусы ai_draft не менялись).

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/food-daily test` | 0 | 129 passed in 6.76s |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m fooddaily.qa_browser --shots docs/screenshots/7e7fb52 --out docs/verification-browser-qa.json` | 0 | 51 действий PASS, axe 0 |
| `python3 qa/viewports.py 8876 '/na-kompaniyu/?r=plov-s-kuricej&r=grecheskij-salat&gosti=8' '/iz-holodilnika/?est=kurica&est=ris' '/iz-holodilnika/?est=kvantovyj' '/recepty/?sort=vremya&vid=tablica' '/poisk/?q=творог' /nesushchestvuet/` | 0 | 59 URL × 4 ширины, 0 замечаний |
| `bash bin/food-daily build --commit HEAD` | 0 | собрано из 7e7fb52 |

Лабораторный LCP (loopback, без троттлинга) — до 224 мс. Карта действий — `docs/ACTION-MAP.md`.

## Обновление на 6e1f1dc (13.10.2026)

Редакционный механизм: изолированная база варианта (editorial clone-db — копия базы A, сверена со снимком C: 22 из 22), правки только новыми версиями (editorial revise: конфликт базы, числа — из записи источника, ворота публикации). Подсказка к чечевичному супу исправлена (v2): новая версия в базе, на странице после пересборки снимка, сохраняется после двух перезапусков превью. Разбор подсказок и замен (моделью, не человеком): на страницах 9 подсказок и 2 замены со ссылкой на шаг источника; 21 подсказка и 20 замен — в editor_notes (22 версии). Веб-редактор /redaktor/ проверен на изолированной копии ad0073b с собственной базой C и своей тестовой учёткой (пароль действующего превью не читался): 26 проверок PASS, чечевичный суп показывает v1–v3, diff v1→v2 содержит старую и новую подсказку, снятые со страниц пункты видны редактору — docs/verification-editor.json.

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/food-daily test` | 0 | 137 passed in 14.50s |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m fooddaily.qa_browser --shots docs/screenshots/6e1f1dc --out docs/verification-browser-qa.json` | 0 | 53 действий PASS, axe 0 |
| `python3 qa/viewports.py 8876 '/na-kompaniyu/?r=plov-s-kuricej&r=grecheskij-salat&gosti=8' '/iz-holodilnika/?est=kurica&est=ris' '/iz-holodilnika/?est=kvantovyj' '/recepty/?sort=vremya&vid=tablica' '/poisk/?q=творог' /nesushchestvuet/` | 0 | 59 URL × 4 ширины, 0 замечаний |
| `bash bin/food-daily build --commit HEAD` | 0 | собрано из 6e1f1dc |

Лабораторный LCP (loopback, без троттлинга) — до 184 мс. Карта действий — `docs/ACTION-MAP.md`.

## Обновление на 9514da0 (13.10.2026)

Пункты галереи (13.10.2026). Новый адрес рецепта курицы /recept/kurica-v-smetanno-chesnochnom-souse/ с редиректом 301 со старого (editorial rename, v3).

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/food-daily test` | 0 | 141 passed in 10.26s |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m fooddaily.qa_browser --shots docs/screenshots/9514da0 --out docs/verification-browser-qa.json` | 0 | 53 действий PASS, axe 0 |
| `python3 qa/viewports.py 8876 '/na-kompaniyu/?r=plov-s-kuricej&r=grecheskij-salat&gosti=8' '/iz-holodilnika/?est=kurica&est=ris' '/iz-holodilnika/?est=kvantovyj' '/recepty/?sort=vremya&vid=tablica' '/poisk/?q=творог' /nesushchestvuet/` | 0 | 59 URL × 4 ширины, 0 замечаний |
| `bash bin/food-daily build --commit HEAD` | 0 | собрано из 9514da0 |

Лабораторный LCP (loopback, без троттлинга) — до 572 мс. Карта действий — `docs/ACTION-MAP.md`.

## Перенос и PR (13.10.2026)

- `origin/main` с исправлением lint (PR #71, 304c3d6) влит в ветку обычным merge; `ruff check .` по репозиторию — чисто.
- PR #124 перенацелен с `claude/template-food-daily` на `main`: на старой базе был конфликт слияния, и GitHub не запускал CI для PR.
  Слияния нет, PR остаётся черновиком; вернуть прежнюю базу — `gh pr edit 124 --base claude/template-food-daily`.
- Комплект переноса — `bash bin/food-daily kit build --out <каталог>` (состав и команды — в его `INSTALL.md`).
  Проверен в изолированном каталоге без git (`food-daily-6663171`): `sha256sum -c` — 0, тесты — 141 passed in 12.43s,
  запуск на 8901 — `/healthz` за 0.25 с, главная 200 (`party-list`),
  53 URL и 3 ресурсов — 0 ошибок.
