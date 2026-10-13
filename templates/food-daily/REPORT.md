# TEMPLATE-FOOD-DAILY-01 — отчёт о передаче

Дата: 11.10.2026. Сервер `claude-control-01`, пользователь `claude`.

| | |
| --- | --- |
| ветка | `claude/template-food-daily` |
| worktree | `/home/claude/wt-template-food-daily` |
| base | `a7f7cb6` (`origin/main`) |
| проверенный commit | `576a232` (код сайта), отчёт и свидетельства — следующим коммитом |
| preview | **http://127.0.0.1:8847/** — закрытый: только петля сервера, `noindex` везде, редактор за паролем. Снаружи недоступен; смотреть через SSH-туннель на порт 8847 |
| артефакт | `var/food-daily/build/576a23255f1e80cb3e0187d2362933ae97aace24/` (61 файл, tree sha256 `67629248…`; повторная сборка того же commit даёт тот же хеш — проверено на `361ae67`) |
| скриншоты | `docs/screenshots/576a232/{home,catalog,recipe}-{mobile,desktop}.png` |

## Фактические количества

| этап | число | примечание |
| --- | ---: | --- |
| URL найдено (10 русскоязычных референсов) | 716 195 | уникальных после нормализации; из них классифицировано как рецепты 403 331 |
| источников с `complete` по картам сайта | 4 из 10 | остальные `partial` с причинами (`docs/audit/competitor-counts.csv`) |
| страниц рецептов получено для пилота | 231 | eda.rambler.ru 151, gastronom 40, 1000.menu 40; все HTTP 200 |
| записей извлечено (найдена разметка рецепта) | 231 | JSON-LD или микроразметка |
| полных записей (название, порции, ≥2 ингредиента с количествами, ≥2 шага) | 145 | все — Еда; у gastronom в JSON-LD нет количеств, у 1000.menu в микроразметке нет шагов |
| тем после дедупликации | 153 | 134 — food-daily, 12 — food-baking, 5 — food-appliances, 2 — food-weekly |
| черновиков **Qwen** | **0** | живого канала к Qwen нет |
| черновиков по заданиям Qwen, написанных сессией Claude (`manual_standin`) | 24 | прошли все проверки импорта; это не Qwen |
| рецептов в preview | 22 | 6 разделов; 2 заблокированы воротами (ошибки единиц в источнике) |
| проверено редактором (человеком) | 0 | |
| приготовлено редакцией | 0 | |
| опубликовано (production) | 0 | |

Видео — состояния не смешиваются:

| сценариев | сгенерированных сцен | готовых файлов | одобренных роликов |
| ---: | ---: | ---: | ---: |
| 3 (сырники, оладьи, плов; 120–126 с) | 0 | 0 | 0 |

Генератор не подключён, бюджет 0: задания в `queued`, `video dispatch` отказывает с `BLOCKED_INPUT`.

## Проверки (команда → exit code → артефакт)

| проверка | команда | exit | результат |
| --- | --- | :-: | --- |
| тесты шаблона | `bash templates/food-daily/bin/food-daily test` | 0 | 103 passed (`var/food-daily/logs/test-run.log`) |
| браузерная приёмка | `python3 -m fooddaily.qa_browser --shots docs/screenshots/576a232 --out docs/verification/browser-qa.json` | 0 | все сценарии true: порции 190 г → 380 г, время не меняется; список покупок; избранное; режим готовки с ←/→/Esc; фильтры, сброс, пустой результат; поиск с ё/регистром/пробелами; рецепт без JS; первый Tab — «К содержимому»; без горизонтальной прокрутки на 390 и 1440 px; правила доступности и контраста — 0 замечаний; ошибок консоли 0 |
| производительность (лабораторно, не полевые данные) | там же | 0 | LCP 68–232 мс, CLS 0, HTML+ресурсы ≤ 49 КБ |
| HTTP-смоук 33 маршрутов | `docs/verification/http-smoke-576a232.txt` | 0 | `X-Robots-Tag: noindex, nofollow` на всех ответах, 404 для несуществующих, заблокированный рецепт 404, редактор 401 без пароля, path traversal 404 |
| редактор | ручной сценарий по HTTP | — | 401 без пароля и с неверным, 403 при чужом CSRF, отказ машинному рецензенту |
| цикл версий на реальном материале | `docs/verification/version-cycle-20261011.txt` | 0 | v2 → конфликт по устаревшей базе (в журнале) → откат v3 = v1 |
| повтор задания | `qwen export`/`import` повторно | 0 | тот же `job_id`; повторный импорт — 24 noop |
| реестры фабрики | `python3 scripts/validate_registries.py` | 0 | |
| unit-тесты фабрики по затронутым областям | `pytest tests/unit -k "allowlist or network or permission or inventory or registr or unattended or guard or authorization"` | 0 | 650 passed |
| полный `tests/unit` фабрики | `pytest -q tests/unit` | 1 | 2521 passed, 5 skipped, **1 failed**: `test_job_result.py::test_real_pilot_results_are_schema_valid` — требует `artifacts/jobs/pilot-local/*.json`, которые создаёт прогон DLE-пилота `tests/run-all.sh`; в свежем worktree их нет, пилот не запускался. С изменениями food-daily не связано, но и не исправлено |
| сканер секретов | `python3 scripts/secret_scan.py` | 0 | находок вне tests/ нет |

