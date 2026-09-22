# UNIFIED_RATINGS — финальный отчёт

```text
VERDICT=PASS_WITH_EXTERNAL_BLOCKER
MODULE=UNIFIED_RATINGS
BRANCH=claude/unified-ratings-1-10-sources-01
WORKTREE=/home/claude/wt-unified-ratings-1-10-sources-01
START_HEAD=ec29b2c7fa046c9b05537744191c0ade1b6b673e
FINAL_HEAD=<см. FINAL_REPORT.json: заполняется последним коммитом>
UPSTREAM=origin/claude/unified-ratings-1-10-sources-01
PUSH_PERFORMED=YES
FORCE_USED=NO
WORKTREE_CLEAN=YES
FOREIGN_FILES_TOUCHED=0
PRODUCTION_SITE_DEPLOYED=0
FRONTEND_SERVICES_RESTARTED=0
DNS_MUTATIONS=0
INDEXABILITY_MUTATIONS=0
PAID_EXTERNAL_API_CALLS=0
DB_BACKUP_CREATED=YES
MIGRATION_DRY_RUN=PASS
MIGRATION_APPLIED=PASS
ROLLBACK_REHEARSED=PASS
COMMUNITY_SCALE=1-10
EDITORIAL_SCALE=1-10
EXTERNAL_NORMALIZED_SCALE=1-10
COMMUNITY_CREATE_PASS=PASS
COMMUNITY_UPDATE_PASS=PASS
COMMUNITY_RETRACT_PASS=PASS
EDITORIAL_RBAC_PASS=PASS
AGGREGATE_REBUILD_PASS=PASS
ANILIST_STATUS=READY (557 записей)
SIMKL_STATUS=BLOCKED_SECRET (0 записей)
KITSU_STATUS=READY (447 записей)
SHIKIMORI_STATUS=READY (599 записей)
IMDB_STATUS=FEED_ONLY (2000 записей)
KINOPOISK_STATUS=FEED_ONLY (2000 записей)
PILOT_TITLES=60
SAMPLE_100_TITLES=600
EXACT_MATCHES=5603
PENDING_REVIEW=84
REJECTED_MATCHES=84
FALSE_AUTOMATIC_MATCHES=0
SOURCE_RECORDS_INSERTED=5603
SOURCE_RECORDS_UPDATED=2
SOURCE_RECORDS_UNCHANGED=398
SOURCE_RECORDS_FAILED=1
INGESTION_ENABLED=YES
SCHEDULER_ENABLED=YES
TESTS_PASSED=254
TESTS_FAILED=0
DOUBLE_RUN_MATCH=YES
FAKE_USER_VOTES_INSERTED=0
SYNTHETIC_VOTES_REMAINING=0
TEST_TELEMETRY_IN_PRODUCTION=0
READY_FOR_WIDGET_INTEGRATION=YES (схема и API готовы; публичная раскатка — отдельный этап)
READY_FOR_ADDITIONAL_TENANTS=YES (площадка добавляется строкой в unified_title_tenant_map)
NEXT_SAFE_STEP=получить secret_ref simkl_client_id, повторить Этап A для Simkl; расширять инкрементальный сбор по расписанию
```

`SOURCE_RECORDS_FAILED=1` — один прогон Kitsu на выборке-100 до миграции
0008, когда «источник не знает тайтл» ещё считалось отказом. После 0008
тот же прогон даёт `not_found=1, failed=0`. Строка оставлена как есть:
переписывать журнал задним числом нельзя.

---

## 1. Схема трёх видов оценок

| Вид | Таблицы | Шкала | Кто пишет |
| --- | --- | --- | --- |
| Внешняя | `unified_external_snapshots` (append-only), `unified_external_current` | исходная шкала источника → 1.0–10.0 | адаптер источника |
| Пользовательская | `community_votes`, `community_vote_events` (существующий ledger) + `unified_user_aggregates` | целое 1–10 | `CommunityRatings` поверх `CommunityVotesService` |
| Редакционная | `unified_editorial_ratings`, `unified_editorial_audit` | целое 1–10 | `EditorialRatings`, только по RBAC |

Общей таблицы оценок нет. Раздельность обеспечена схемой, а не
соглашением: «редакционная оценка попала в пользовательский агрегат» —
не ошибка, которую нужно ловить проверкой, а состояние, которого в этой
схеме не существует. Проверяется тестами
`test_editorial_score_never_enters_the_vote_ledger` и
`test_editorial_score_is_labelled_as_ours`.

## 2. Таблицы и миграции

**Миграция 0007** (expand-only, 12 таблиц):
`unified_titles`, `unified_title_tenant_map`, `unified_source_links`,
`unified_external_snapshots`, `unified_external_current`,
`unified_editorial_ratings`, `unified_editorial_audit`,
`unified_user_aggregates`, `unified_import_runs`, `unified_review_queue`,
`unified_schedule_state`, `unified_metrics`.

**Миграция 0008**: `unified_import_runs.not_found` — отделяет «источник не
знает тайтл» от отказа источника.

