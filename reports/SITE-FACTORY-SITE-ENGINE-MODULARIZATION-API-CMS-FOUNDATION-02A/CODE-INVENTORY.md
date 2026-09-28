# Фактическая карта кода

Измерение, а не оценка. Граф импортов построен разбором AST: строка со словом
«import» в комментарии в граф не попадает. Скрипт — `tools/inventory.py`; запуск: `python3 tools/inventory.py .`

## Репозитории и языки

| Репозиторий | Язык | Роль | Точка входа |
| --- | --- | --- | --- |
| `/srv/site-factory/repo` (рабочие копии `work-test`, `work-02a`) | Python 3.10 | фабрика: планирование, сборка, выкладка, витрины Lords | `python -m factory` |
| `/srv/sites/yummyani-staging/repo` | TypeScript, Next.js, Prisma | три аниме-портала из одного образа | `next start` в контейнере |

## Размер по областям (Python)

| Область | Файлов | Строк |
| --- | --- | --- |
| `lords` | 24 | 7 527 |
| `secret_hub` | 19 | 6 097 |
| `analytics` | 10 | 2 735 |
| `targets` | 5 | 1 448 |
| `seo` | 11 | 1 354 |
| `recs` | 8 | 1 224 |
| `topvisor` | 7 | 956 |
| `cli` | 1 | 864 |
| `render` | 1 | 778 |
| `validation` | 1 | 684 |
| `verify` | 1 | 654 |
| `site_engine` | 2 | 244 |

Остальные двадцать с лишним областей — по одному файлу до 450 строк.

## Точки входа

Подкоманды `factory`: `status`, `resume`, `queue`, `reference-audit`,
`seo-cross-site`, `knowledge`, `db`, `blueprint`, `lords-plan`,
`lords-preview`, `lords-bundle`, `lords-staging`, `lords-live`, `env-report`,
`input-request`, `selfcheck`.

## Фоновые таймеры

| Таймер | Период | Что делает |
| --- | --- | --- |
| `yummy-episode-watcher.timer` | 5 мин | наблюдение за появлением серий |
| `yummy-watchdog.timer` | 5 мин | контроль самого наблюдателя |
| `yummy-enrich.timer` | 10 мин | добор карточек из detail |
| `lords-content-refresh.timer` | 120 мин | обход каталога и пересборка витрин |
| `site-factory-health.timer` | 15 мин | health публичных площадок |
| `site-factory-backup.timer` | сутки | резервные копии |
| `site-factory-selfcheck.timer` | сутки | самопроверка фабрики |
| `site-factory-seo-dryrun.timer` | сутки | сухой прогон SEO |
| `site-factory-restore-proof.timer` | неделя | репетиция восстановления |

## Клиенты поставщика

`cdnvideohub` упоминается в `factory/lords/content_live.py`,
`content_api.py`, `live_site.py`, `live_build.py`, `live_bundle.py`,
`playability.py`, а также в `factory/verify.py` и `factory/analytics/events.py`.
Единой точки входа к поставщику нет — это первое, что должен закрыть
`provider-adapters`.

## Хранилища и runtime-файлы

* кэш живого каталога Lords — три файла по 34,8 МБ, 53 116 записей;
* состояние наблюдателя Yummy — `/srv/sites/yummyani-staging/runtime/episode-state/`:
  `watcher.json` (5,9 МБ, 6 774 записи), `events.jsonl`, `episodes.json`,
  `watchdog-state.json`, `watchdog-status.json`, `watchdog-alerts.jsonl`;
* Postgres — по одной базе на тенант Yummy;
* релизы Lords — `/srv/lords/lords-0X/releases/<sha12>` с симлинком `current`,
  хранятся два.

Часто читаемые описания: `build-manifest.json`, `routes.json`, `report.json`,
`bundle-manifest.json`, `acceptance-routes.json`, `tenant-config.json`,
`target-state.json`, `seo-report.json`, `seo-render.json`, `seo-lint.json`.

## Тестовые наборы

* Python: 142 файла, 2 830 тестов;
* TypeScript: 62 файла, 521 тест.