Не запускалось: axe-core (в worktree `node_modules` — висячая ссылка; вместо него
собственные правила доступности и контраста); `tests/run-all.sh` фабрики
целиком (DLE-контур к шаблону не относится); полевые Core Web Vitals (нет домена и трафика).

## Готовность первого сайта

| этап | вес | готово | основание |
| --- | ---: | ---: | --- |
| шаблон, сетки, маршруты, функции читателя | 25 | 25 | все обязательные страницы и функции работают, E2E зелёные |
| техническое SEO | 15 | 13 | матрица и тесты; −2: нет `image` в Recipe (нет своих фото), не проверено в Вебмастере (нет домена) |
| контент пилота (≥20 полных рецептов) | 15 | 12 | 22 в preview; −3: тексты не от Qwen и не проверены редактором |
| импорт и редакционный контур | 15 | 13 | версии, конфликт, откат, ворота; −2: живой Qwen не подключён |
| изоляция и сборка | 10 | 10 | тесты изоляции, сборка из `git archive`, граница diff |
| видео | 10 | 3 | сценарии и адаптер есть, роликов нет |
| выкладка | 10 | 3 | закрытый preview на петле; удалённого стенда нет |
| **итого** | 100 | **79 %** | готовность **закрытого preview**. До production — ещё права на контент (BLOCKED_RIGHTS), домен (BLOCKED_INPUT), редакторская проверка, авторизация в manifest |

Сайтов сети: planned — 9, preview — 1, production — 0.

## Команды

Продолжение сбора (checkpoint, лимиты из `config/crawl.yaml`):

```bash
bash templates/food-daily/bin/food-daily catalog --host iamcook --max-pages 5000 --max-seconds 5400
bash templates/food-daily/bin/food-daily counts --export
bash templates/food-daily/bin/food-daily import plan --hosts eda-rambler --topics 134 && bash templates/food-daily/bin/food-daily import run --limit 50
```

Только этот preview: `bash templates/food-daily/bin/food-daily start | stop | status | restart`.

Откат: материала — `food-daily editorial rollback <content_id> --to <версия>` →
`editorial snapshot` → `restart`; снятие — `editorial unpublish <content_id>`;
всего сайта — `food-daily stop` (данные в `var/food-daily` не удаляются);
кода — `git revert` коммитов ветки.

## Что заблокировано и почему

| что | статус | что нужно |
| --- | --- | --- |
| production | BLOCKED_RIGHTS + BLOCKED_INPUT | юридическая оценка режима «факты + свой текст + ссылка» (FD-02); домен; `production_authorized` |
| Qwen | нет канала | инструменты моста для outbox/inbox food-daily (handoff в `docs/INTEGRATIONS.md`) |
| seo-engine | BLOCKED_ACCESS | scoped-учётка tenant `food-daily` |
| видео | BLOCKED_INPUT | провайдер генерации и синтеза речи, лимит расходов |
| D128 в `knowledge/DECISIONS.md` | через `/research-freeze` | правка ломает `KNOWLEDGE_FREEZE` (FD-13) |
| russianfood.com | 403 после обхода | повтор позже с меньшей частотой |

