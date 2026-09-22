# UNIFIED_RATINGS — этап 2: покрытие, полный сбор, канарейка animedia.icu

```text
VERDICT=BLOCKED_CONCURRENT_DEPLOYMENT
MODULE=UNIFIED_RATINGS
AUTHORIZED_DOMAIN=animedia.icu
SOURCE_BRANCH=claude/unified-ratings-1-10-sources-01
SOURCE_COMMIT=<FINAL_HEAD, см. STAGE2_FINAL_REPORT.json>
ADAPTER_BRANCH=claude/animedia-ratings-canary-01
ADAPTER_COMMIT=c26404668d7f9af912ec63a57caaf85b2b76bd7e
ARTIFACT_SHA256=cd92db74d79d2b15e8f6b460a07bcdaec9ec1db9699ddae19b556770496b4240
BUILD_ID=NOT_BUILT — сборка animedia-frontend.py перезаписала бы живой релиз чужой сессии
SERVICE=nova-animedia-01.service
PID_BEFORE=279780
PID_AFTER=279780 (не перезапускался)
ROLLBACK_TARGET=/srv/lords/.frontend/releases/20260921T214937Z-fac5643-animedia-parity

CATALOG_TITLES_TOTAL=53596
CATALOG_TITLES_ATTEMPTED=53596
CATALOG_TITLES_COMPLETED=51182
TITLES_WITH_ANY_EXTERNAL_RATING=33687
TITLES_WITH_2PLUS_EXTERNAL_RATINGS=24737
TITLES_WITHOUT_RATINGS=19909
CATALOG_COVERAGE_PERCENT=62.85

ANIMEDIA_ICU_TITLES_TOTAL=7425
ANIMEDIA_ICU_TITLES_WITH_RATING=6860
ANIMEDIA_ICU_COVERAGE_PERCENT=92.39
ANIMEDIA_ICU_TITLES_WITH_2PLUS=5637

ANILIST_TITLES=5484
SIMKL_TITLES=0
SHIKIMORI_TITLES=6760
KITSU_TITLES=4833
IMDB_TITLES=26807
KINOPOISK_TITLES=19543

EXACT_MATCHES=51182
PENDING_REVIEW=2440
FALSE_AUTOMATIC_MATCHES=0
SOURCE_RECORDS_FAILED=25

COMMUNITY_SCALE=1-10
OWNER_TEST_ACCESS_ONLY=YES
PUBLIC_RATINGS_READ=READY (флаг подготовлен, файл не размещён)
PUBLIC_RATINGS_WRITE=NO
PUBLIC_WRITE_ROLLOUT_PERCENT=0
KILL_SWITCH_READY=YES

BACKUP_CREATED=YES
RESTORE_PASS=YES
MIGRATION_DRY_RUN=PASS
ROLLBACK_REHEARSAL=PASS
TEST_RUN_1=334 passed / 0 failed
TEST_RUN_2=334 passed / 0 failed
ADAPTER_TEST_RUN_1=18 passed / 0 failed
ADAPTER_TEST_RUN_2=18 passed / 0 failed
DOUBLE_RUN_MATCH=YES

CROSS_TENANT_READS=0
CROSS_TENANT_WRITES=0
FAKE_USER_VOTES_INSERTED=0
COMMENTS_MUTATIONS=0
SEO_MUTATIONS=0
DNS_MUTATIONS=0
TLS_MUTATIONS=0
INDEXABILITY_MUTATIONS=0
SECOND_DOMAIN_MUTATIONS=0

INDEXABILITY_BEFORE=noindex,nofollow на / /catalog/ /title/ /episode/ и 404
INDEXABILITY_AFTER=идентично (ничего не менялось)
CANONICAL_UNCHANGED=YES

IMDB_TOTAL_AVAILABLE=45254
IMDB_IMPORTED=45254
IMDB_HAS_MORE=NO (весь фид пройден)
IMDB_2000_LIMIT_CAUSE=срез [:2000] в разовом скрипте прошлого этапа; в модуле такого предела нет

KINOPOISK_TOTAL_AVAILABLE=46823
KINOPOISK_IMPORTED=46851
KINOPOISK_HAS_MORE=NO (весь фид пройден)
KINOPOISK_2000_LIMIT_CAUSE=срез [:2000] в разовом скрипте прошлого этапа

AMD_ONLINE_STATUS=BLOCKED_SOURCE_PERMISSION
AMD_ONLINE_ACCESS_TYPE=BLOCKED
AMD_ONLINE_API_FOUND=NO
AMD_ONLINE_FEED_FOUND=NO
AMD_ONLINE_AUTHORIZED_EXPORT_FOUND=NO
AMD_ONLINE_IMPORTED=0
AMD_ONLINE_UNIQUE_TITLES=0

COMPOSITE_FORMULA_VERSION=equal_weight_mean_v1
COMPOSITE_MIN_SOURCES=2
TITLES_WITH_COMPOSITE_RATING=24737
COMPOSITE_COVERAGE_PERCENT=46.15
ANIMEDIA_ICU_COMPOSITE_COVERAGE_PERCENT=75.92

DAILY_TARGET=500
DAILY_COMPLETED=110100
DAILY_UNCHANGED_CHECKED=7466
DAILY_PENDING_BACKLOG=660
DAILY_BLOCKED_BY_RATE_LIMIT=147
DAILY_BLOCKED_BY_SECRET=1
ESTIMATED_DAYS_TO_BACKFILL_COMPLETE=1

SIMKL_BLOCKER=secret_ref simkl_client_id отсутствует; HTTP 412 client_id_failed
NEXT_OWNER_ACTION=см. раздел «Что требуется от владельца»
```

