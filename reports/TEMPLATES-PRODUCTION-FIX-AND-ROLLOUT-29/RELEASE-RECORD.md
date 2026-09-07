# Реестр выкладки TEMPLATES-PRODUCTION-FIX-AND-ROLLOUT-29

Все значения сняты с боевого хоста claude-control-01 7 сентября 2026.

## Выкладка 1 — слой отдачи постеров (все шесть витрин)

Меняется конфигурация nginx на хосте; релизы витрин НЕ пересобирались.

| поле | значение |
|---|---|
| объект | `/etc/nginx/snippets/yummyani-poster-cache.conf`, `/etc/nginx/conf.d/yummyani-poster-cache.conf` |
| суть | имя поставщика берётся из переменной, `resolver … valid=60s`; адрес больше не закрепляется при загрузке |
| применено | `systemctl reload nginx` |
| rollback target | `/root/nginx-backups/snippet-yummyani-poster-cache.conf.20260907-191839.bak` (4186 Б), `/root/nginx-backups/confd-yummyani-poster-cache.conf.20260907-191839.bak` (3589 Б) |
| откат | восстановить оба файла и `nginx -t && systemctl reload nginx` |
| охват | lordfilm47.space, lordserial33.biz, 1lordserials1.online, yummyani.biz, yummyani.org, yummyani.site |
| проверка | 345 постеров из 345 — настоящие файлы, заглушек 0; после планового refresh — 291 из 291 |
| источник правды | `tests/fixtures/nginx-poster-cache-*.conf` + `tests/unit/test_poster_origin_is_resolved_per_request.py` |
| ветка | `claude/templates-production-fix-29`, коммит `35d4289` |

## Выкладка 2 — приложение Yummy (три витрины)

| поле | значение |
|---|---|
| репозиторий | `sbc-create/yummyani` (отдельный от фабрики) |
| ветка | `claude/yummy-update-time-29` |
| source SHA | `cf8150da96e0e40c5cf59c6ac986c9fae8920691` |
| образ | `sha256:f9657a2e7c8df24f511df6c74e60fbbc23ded4574210c6fa9cfe9c5f8f9bf21a` |
| теги образа | `yummyani/web:staging`, `yummyani/web:prodfix-29` |
| rollback target | `yummyani/web:rollback-prodfix-29` → `sha256:2b8de871745e6098cfcbfd7bfff7e83d9b1e47bddfef03baf71d2da2517d8cd4` (ревизия `4460031…`) |
| резервная копия БД | `/srv/backups/yummyani-staging/20260907T194930Z` — три базы, у каждой сверен восстановленный дамп |
| порядок | canary `web-biz` → `web-org` → `web-site`, по одной витрине |

### Ход выкладки

| шаг | витрина | ревизия после | «Обновления аниме»: строк со временем |
|---|---|---|---|
| до | все три | `4460031…` | 1 из 24 |
| canary | yummyani.biz | `cf8150d…` | **24 из 24** |
| — | yummyani.org | `4460031…` (не тронута) | 1 из 24 |
| — | yummyani.site | `4460031…` (не тронута) | 1 из 24 |
| rollout | yummyani.org | `cf8150d…` | **24 из 24** |
| rollout | yummyani.site | `cf8150d…` | **24 из 24** |

### Проверка отката — выполнена на самом деле

`yummyani.site` возвращена на `4460031…`: строк со временем снова 1 из 24,
при этом `yummyani.biz` и `yummyani.org` остались на `cf8150d…` с 24 из 24 —
соседние витрины не пострадали. После проверки витрина возвращена вперёд.

## Витрины Lords — не изменялись

| витрина | release | подтверждение |
|---|---|---|
| lordfilm47.space | `b6ca450efdb2` | HTTP 200 |
| lordserial33.biz | `edd290dd6616` | HTTP 200 |
| 1lordserials1.online | `a12130ce1c1c` | HTTP 200 |

Указатели `current` до и после работ совпадают. Контракт плеера и список
разрешённых playback identifiers не затрагивались.
