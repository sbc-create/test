# Контракт кэша

Схема: `schemas/site-engine/cache-policy.schema.json`. Политика описана в каждом
профиле сайта целиком — общего умолчания нет, чтобы «настройка по умолчанию» не
превращалась в невидимую причину несвежести.

## Слои и TTL (одинаковы у всех шести сайтов)

| Слой | TTL, с | SWR, с | Теги |
| --- | --- | --- | --- |
| `new_episodes` | 300 | 120 | `shelf:new-episodes`, `events` |
| `homepage_shelves` | 300 | 300 | `shelf` |
| `catalog` | 900 | 600 | `catalog` |
| `title_page` | 900 | 600 | `title` |
| `schedule` | 1800 | 600 | `schedule` |
| `announcements` | 1800 | 600 | `announcements` |
| `seo` | 3600 | 1800 | `seo` |
| `ratings` | 21600 | 3600 | `ratings` |
| `static_assets` | 86400 | — | `static` |

`last_known_good` включён у всех слоёв: при отказе источника отдаём последнее
хорошее состояние, а не пустоту.

## Инвалидация по событиям

| Событие | Сбрасываемые теги |
| --- | --- |
| `EPISODE_ADDED` | `title`, `shelf:new-episodes`, `catalog` |
| `TITLE_CREATED` | `shelf:new-titles`, `catalog` |
| `PLAYBACK_AVAILABLE` | `title`, `shelf:watchable` |
| `RATING_UPDATED` | `title`, `ratings` |
| `SCHEDULE_UPDATED` | `schedule` |
| `ANNOUNCEMENT_UPDATED` | `announcements` |

Режим — `event-driven`, поддерживается сухой прогон (`dry_run_supported`).

## Запрещено

`cache_errors: false` — ошибки не кэшируются. `empty_response_as_success: false`
— пустой ответ не считается успехом и не вытесняет хорошие данные.
`indefinite_html_cache: false` — бессрочного кэша HTML не бывает.

Эти три запрета — прямое следствие того, как каталог однажды «похудел»:
неполный ответ был закэширован как успешный и держался до истечения TTL.

## Ключи и наблюдаемость

Ключи скоупятся сайтом (`site_scoped: true`): три тенанта из одного образа не
должны видеть кэш друг друга. Защита от лавины — `coalesce`. Слой обязан
показывать `hit/miss/stale` (`expose_hit_miss_stale: true`) — иначе диагностика
несвежести превращается в гадание.

## PERFORMANCE/CACHE GATE

Постоянное требование владельца: любая работа, затрагивающая производительность
или кэш, закрывается только с измерениями до и после. Замер без «до» не
принимается.