## Следующие задачи

1. **Редакторская проверка 22 рецептов человеком** и решение по двум заблокированным (бульон 400 л, сливки 100 стаканов) — через `/redaktor/`.
2. **Канал Qwen**: инструменты моста `food_daily_jobs`/`food_daily_submit`, затем прогон 24 заданий настоящим Qwen и сравнение с `manual_standin`.
3. **Права на контент и домен**: оценка FD-02, выбор домена, `origin.production`, Вебмастер; без этого production не начинается.
4. **Собственные фото/иллюстрации блюд** вместо одной иллюстрации на раздел (сейчас все карточки раздела одинаковы) — это же снимет ограничение `image` в Recipe.
5. **Следующий шаблон** — TEMPLATE-FOOD-BAKING-01 или FOOD-WEEKLY-01 по ТЗ в `docs/NETWORK-PLAN.md`, в своей ветке и worktree от `origin/main`.

---

## Дополнение 12.10.2026 (PRACTICAL-NETWORK-NIGHT-CONTINUE-02)

Проверенный код: `59972fa`. Артефакт: `var/food-daily/build/59972fa20092390ea3673e6b15c8f391c89c1fb2/` (67 файлов).
Скриншоты: `docs/screenshots/59972fa/{home,catalog,recipe,tag,article}-{mobile,desktop}.png`.

Исправлено:
1. Иллюстрация раздела больше не выдаётся за блюдо: карточки и шапка рецепта без медиа, карточка показывает раздел, название, первую фразу, главные продукты, время, порции.
2. Теги на рецепте — ссылки только на живые страницы; индексы `/produkty/`, `/sposob/`.
3. Новый тип страницы «совет» (3 материала, выведенных из данных рецептов) с Article-разметкой.
4. ItemList на разделах, тегах, подборках; печатная версия рецепта.
5. axe-core 4.13.0 установлен в `templates/food-daily/qa/` со своим lockfile; прогон по 15 страницам × 2 экрана — 0 нарушений после исправления контраста «404». Проход клавиатурой: главная и рецепт, 30 шагов фокуса, ловушек нет; поле поиска показывает фокус обводкой формы (`:focus-within`).
6. Линт шаблона: 0 замечаний (`templates/food-daily/ruff.toml`); первоначальный FAIL линта в CI PR #95 был моим — исправлен.

| проверка | команда | exit | результат |
| --- | --- | :-: | --- |
| тесты шаблона | `bash templates/food-daily/bin/food-daily test` | 0 | 113 passed |
| ruff | `python3 -m ruff check templates/food-daily && python3 -m ruff format --check templates/food-daily` | 0 | 0 замечаний |
| браузер + axe + клавиатура | `python3 -m fooddaily.qa_browser --shots docs/screenshots/59972fa` | 0 | все сценарии true, axe 0, консоль 0 |
| CI PR | GitHub Actions `verify.sh` | FAIL ожидается | 20 замечаний ruff в общих `tests/unit` есть на `main` (CI `main` красный с 04.09) — `docs/HANDOFF-CI.md` |

Готовность закрытого preview по чек-листу (12 пунктов: главная, каталог, разделы, теги, рецепт, советы, поиск, фильтры, избранное/покупки/режим готовки, SEO-матрица и тесты, доступность, изоляция и сборка из commit) — **12 из 12**.
Техническая готовность к production — **нет**: внешние условия — домен (BLOCKED_INPUT), права на контент (BLOCKED_RIGHTS), проверка редактором (0 из 22), CI-гейт (FAIL по общему линту), изображения блюд (нет; Recipe без `image` не годится для расширенного результата).
Статус: **READY_FOR_REVIEW_WITH_BLOCKERS**.
Qwen: ночной прогон не подтверждён (ветки и файлов нет), реальных Qwen-результатов 0.

## Обновление на d05068d (ночь 12–13.10, после вариантов B и C)

