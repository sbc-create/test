# food-baking — отчёт (12.10.2026)

| | |
| --- | --- |
| сайт | «Тесто и десерты» (рабочее название) |
| ветка / worktree | `claude/template-food-baking` / `/home/claude/wt-template-food-baking` |
| база | `a7f7cb6` = origin/main (не food-daily) |
| проверенный код | `cd39fdc` |
| preview | `http://127.0.0.1:8848/` — только петля сервера `claude-control-01`, доступ — SSH-туннель на порт 8848; `noindex` везде |
| артефакт | `var/food-baking/build/cd39fdcf8aff79e229d17f32d68075930378a29b/` (31 файл) |
| скриншоты | `docs/screenshots/cd39fdc/{home,catalog,recipe,dough,pitfalls}-{mobile,desktop}.png` |

## Объёмы

| что | число |
| --- | ---: |
| URL выпечки в картах Еды | 14 489 |
| страниц получено | 24 (+28 запросов аудита) |
| записей с разметкой рецепта | 24 |
| полных записей | 17 |
| рецептов в preview | 13 (кексы, хлеб, пироги, печенье, заварное, без выпечки) |
| черновиков Qwen | 0 |
| черновиков сессии Claude (`manual_standin`) | 13 |
| проверено редактором / испечено | 0 / 0 |
| production | 0 |

## Проверки

| проверка | команда | exit | результат |
| --- | --- | :-: | --- |
| тесты | `bash templates/food-baking/bin/food-baking test` | 0 | 20 passed |
| ruff | `python3 -m ruff check templates/food-baking && python3 -m ruff format --check templates/food-baking` | 0 | 0 замечаний |
| браузер + axe 4.13.0 | `python3 -m bakebook.qa --shots docs/screenshots/cd39fdc` | 0 | все сценарии true; axe — 0 нарушений на 13 страницах × 2 экрана; «ошибки консоли» — только ответ 404 намеренной страницы `/nesushchestvuet/` |
| редактор | `python3 var/food-baking/editor_check.py` | 0 | 401 / 401 / 200 |
| сканер секретов | `python3 scripts/secret_scan.py` | 0 | находок нет |
| CI | GitHub Actions | ожидается FAIL | общий линт `tests/unit` на main (см. handoff food-daily `docs/HANDOFF-CI.md`) |

Сценарии: таймер из времени источника (80 мин, отсчёт идёт), отметка «отвешено»,
фильтр по виду теста и пустой результат, поиск без учёта регистра и окончаний,
рецепт и предупреждения без JS, первый Tab — «К тексту», без горизонтальной прокрутки.

## Готовность

Закрытый preview по чек-листу (главная, каталог, рецепт, вид теста, разбор ошибок,
тег, поиск, 404, редактор, SEO-матрица и тесты, доступность, изоляция и сборка из
commit): **12 из 12**. Production — нет: домен (BLOCKED_INPUT), права (BLOCKED_RIGHTS),
редакторская проверка (0 из 13), фото (Recipe без image), CI-гейт.
Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**.

## Ограничения

* только 2 вида теста набирают ≥2 рецептов (кексовое, заварное) — у дрожжевого и
  без выпечки по 1 рецепту, страниц нет; следующая партия импорта должна их добрать;
* в 6 из 13 рецептов источник противоречив (масло 90/80 г, соль, виноград вне
  списка) — записано в `editor_notes`, в тексте не исправлено.

## Обновление b758e94

Подсказка поиска сокращена (FB-09). `python3 qa/viewports.py 8848 /poisk/?q=печенье /nesushchestvuet/` → exit 0, 27 URL × 4 ширины — 0 замечаний (`docs/verification-viewports.json`). `bin/food-baking test` → 20 passed. Браузерная приёмка не перезапускалась: изменён только текст подсказки.

## Обновление на 79bf0b8 (ночь 12–13.10, после вариантов B и C)

Изменения: метатеги варианта `book-spread` (тест), подсказка поиска (FB-09). Перезапущено на 79bf0b8: `python3 -m bakebook.qa --shots docs/screenshots/79bf0b8 --out docs/verification-browser-qa.json` → exit 0, 21 сценарий без провалов, axe 4.13.0 — 0 нарушений, 10 скриншотов;
`python3 qa/viewports.py 8848 /poisk/?q=печенье /nesushchestvuet/` → exit 0, 27 URL × 4 ширины — 0 замечаний (`docs/verification-viewports.json`); `bin/food-baking test` → 21 passed.

## Обновление на 21d30ce (13.10.2026): редактор

Найдено проверкой редактора в браузере (раньше редактор проверялся только по HTTP: 401/403): на 390 px таблица
давала горизонтальный скролл. Исправлено так же, как в B/C.

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/food-baking test` | 0 | 21 passed |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m bakebook.qa --shots docs/screenshots/21d30ce --out docs/verification-browser-qa.json` | 0 | 21 сценарий PASS, axe 0 |
| `python3 qa/viewports.py 8848 /poisk/?q=печенье /nesushchestvuet/ > docs/verification-viewports.json` | 0 | 27 URL × 4 ширины, 0 замечаний |
| `bash bin/food-baking build --commit HEAD` | 0 | собрано из 21d30ce |
| приёмка редактора (scratchpad `ed_qa.py`) | 0 | 14 проверок PASS — `docs/verification-editor.json` |

Проверки редактора:

| действие | результат | ключ |
| --- | --- | --- |
| редактор: без входа — 401 и запрос Basic Auth | PASS | `no_auth_401_with_challenge` |
| редактор: неверный пароль — 401 | PASS | `wrong_password_401` |
| редактор: чужое имя с верным паролем — 401 | PASS | `wrong_user_401` |
| редактор: верные данные — 200 | PASS | `login_200` |
| редактор: страница редактора — noindex | PASS | `editor_noindex` |
| редактор: robots закрывает /redaktor/ (в preview — «Disallow: /») | PASS | `robots_disallow_redaktor` |
| редактор: в sitemap нет /redaktor/ | PASS | `sitemap_has_no_redaktor` |
| редактор: строк в таблице столько же, сколько рецептов в content.json | PASS | `list_rows_match_content` |
| редактор: история версий совпадает с history.jsonl | PASS | `history_rows_match_file` |
| редактор: POST не принимается (501): редактор только читает | PASS | `post_not_accepted` |
| редактор: на странице нет форм изменения | PASS | `read_only_no_forms` |
| редактор: нет горизонтального скролла на 390 и 1440 px | PASS | `no_hscroll_editor_pages` |
| редактор: axe-core 4.13.0 — 0 нарушений | PASS | `axe_zero_editor_pages` |
| редактор: нет ошибок консоли | PASS | `no_console_errors` |