---

## 1. Настоящее покрытие: знаменатель, а не число строк

Прежняя цифра **5603 — это строки источников**, а не произведения. Одно
произведение с AniList, Kitsu и Shikimori даёт три строки и одно
произведение.

| Величина | Каталог | animedia.icu |
| --- | --- | --- |
| Уникальных произведений | 53 596 | 7 425 |
| Внешних идентификаторов | 107 431 | 14 495 |
| Строк источников | 110 100 | — |
| Оценок со значением | 63 427 | — |
| Успешно сопоставленных произведений | 51 182 | — |

| Покрытие | Каталог | % | animedia.icu | % |
| --- | --- | --- | --- | --- |
| Хотя бы одна внешняя оценка | 33 687 | **62,85** | 6 860 | **92,39** |
| Две и более независимые | 24 737 | 46,15 | 5 637 | 75,92 |
| Сводная оценка | 24 737 | 46,15 | 5 637 | 75,92 |
| Без единой оценки | 19 909 | 37,15 | 565 | 7,61 |
| Без внешних идентификаторов | 79 | 0,15 | 23 | 0,31 |
| На ручной проверке | 2 440 | 4,55 | — | — |

Было на старте этапа: каталог **3,24 %**, animedia.icu **8,61 %**.

Типы: каталог — 33 190 фильмов и 20 406 сериалов; animedia.icu — 5 504
сериала и 1 921 фильм. Каталог различает только эти два типа, поэтому
OVA и спецвыпуски отдельными классами в нём не выделены — это и есть
причина большинства карантинов ниже.

По источникам (уникальные произведения):

| Источник | Каталог | animedia.icu |
| --- | --- | --- |
| Shikimori | 6 760 | 6 760 |
| AniList | 5 484 | 5 484 |
| Kitsu | 4 833 | 4 833 |
| IMDb (фид) | 26 807 | 226 |
| Кинопоиск (фид) | 19 543 | 197 |
| Simkl | 0 | 0 |

## 2. Откуда взялось «ровно 2000»

Не предел фида, не курсор, не страница, не дневная квота и не лицензия.
Это **срез `[:2000]` в разовом скрипте запуска прошлого этапа**
(`titles = reg.with_external_id(...)[:2000]`). В коде модуля числа 2000
нет вовсе — проверено `grep` по `factory/unified_ratings/`.

Фид содержит 45 254 идентификатора IMDb (26 834 с реальной оценкой) и
46 823 Кинопоиска (19 600 с оценкой). Оба пройдены полностью:
`IMDB_IMPORTED=45254`, `KINOPOISK_IMPORTED=46851`. Доказательство —
`08-sources/LIMIT_2000_INVESTIGATION.json`.