Добавлены метатеги варианта `classic-cards` (тест) и исправлена обрезанная подсказка на 404 (FD-14). Перезапущено на d05068d:
`python3 -m fooddaily.qa_browser --shots docs/screenshots/d05068d --out docs/verification/browser-qa.json` → exit 0, 26 сценариев
без провалов, axe 4.13.0 — 0 нарушений, 10 скриншотов; `python3 qa/viewports.py 8847 /poisk/?q=тыква /nesushchestvuet/` → exit 0,
53 URL × 4 ширины — 0 замечаний (`docs/verification/viewports-d05068d.json`); `bin/food-daily test` → 116 passed.

## Обновление на 2bd36b8

Зарезервировано место под переключатель порций и кнопки рецепта (их показывает JS) — сдвиг макета на странице рецепта убран
(лабораторный CLS по прогону — 0). Перезапущено: `python3 -m fooddaily.qa_browser --shots docs/screenshots/2bd36b8 --out docs/verification/browser-qa.json`
→ exit 0, 26 сценариев без провалов, axe 0; `python3 qa/viewports.py 8847 …` → 53 URL × 4 ширины, 0 замечаний
(`docs/verification/viewports-2bd36b8.json`); `bin/food-daily test` → 116 passed.

## Обновление на e69bf15 (13.10.2026): редактор

Найдено проверкой редактора в браузере (раньше редактор проверялся только по HTTP: 401/403): на 390 px таблица
давала горизонтальный скролл, `<pre>` не был доступен с клавиатуры, поля diff и выбор решения были без подписей (axe: label, select-name, scrollable-region-focusable). Исправлено так же, как в B/C.

| команда | exit | результат |
| --- | --- | --- |
| `bash bin/food-daily test` | 0 | 118 passed |
| `ruff check . && ruff format --check .` | 0 | чисто |
| `python3 -m fooddaily.qa_browser --shots docs/screenshots/e69bf15 --out docs/verification/browser-qa.json` | 0 | 26 сценариев PASS, axe 0 |
| `python3 qa/viewports.py 8847 /poisk/?q=тыква /nesushchestvuet/ > docs/verification/viewports-e69bf15.json` | 0 | 53 URL × 4 ширины, 0 замечаний |
| `bash bin/food-daily build --commit HEAD` | 0 | собрано из e69bf15 |
| приёмка редактора (scratchpad `ed_qa.py`) | 0 | 26 проверок PASS — `docs/verification/editor.json` |

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
| редактор: строк в списке столько же, сколько материалов в БД (24) | PASS | `list_rows_match_db` |
| редактор: публичная страница выбранного рецепта — 200 | PASS | `public_page_200_before` |
| редактор: параметр msg экранируется (<script> не исполняется) | PASS | `msg_param_escaped` |
| редактор: POST без CSRF-токена — 403 | PASS | `post_without_csrf_403` |
| редактор: POST без входа — 401 | PASS | `post_without_auth_401` |
| редактор: после отклонённых POST страница не изменилась (200) | PASS | `public_page_200_after_refused_posts` |
| редактор: ссылка из списка открывает материал | PASS | `list_link_opens_item` |
| редактор: «Снять» → сообщение «снято с preview» | PASS | `unpublish_msg` |
| редактор: статус публикации стал hidden | PASS | `unpublish_status_hidden` |
| редактор: публичная страница после снятия — 404 | PASS | `public_page_404_after_unpublish` |
| редактор: снимок сайта изменился только у этого материала | PASS | `snapshot_only_target_removed` |
| редактор: «В preview» → страница снова 200 | PASS | `republish_restores_public_page` |
| редактор: откат к v1 создаёт новую версию, а не стирает историю | PASS | `rollback_creates_new_version` |
| редактор: diff между версиями показан | PASS | `diff_shown` |
| редактор: решение редактора записано (статус editor_rejected на копии) | PASS | `review_recorded` |
| редактор: журнал содержит действия editor:<имя> | PASS | `audit_log_has_editor_actions` |
| редактор: нет горизонтального скролла на 390 и 1440 px | PASS | `no_hscroll_editor_pages` |
| редактор: axe-core 4.13.0 — 0 нарушений | PASS | `axe_zero_editor_pages` |
| редактор: нет ошибок консоли | PASS | `no_console_errors` |