Ни одна существующая таблица не изменена и не удалена. Проверено на
побайтовой копии боевой базы: таблиц было 37, стало 49, удалено 0,
количество строк в таблицах работающего виджета не изменилось
(`02-db/MIGRATION_APPLIED.json`), и те же запросы старого gateway
возвращают те же строки (`test_existing_canary_queries_still_work_after_the_migration`).

## 3. Формулы нормализации

| Исходная шкала | Формула | Проверено на |
| --- | --- | --- |
| 0–10 | `normalized = raw` | Shikimori 7.38 → 7.4 |
| 0–100 | `normalized = raw / 10` | AniList 70 → 7.0; Kitsu «73.15» → 7.3 |
| 0–5 | `normalized = raw * 2` | покрыто тестами |

Формула берётся из контракта конкретного источника. Одновременно
хранятся исходное значение, исходная шкала, нормализованное значение и
идентификатор формулы.

Состояния значения различаются: `OK`, `ABSENT`, `ZERO_NOT_A_RATING`,
`OUT_OF_RANGE_LOW`, `OUT_OF_RANGE_HIGH`, `INVALID_TYPE`,
`CONTRACT_UNVERIFIED`, `UNMEASURED`. Ни одно не превращается в ноль.

## 4. Статус каждого источника

| Источник | Способ | Статус | Записей | Примечание |
| --- | --- | --- | --- | --- |
| AniList | официальный публичный GraphQL, без ключа | READY | 557 | лимит объявлен сервером (30/мин), наш cap 20/мин |
| Kitsu | официальный публичный JSON:API, без ключа | READY | 447 | лимит не объявлен, cap 20/мин; `userCount` ≠ голоса |
| Shikimori | уже разрешённый коннектор проекта | READY | 599 | новый клиент не создавался |
| Simkl | официальный API, требует `client_id` | **BLOCKED_SECRET** | 0 | `HTTP 412 client_id_failed`; ключа нет |
| IMDb | договорный фид поставщика | FEED_ONLY | 2000 | прямой сбор не запускался, 0 сетевых запросов |
| Кинопоиск | договорный фид поставщика | FEED_ONLY | 2000 | прямой сбор не запускался, 0 сетевых запросов |

Simkl: адаптер написан целиком и отказывает **до** сетевого запроса.
Контракт шкалы помечен непроверенным, поэтому нормализация вернула бы
`CONTRACT_UNVERIFIED`, а не число. Разблокировка — одно внешнее
действие: выдать `secret_ref simkl_client_id`.

## 5–6. Примеры и таблица исходных/нормализованных оценок

«Уж не зомби ли это?» (2011), `nova:019f8ec2-a72b-708d-8dd4-c1dcb0bef8bd`:

| Источник | Исходное | Исходная шкала | Формула | Нормализовано | Голоса |
| --- | --- | --- | --- | --- | --- |
| Наша оценка | — | — | — | — (не поставлена) | — |
| Оценка зрителей | — | — | — | — (агрегат не рассчитывался) | — |
| AniList | 69 | 0–100 | `raw / 10` | 6.9 | 51 884 |
| Simkl | — | — | — | — (SOURCE_BLOCKED) | — |
| Kitsu | 74.07 | 0–100 | `raw / 10` | 7.4 | 23 217 |
| Shikimori | 7.32 | 0–10 | `raw` | 7.3 | 19 201 |
| IMDb | 6.9 | 0–10 | `raw` | 6.9 | нет в фиде |
| Кинопоиск | 6.641 | 0–10 | `raw` | 6.6 | нет в фиде |

Ещё семь тайтлов с той же структурой — `06-ingest/EXAMPLES.json`
(«Альдноа.Зеро», «Мир по-прежнему красив», «Пожиратель душ: Класс НОТ»,
«С места на место», «Санка Рэа», «У меня мало друзей», «Юный лорд —
мастер побега»).

Видно то, ради чего источники держат раздельно: у «С места на место»
AniList даёт 7.2, а IMDb — 6.6. Среднее по ним не измеряет ничего.

## 7. Результаты сопоставления

| | |
| --- | --- |
| Точных связей (`exact`) | 5603 |
| В очереди проверки (`pending` + `conflict`) | 84 |
| Ложных автоматических сопоставлений | **0** |

Все 5603 связи получены по точному внешнему идентификатору, подтверждённому
обеими сторонами: мы спрашиваем по MAL ID, источник возвращает свой
crosswalk (`idMal` у AniList, `malId` у Shikimori, `/mappings` у Kitsu), и
связь принимается только когда идентификаторы совпали и факты не
разошлись. Ни одна связь не сделана по похожему названию.

## 8. Review queue

| Причина | Записей |
| --- | --- |
| `YEAR_MISMATCH` | 50 |
| `SPECIAL_OVA_VS_MAIN` | 30 |
| `MOVIE_VS_SERIES` | 4 |
| **Всего** | **84** |

Полный список — `06-ingest/REVIEW_QUEUE.json`. Автоматически не
публикуются: строка источника получает состояние `PENDING_REVIEW`, а не
значение.

## 9. Фактический объём записанных данных

