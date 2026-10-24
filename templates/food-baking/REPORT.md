# Отчёт food-baking, вариант B «Тесто и десерты» (oven-bench)

Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**. Проверенный код: `3f222ce7bf5edcda38109c9429b6bbca0c5ba6ce`, ветка `claude/template-food-baking-b` (вариант A 8a5cb1e).

## Как открыть

- Preview: `http://127.0.0.1:8864/` (loopback, `noindex, nofollow`).
- Отличие от A (8848): главная по температуре духовки, каталог — таблица сравнения с сортировкой, рецепт — рабочий лист (полоса духовки, «Отвесить» с пекарским процентом, шаги с отметками и таймером в своём шаге); свои CSS/JS, ключи fbb.*. Сравнение — docs/AUDIT.md.
- Скриншоты (390 и 1440 px): `docs/screenshots/3f222ce/` — главная, каталог, рецепт (кекс), рецепт с пекарским процентом, вид теста, разбор ошибок.
- Артефакт: `var/food-baking/build/3f222ce…/` — 31 файлов.

## Проверки на 3f222ce (фактически запущены)

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/food-baking test` | 0 | 0 — 26 passed |
| `ruff check . + ruff format --check .` | 0 | 0 — чисто |
| `pytest tests/unit/test_permission_matrix.py` | 0 | 0 — 192 passed |
| `bash bin/food-baking build --commit HEAD` | 0 | 0 — 31 файл, var/food-baking/build/3f222ce… |
| `python3 -m bakebook.qa …` | 0 | 0 — 33 действия PASS; axe 0 |
| `python3 qa/viewports.py 8864 …` | 0 | 0 — 29 URL × 4 ширины, 0 замечаний |
| `python3 -m bakebook.qa --shots docs/screenshots/3f222ce --out docs/verification-browser-qa.json …` | 0 | 33 действий PASS; axe 0 на 30 стр.×ширин |
| `python3 qa/viewports.py 8864 …` | 0 | 29 URL × 4 ширины — 0 замечаний |

LCP (лаборатория, loopback, без троттлинга) 48–256 мс. Карта действий — `docs/ACTION-MAP.md`.

## Готовность

| слой | состояние |
| --- | --- |
| интерфейс | готов: по температуре с якорями, таблица сравнения с фильтрами и сортировкой, рабочий лист (пекарский процент, отметки «отвешено» и шагов с сохранением и сбросом, таймеры из источника), виды теста, разборы ошибок, поиск, 404 |
| наполнение | тот же снимок, что у A: 13 рецептов (eda.rambler.ru, факты); тексты — manual_standin, не Qwen; редакция не проверяла и не пекла |
| внешние интеграции | нет (реклама и счётчики выключены) |
| production | заблокирован: нет домена и `production_authorized` (BLOCKED_INPUT) |

## Обновление на 229f66b (13.10.2026): редактор

Исправлено: на 390 px таблица редактора давала горизонтальный скролл.

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/food-baking test` | 0 | PASS |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m bakebook.qa --shots docs/screenshots/229f66b --out docs/verification-browser-qa.json` | 0 | 33 действий PASS, axe 0 |
| `python3 qa/viewports.py 8864 …` | 0 | 29 URL × 4 ширины, 0 замечаний |
| `bash bin/food-baking build --commit HEAD` | 0 | собрано из 229f66b |
| приёмка редактора (scratchpad `ed_qa.py`) | 0 | 14 проверок PASS — `docs/verification-editor.json` |

Редактор: было NOT_RUN (секрет не создавался), теперь проверен на изолированной копии этого коммита; способ и
ограничения — в `docs/verification-editor.json`. Решение «editor_rejected» записывалось только в копию БД.

## Обновление на 37fe950 (13.10.2026)

Основной вариант (решение владельца 13.10.2026). Перенесено из C: «Пеку несколько» (/pechem/: общий список продуктов по нескольким рецептам, группы по температуре духовки, отметки купленного, память выбора, пустой выбор блокируется, неизвестный рецепт — 400). Отметки «отвешено» в B уже были (marks_persist_after_reload, reset_clears_marks) — перенос не нужен. Редактор не менялся.

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/food-baking test` | 0 | 30 passed in 0.77s |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m bakebook.qa --shots docs/screenshots/37fe950 --out docs/verification-browser-qa.json` | 0 | 44 действий PASS, axe 0 |
| `python3 qa/viewports.py 8864 '/pechem/?r=limonnyj-keks&r=yablochnoe-myagkoe-pechene&r=tort-bez-vypechki-s-vinogradom' '/pechem/?r=neizvestno' '/recepty/?sort=temp' '/poisk/?q=печенье' /nesushchestvuet/` | 0 | 31 URL × 4 ширины, 0 замечаний |
| `bash bin/food-baking build --commit HEAD` | 0 | собрано из 37fe950 |

Лабораторный LCP (loopback, без троттлинга) — до 284 мс. Карта действий — `docs/ACTION-MAP.md`.

## Обновление на 55f09b2 (13.10.2026)

Технический SEO (13.10.2026): описания списков (теги, подборки, разделы, типы работ, проблемы) собираются из названий материалов в пределах 160 знаков, длинные описания режутся по границе фразы; суффикс сайта в заголовке выводится, только если заголовок с ним не длиннее 70 знаков. Новый тест tests/test_snippets.py проверяет все URL sitemap (описание 20–160, суффикс — в пределах 70).

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/food-baking test` | 0 | 31 passed in 0.96s |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m bakebook.qa --shots docs/screenshots/55f09b2 --out docs/verification-browser-qa.json` | 0 | 44 действий PASS, axe 0 |
| `python3 qa/viewports.py 8864 '/pechem/?r=limonnyj-keks&r=yablochnoe-myagkoe-pechene&r=tort-bez-vypechki-s-vinogradom' '/pechem/?r=neizvestno' '/recepty/?sort=temp' '/poisk/?q=печенье' /nesushchestvuet/` | 0 | 31 URL × 4 ширины, 0 замечаний |
| `bash bin/food-baking build --commit HEAD` | 0 | собрано из 55f09b2 |

Лабораторный LCP (loopback, без троттлинга) — до 220 мс. Карта действий — `docs/ACTION-MAP.md`.

## Обновление на 4356f03 (13.10.2026)

Чистая копия: у сервера появился --port, у браузерной приёмки — QA_BASE (проверка рядом с действующим превью на 8901–8910, см. RUN-LOCAL.md в ветке claude/template-food-daily). Проверка контента моделью и скриптами (не человеком; статусы ai_draft не менялись). Контент: три предупреждения переписаны строго по шагам источника (версии 2). Тесты сверки черновиков без закрытых снимков var/…/private — SKIPPED с причиной (в этой рабочей копии снимки есть, тесты выполнены).

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/food-baking test` | 0 | 31 passed in 0.85s |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m bakebook.qa --shots docs/screenshots/4356f03 --out docs/verification-browser-qa.json` | 0 | 44 действий PASS, axe 0 |
| `python3 qa/viewports.py 8864 '/pechem/?r=limonnyj-keks&r=yablochnoe-myagkoe-pechene&r=tort-bez-vypechki-s-vinogradom' '/pechem/?r=neizvestno' '/recepty/?sort=temp' '/poisk/?q=печенье' /nesushchestvuet/` | 0 | 31 URL × 4 ширины, 0 замечаний |
| `bash bin/food-baking build --commit HEAD` | 0 | собрано из 4356f03 |

Лабораторный LCP (loopback, без троттлинга) — до 228 мс. Карта действий — `docs/ACTION-MAP.md`.

## Обновление на 09b03fc (13.10.2026): тесты в чистой копии

Логика валидатора черновиков проверяется на синтетической фикстуре `tests/fixtures/validator_case.json`
(не из источника), добавлена сверка черновиков с публичными фактами из git.

| где | команда | exit | результат |
| --- | --- | --- | --- |
| рабочая копия (закрытые снимки есть) | `bash bin/food-baking test -rs` | 0 | 33 passed |
| чистая копия `git worktree add --detach … claude/template-food-baking-b` | `bash bin/food-baking test -rs` | 0 | 32 passed, 1 skipped |

Пропущенный в чистой копии тест — полная сверка текста черновиков с источником (`test_all_drafts_pass_validation`):
ему нужен сырой текст страниц `var/food-baking/private`, который не хранится в git (права, срок хранения), а заново
скачать его после заморозки знаний нельзя (CLOSED_WORLD). В чистой копии он **не выполнялся**; в рабочей копии — PASS.

## Перенос и PR (13.10.2026)

- `origin/main` с исправлением lint (PR #71, 304c3d6) влит в ветку обычным merge; `ruff check .` по репозиторию — чисто.
- PR #112 перенацелен с `claude/template-food-baking` на `main`: на старой базе был конфликт слияния, и GitHub не запускал CI для PR.
  Слияния нет, PR остаётся черновиком; вернуть прежнюю базу — `gh pr edit 112 --base claude/template-food-baking`.
- Комплект переноса — `bash bin/food-baking kit build --out <каталог>` (состав и команды — в его `INSTALL.md`).
  Проверен в изолированном каталоге без git (`food-baking-e26066a`): `sha256sum -c` — 0, тесты — 34 passed, 1 skipped in 1.43s,
  запуск на 8902 — `/healthz` за 0.25 с, главная 200 (`oven-bench`),
  26 URL и 3 ресурсов — 0 ошибок.
