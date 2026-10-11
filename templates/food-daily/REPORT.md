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