| | |
| --- | --- |
| Канонических тайтлов | 53 596 |
| Снимков внешних оценок вставлено | 5603 |
| Обновлено | 2 |
| Unchanged (новой версии не создано) | 398 |
| Отказов источника | 1 (до миграции 0008 — см. выше) |
| Тайтлов в расписании | 1603 |

## 10. Расписание обновлений

| Тир | Интервал | Тайтлов |
| --- | --- | --- |
| ONGOING | 24 ч (12–72) | 0 |
| RECENT_FINISHED | 7 дней (2–21) | 2 |
| ARCHIVE | 30 дней (14–90) | 1601 |
| RETRY | 6 ч, не более 5 отказов подряд | — |

Каждый источник идёт по своей очереди. Одновременного полного обхода
нет (`concurrent_full_sweep: false`). Неизменившееся значение отодвигает
проверку, изменившееся приближает, отказ отодвигает сильнее;
подстройка не выходит за границы тира.

## 11. Результаты тестов

| | Прогон 1 | Прогон 2 |
| --- | --- | --- |
| Пройдено | 254 | 254 |
| Провалено | 0 | 0 |

`DOUBLE_RUN_MATCH=YES`. Именованные ворота проверены отдельными
запусками конкретных тестов, а не выведены из общей суммы:
`COMMUNITY_CREATE_PASS`, `COMMUNITY_UPDATE_PASS`,
`COMMUNITY_RETRACT_PASS`, `EDITORIAL_RBAC_PASS`,
`AGGREGATE_REBUILD_PASS` — все PASS (`05-tests/TEST_RUNS.json`).

Тесты нашли три настоящих дефекта, а не подтвердили уже верное:
контрольная сумма агрегата не защищала собственную строку; пересчёт
агрегата читал ledger вне транзакции записи и терял голоса при
конкурентной записи; карантин срабатывал на каждом втором спецвыпуске
из-за разной детализации типов у нас и у источников. Четвёртый дефект
нашёл живой пилот: проверка внешнего идентификатора сравнивала наш ID
сам с собой.

## 12. Подтверждение отсутствия синтетических голосов

```text
FAKE_USER_VOTES_INSERTED=0
SYNTHETIC_VOTES_REMAINING=0
TEST_TELEMETRY_IN_PRODUCTION=0
```

В боевой базе `community_votes` = 0 строк. Тестовых тайтлов из фикстур
(`nova:t-00*`) — 0, редакционных оценок — 0, пользовательских агрегатов
— 0. Тесты работают на временных базах: путь передаётся явно, а
`test_store_never_silently_targets_production` проверяет, что значение
по умолчанию в тестах не используется.

## 13. Коммиты

| Коммит | Что |
| --- | --- |
| `6c480d0` | изоляция и preflight |
| `079c262` | схема и миграция 0007 |
| `d60512d` | внешние источники: контракты, адаптеры, сопоставление, конвейер |
| `6ea4d1f` | API пользовательских оценок |
| `ac07b92` | редакционная оценка с RBAC и audit |
| `c1f8611` | отображение по источникам и сортировочный показатель |
| `5570482` | адаптивное расписание |
| `5e15bc2` | CLI по ступеням |
| `3c6d79b` | тесты |
| `a4c1edc` | подтверждение crosswalk источником, миграция 0008, пакетная запись |
| `42ed192` | документация |

## 14. Пути к evidence

`artifacts/evidence/unified-ratings-01/` — состав описан в `README.md`
этого каталога.

## 15. Ограничения и оставшиеся внешние гейты

1. **Simkl BLOCKED_SECRET.** Нужен `secret_ref simkl_client_id`. После
   выдачи — повторный Этап A (подтвердить контракт шкалы живым ответом),
   затем пилот. Обход не выполнялся и не будет.
2. **Проверка фактов для Shikimori слабее.** Разрешённый коннектор не
   отдаёт год, тип и число эпизодов, поэтому для Shikimori связь
   проверяется только crosswalk-идентификатором; расхождения по году и
   типу для этого источника — `UNMEASURED`, а не «проверено и сошлось».
   Это видно в числах: на выборке-100 AniList дал 10 карантинов,
   Kitsu — 8, Shikimori — 1.
3. **Оценка зрителей нигде не рассчитана**, потому что голосов нет: в
   боевом ledger 0 строк. Агрегат появится с первым настоящим голосом.
4. **Покрытие внешними оценками частичное**: собрано ~1600 тайтлов из
   7033 с MAL ID. Дальше — по расписанию, инкрементально.
5. **Виджет не раскатывался.** Подготовленный 1% Yummy-canary не изменён:
   флаги раскатки и таблицы, которые читает gateway, совпадают с
   состоянием до этапа (`06-ingest/CANARY_INTACT.json`). 24-часовое окно
   наблюдения не начиналось и начаться не могло — live-deploy виджета не
   выполнялся.
6. **Сбор внешних оценок ≠ готовность к публикации.** Ни одно собранное
   значение не показано пользователям. Публичное отображение требует
   отдельной проверки и отдельного решения.