## 3. Полный сбор

| Источник | Произведений пройдено | Вставлено | Обновлено | Unchanged | Не найдено | Отказов |
| --- | --- | --- | --- | --- | --- | --- |
| Shikimori | 7 032 | 6 354 | 204 | 395 | 7 | 0 |
| AniList | 6 953 | 4 301 | 0 | 1 458 | 151 | 25 |
| Kitsu | 7 000+ | 3 370+ | 251 | 215 | 407 | 0 |
| IMDb (фид) | 45 254 | 44 251 | 0 | 0 | 2 | 0 |
| Кинопоиск (фид) | 46 851 | 45 849 | 0 | 1 000 | 2 | 0 |

Ограничения источников соблюдались: AniList сам объявляет 30 запросов в
минуту, наш cap 20; 147 ответов 429 обработаны паузой и повтором с
ограниченным backoff, обхода лимитов не было. Фиды сетевых запросов не
делают вовсе.

## 4. Сводная оценка

`composite_external_rating`, в интерфейсе «Сводная оценка».

```
composite = Σ(normalized_i × weight_i) / Σ(weight_i),  weight_i = 1.0
```

Число голосов **не** вес: у AniList под сто тысяч оценивших, у Kitsu —
десятки тысяч, и взвешивание по голосам сделало бы сводную оценку почти
равной AniList. Голоса показываются отдельно как признак уверенности.

Появляется при двух и более источниках. С одним — состояние
`SINGLE_SOURCE_ONLY`: одно число сводной оценкой не является, и называть
его так значит вводить читателя в заблуждение.

Рассчитана для 24 737 произведений (46,15 %), на animedia.icu — 5 637
(75,92 %).

## 5. AMD Online

`AMD_ONLINE_STATUS=BLOCKED_SOURCE_PERMISSION`. Официального API нет
(`/api/` → 404, сайт на DataLife Engine), разрешённого фида нет,
внутреннего экспорта нет, письменное разрешение в проекте зафиксировано
как `NOT_PROVIDED`. Парсер **не создан**: публичная HTML-страница не
является разрешением на систематический сбор.

Модель на случай разрешения спроектирована: общий рейтинг и оценки
сюжета, персонажей, рисовки и озвучки хранятся отдельными dimensions и
не смешиваются.

## 6. Очередь проверки: 2 440 записей

| Причина | Записей |
| --- | --- |
| `SPECIAL_OVA_VS_MAIN` | 1 843 |
| `MOVIE_VS_SERIES` | 288 |
| `YEAR_MISMATCH` | 240 |
| `EXTERNAL_ID_CONFLICT` | 46 |
| `SEASON_MISMATCH` | 18 |
| `REMAKE` | 5 |

Ложных автоматических сопоставлений — **0**. Ни одна запись очереди не
публикуется: строка источника получает состояние `PENDING_REVIEW`.

Преобладание `SPECIAL_OVA_VS_MAIN` объяснимо и ожидаемо: наш каталог
знает только `tv` и `movie`, а AniList и Kitsu различают OVA, ONA и
спецвыпуски. Разбор по причинам с примерами —
`10-coverage/STAGE2_COVERAGE.json` → `review_queue.samples_per_reason`.

## 7. Суточная квота

`DAILY_COMPLETED=110100` при цели 500 — это первичное наполнение, а не
обычные сутки. Backlog сократился до **660** связок, прогноз завершения
первичного наполнения — 1 день. После него система переходит из режима
наполнения в режим актуализации и не создаёт записи ради цифры.

Зачёт идёт по парам «произведение + источник», у которых появилось или
изменилось значение. Повторное чтение неизменившегося (7 466 за сутки) в
цель не входит.

## 8. Канарейка animedia.icu: почему остановка

Цепочка проверена, не угадана:

```
animedia.icu → /etc/nginx/lords/animedia-01.conf → 127.0.0.1:9121
             → nova-animedia-01.service → PID 279780
             → releases/20260921T214937Z-fac5643-animedia-parity
```

`animedia-01.service` — **другой** юнит (PID 474239) и порт 9121 не
держит.

Ворота индексации пройдены: `noindex, nofollow` в заголовке и в meta на
всех пяти маршрутах, canonical на месте, ничего не менялось.

**Блокирует выкладку то, что витрина занята.** Работающий релиз собран
веткой `claude/animedia-original-parity-01` из worktree
`/home/claude/wt-animedia-original-parity-01`, и её сессия в момент
проверки продолжала собирать новые релизы (`git archive` новых коммитов,
PID 2029305/2029314). Текущий `animedia-frontend.py` не импортирует ни
community-, ни unified-overlay, поэтому подключение виджета требует
правки файла витрины — а сборка своего артефакта из ветки оценок
перезаписала бы их живой релиз. Это перехват, и он запрещён.

Поэтому артефакт витрины **не собирался**, служба **не
перезапускалась**, файлы в `/srv/lords/.frontend/` **не размещались**.

## 9. Что подготовлено и ждёт

Ветка `claude/animedia-ratings-canary-01`, коммит `c264046`:

* `factory/animedia/unified_ratings_adapter.py` — минимальный адаптер,
  отказывающий в пользу страницы (нет файла, нет флага, тайтл вне
  когорты, повреждённый JSON — карточка рендерится как прежде);
* `factory/animedia/frontend/unified_rating_widget.{html,css,js}` —
  сводная оценка, источники раздельно, «Оценка зрителей», «Наша оценка»,
  шкала 1–10 с клавиатурной навигацией, изменением и отзывом;
* `docs/animedia/UNIFIED_RATINGS_INTEGRATION.md` — контракт: три точки
  подключения в витрине и три метода API;
* 18 тестов адаптера, два зелёных прогона.

Пакет выкладки (не размещён):

| Файл | Куда | SHA-256 |
| --- | --- | --- |
| `unified-ratings-projection-animedia.json` (14,75 МБ, 6 860 произведений) | `/srv/lords/.frontend/` | `cd92db74…6b4240` |
| `unified-ratings-flags-animedia.json` | `/srv/lords/.frontend/` | `898f2647…558d841` |

Флаги: чтение включено, запись выключена, раскатка записи 0 %, kill
switch готов, когорта задана явным списком.

## 10. Что требуется от владельца

1. **Очередь на animedia.icu.** Дождаться, пока терминал «ШАБЛОН
   ANIMEDIA» (`claude/animedia-original-parity-01`) завершит цикл, затем
   передать ему контракт из
   `docs/animedia/UNIFIED_RATINGS_INTEGRATION.md`. Три строки в
   `automation/host/animedia-frontend.py` — импорт, вызов
   `merge_into_detail` и монтирование партиала.
2. **Simkl.** Создать `secret_ref simkl_client_id` в штатном secret
   storage. Значение не раскрывать. После этого — повторный Этап A для
   подтверждения контракта шкалы живым ответом, затем пилот.
3. **AMD Online.** Получить письменное разрешение владельца amd.online
   на систематическое чтение публичных карточек с указанием допустимой
   частоты, либо доступ к экспорту. Документ — как
   `docs/rights/amd-online-ratings.md`.

## 11. Честные ограничения

* Голосование зрителей нигде не включено и ни одного голоса в боевой
  базе нет: `community_votes = 0`. Проверить создание, изменение и отзыв
  «на живом» нельзя, пока виджет не выложен; всё это проверено тестами.
* 2 440 сопоставлений ждут человека и не показываются.
* Покрытие каталога 62,85 %, а не 100 %: у 19 909 произведений ни один
  разрешённый источник не дал значения — в основном это записи без
  MAL-идентификатора и без оценки в фиде. Это не сбой сбора, а предел
  доступных данных.
* В ходе работы дважды переполнялся общий диск. Причина со стороны
  этого этапа — тестовый фикстур, копировавший выросшую боевую базу в
  каждом тесте; исправлено на одну копию за прогон. Основной объём в
  обоих случаях занимали временные каталоги другой сессии, их не
  трогали.
