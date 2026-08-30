# Модули Site Engine

Файл порождается из `config/site-engine/module-registry.json`; правится реестр.
Гейт границ читает тот же реестр, поэтому документ не может разойтись с кодом.

| Модуль | Статус | Владеет | Реализация |
| --- | --- | --- | --- |
| `core-contracts` | реализован | определения нормализованной модели и контрактов | `factory/site_engine/contracts.py` |
| `site-configuration` | реализован | профили сайтов и флаги | `factory/site_engine/profiles.py` |
| `provider-adapters` | подключён адаптером к существующей реализации | сырые ответы поставщика | `factory/site_engine/providers.py` |
| `content-ingestion` | подключён адаптером к существующей реализации | состояние обхода и полноту | `factory/site_engine/ingestion.py` |
| `normalized-content` | реализован | Title, Season, Episode и их канонические идентификаторы | `factory/site_engine/store.py` |
| `catalog` | описан контрактом, кода пока нет | правила выборки, но не сами данные | — |
| `episodes-seasons` | описан контрактом, кода пока нет | счётчики сезонов и вывод о прибавке | — |
| `playback` | описан контрактом, кода пока нет | PlaybackAvailability | — |
| `shelves` | описан контрактом, кода пока нет | полки | — |
| `ratings` | описан контрактом, кода пока нет | Rating | — |
| `schedule` | описан контрактом, кода пока нет | ScheduleItem | — |
| `announcements` | описан контрактом, кода пока нет | Announcement | — |
| `cache-invalidation` | реализован | теги кэша и их отображение из событий | `factory/site_engine/cache.py` |
| `seo-bridge` | описан контрактом, кода пока нет | SeoDocument | — |
| `editorial` | реализован | EditorialOverride, Draft, Revision, Publication | `factory/site_engine/editorial.py` |
| `audit` | реализован | AuditEvent | `factory/site_engine/audit.py` |
| `monitoring` | описан контрактом, кода пока нет | метрики и тревоги | — |
| `renderer-adapters` | подключён адаптером к существующей реализации | страницы | `factory/site_engine/renderers.py` |
| `site-engine-api` | реализован | формой ответов и их совместимостью | `factory/site_engine/api/app.py` |

## Подробно

### `core-contracts`

**Назначение.** Схемы и типы, на которые ссылаются все остальные. Ничего не делает сам.

**Статус.** реализован

**Владеет данными.** определения нормализованной модели и контрактов

**Публичный интерфейс.** `schemas/site-engine/*.schema.json`, `factory.site_engine.contracts`

**Вход.** —  
**Выход.** JSON Schema, типы

**События.** не выпускает

**Зависит от.** ни от кого

**Запрещённые зависимости.** `любой модуль, любой фреймворк, любая БД, любой поставщик`

**Ошибки.** `SchemaError`

**Метрики.** —  
**Теги кэша.** —

### `site-configuration`

**Назначение.** Профиль сайта: всё, что отличает сайт от сайта.

**Статус.** реализован

**Владеет данными.** профили сайтов и флаги

**Публичный интерфейс.** `factory.site_engine.profiles`, `factory.site_engine.scaffold`

**Вход.** config/site-profiles/*.json  
**Выход.** SiteProfile, новый профиль сайта

**События.** не выпускает

**Зависит от.** `core-contracts`

**Запрещённые зависимости.** `provider-adapters`, `content-ingestion`, `renderer-adapters`

**Ошибки.** `ProfileNotFound`, `ProfileInvalid`

**Метрики.** `profiles_loaded`  
**Теги кэша.** —

### `provider-adapters`

**Назначение.** Перевод чужого API в наш контракт. Знает про HTTP, не знает про витрины.

**Статус.** подключён адаптером к существующей реализации

**Владеет данными.** сырые ответы поставщика

**Публичный интерфейс.** `factory.site_engine.adapters.yummy_events`, `factory.site_engine.providers.ProviderAdapter`

**Вход.** внешний API  
**Выход.** RawTitle, RawSeason

**События.** `перевод чужого формата в ContentEvent`

**Зависит от.** `core-contracts`

**Запрещённые зависимости.** `renderer-adapters`, `seo-bridge`, `shelves`, `editorial`

**Ошибки.** `ProviderUnavailable`, `ProviderContractBroken`

**Метрики.** `provider_requests`, `provider_failures`  
**Теги кэша.** —

### `content-ingestion`

**Назначение.** Обход поставщика и наполнение нормализованного хранилища.

**Статус.** подключён адаптером к существующей реализации

**Владеет данными.** состояние обхода и полноту

**Публичный интерфейс.** `factory.site_engine.ingestion`

**Вход.** ProviderAdapter  
**Выход.** IngestionRun, CoverageReport

**События.** `TITLE_CREATED`, `TITLE_UPDATED`, `EPISODE_ADDED`, `SEASON_ADDED`, `SOURCE_ANOMALY`

**Зависит от.** `core-contracts`, `provider-adapters`, `normalized-content`

**Запрещённые зависимости.** `seo-bridge`, `renderer-adapters`, `shelves`, `editorial`

**Ошибки.** `SourceError`, `CatalogTruncation`

**Метрики.** `titles_seen`, `pages_walked`, `detail_failures`  
**Теги кэша.** —

### `normalized-content`

**Назначение.** Нормализованное хранилище: единственный источник правды о содержимом.

**Статус.** реализован

**Владеет данными.** Title, Season, Episode и их канонические идентификаторы

**Публичный интерфейс.** `factory.site_engine.store.NormalizedStore`

**Вход.** записи от ingestion  
**Выход.** Title, Season, Episode

**События.** не выпускает

**Зависит от.** `core-contracts`

**Запрещённые зависимости.** `provider-adapters`, `renderer-adapters`, `seo-bridge`

**Ошибки.** `TitleNotFound`

**Метрики.** `titles_stored`  
**Теги кэша.** `catalog`, `title`

### `catalog`

**Назначение.** Выборки по нормализованному хранилищу: фильтры, сортировки, страницы.

**Статус.** описан контрактом, кода пока нет

**Владеет данными.** правила выборки, но не сами данные

**Публичный интерфейс.** `CatalogQuery`

**Вход.** NormalizedStore  
**Выход.** Page[Title]

**События.** не выпускает

**Зависит от.** `core-contracts`, `normalized-content`

**Запрещённые зависимости.** `provider-adapters`, `content-ingestion`, `seo-bridge`

**Ошибки.** `QueryInvalid`

**Метрики.** `catalog_queries`  
**Теги кэша.** `catalog`

### `episodes-seasons`

**Назначение.** Сезоны, серии и дельта серий.

**Статус.** описан контрактом, кода пока нет

**Владеет данными.** счётчики сезонов и вывод о прибавке

**Публичный интерфейс.** `EpisodeDelta`

**Вход.** NormalizedStore  
**Выход.** Season, Episode

**События.** `EPISODE_ADDED`, `SEASON_ADDED`

**Зависит от.** `core-contracts`, `normalized-content`

**Запрещённые зависимости.** `renderer-adapters`, `seo-bridge`

**Ошибки.** собственных нет

**Метрики.** `episodes_added`  
**Теги кэша.** `title`, `shelf:new-episodes`

### `playback`

**Назначение.** Признак «смотрибельно» и ничего кроме.

**Статус.** описан контрактом, кода пока нет

**Владеет данными.** PlaybackAvailability

**Публичный интерфейс.** `PlaybackProbe`

**Вход.** NormalizedStore  
**Выход.** PlaybackAvailability

**События.** `PLAYBACK_AVAILABLE`, `PLAYBACK_UNAVAILABLE`

**Зависит от.** `core-contracts`, `normalized-content`

**Запрещённые зависимости.** `seo-bridge`, `editorial`

**Ошибки.** собственных нет

**Метрики.** `playable_titles`  
**Теги кэша.** `title`, `shelf:watchable`

### `shelves`

**Назначение.** Состав и порядок полок витрины.

**Статус.** описан контрактом, кода пока нет

**Владеет данными.** полки

**Публичный интерфейс.** `ShelfBuilder`

**Вход.** catalog, episodes-seasons, ratings  
**Выход.** Shelf

**События.** не выпускает

**Зависит от.** `core-contracts`, `normalized-content`

**Запрещённые зависимости.** `provider-adapters`, `content-ingestion`, `seo-bridge`

**Ошибки.** собственных нет

**Метрики.** `shelves_built`  
**Теги кэша.** `shelf`

### `ratings`

**Назначение.** Оценки из подтверждённых владельцем источников.

**Статус.** описан контрактом, кода пока нет

**Владеет данными.** Rating

**Публичный интерфейс.** `RatingSource`

**Вход.** внешние идентификаторы  
**Выход.** Rating

**События.** `RATING_UPDATED`

**Зависит от.** `core-contracts`, `normalized-content`

**Запрещённые зависимости.** `renderer-adapters`, `seo-bridge`

**Ошибки.** `RatingSourceUnavailable`

**Метрики.** `ratings_known`  
**Теги кэша.** `ratings`

### `schedule`

**Назначение.** Календарь выхода серий.

**Статус.** описан контрактом, кода пока нет

**Владеет данными.** ScheduleItem

**Публичный интерфейс.** `ScheduleSource`

**Вход.** normalized-content  
**Выход.** ScheduleItem

**События.** `SCHEDULE_UPDATED`

**Зависит от.** `core-contracts`, `normalized-content`

**Запрещённые зависимости.** `seo-bridge`

**Ошибки.** `ScheduleSourceMissing`

**Метрики.** —  
**Теги кэша.** `schedule`

### `announcements`

**Назначение.** Анонсы и новости.

**Статус.** описан контрактом, кода пока нет

**Владеет данными.** Announcement

**Публичный интерфейс.** `AnnouncementSource`

**Вход.** normalized-content, editorial  
**Выход.** Announcement

**События.** `ANNOUNCEMENT_UPDATED`

**Зависит от.** `core-contracts`, `normalized-content`

**Запрещённые зависимости.** `provider-adapters`

**Ошибки.** собственных нет

**Метрики.** —  
**Теги кэша.** `announcements`

### `cache-invalidation`

**Назначение.** Теги, их сброс и политика кэша. Правил показа не устанавливает.

**Статус.** реализован

**Владеет данными.** теги кэша и их отображение из событий

**Публичный интерфейс.** `factory.site_engine.cache.CacheProvider`, `factory.site_engine.cache.InvalidationRequest`

**Вход.** ContentEvent, CachePolicy  
**Выход.** CacheResult

**События.** не выпускает

**Зависит от.** `core-contracts`

**Запрещённые зависимости.** `provider-adapters`, `renderer-adapters`, `seo-bridge`, `shelves`, `catalog`

**Ошибки.** собственных нет

**Метрики.** `cache_hit`, `cache_miss`, `cache_stale`, `cache_error`  
**Теги кэша.** `*`

### `seo-bridge`

**Назначение.** Мост между нормализованным контентом и SEO. Каталогом не владеет.

**Статус.** описан контрактом, кода пока нет

**Владеет данными.** SeoDocument

**Публичный интерфейс.** `SeoBridge`

**Вход.** normalized-content  
**Выход.** SeoDocument

**События.** не выпускает

**Зависит от.** `core-contracts`, `normalized-content`

**Запрещённые зависимости.** `provider-adapters`, `content-ingestion`

**Ошибки.** собственных нет

**Метрики.** —  
**Теги кэша.** `seo`

### `editorial`

**Назначение.** Редакционный слой: правки поверх данных поставщика, не вместо них.

**Статус.** реализован

**Владеет данными.** EditorialOverride, Draft, Revision, Publication

**Публичный интерфейс.** `factory.site_engine.editorial`

**Вход.** редакторские действия  
**Выход.** EditorialOverride, Revision

**События.** не выпускает

**Зависит от.** `core-contracts`, `audit`

**Запрещённые зависимости.** `provider-adapters`, `content-ingestion`

**Ошибки.** `RevisionConflict`, `PermissionDenied`

**Метрики.** `overrides_active`  
**Теги кэша.** `title`, `seo`

### `audit`

**Назначение.** Кто, когда и почему изменил. Запись только добавляется.

**Статус.** реализован

**Владеет данными.** AuditEvent

**Публичный интерфейс.** `factory.site_engine.audit`

**Вход.** действия модулей  
**Выход.** AuditEvent

**События.** не выпускает

**Зависит от.** `core-contracts`

**Запрещённые зависимости.** `provider-adapters`, `renderer-adapters`

**Ошибки.** собственных нет

**Метрики.** `audit_events`  
**Теги кэша.** —

### `monitoring`

**Назначение.** Покрытие, здоровье, пороги и тревоги.

**Статус.** описан контрактом, кода пока нет

**Владеет данными.** метрики и тревоги

**Публичный интерфейс.** `HealthReport`, `CoverageReport`

**Вход.** все модули  
**Выход.** HealthReport

**События.** не выпускает

**Зависит от.** `core-contracts`

**Запрещённые зависимости.** —

**Ошибки.** собственных нет

**Метрики.** `coverage_ratio`  
**Теги кэша.** —

### `renderer-adapters`

**Назначение.** Перевод нормализованного контента в страницы. Данными не владеет.

**Статус.** подключён адаптером к существующей реализации

**Владеет данными.** страницы

**Публичный интерфейс.** `factory.site_engine.renderers.RendererAdapter`

**Вход.** Shelf, Title  
**Выход.** страницы

**События.** не выпускает

**Зависит от.** `core-contracts`, `site-configuration`

**Запрещённые зависимости.** `provider-adapters`, `content-ingestion`, `cache-invalidation`

**Ошибки.** `RenderFailed`

**Метрики.** `pages_rendered`  
**Теги кэша.** —

### `site-engine-api`

**Назначение.** Чтение нормализованного контента снаружи модульного монолита. Собственных данных не имеет и ничего не изменяет.

**Статус.** реализован

**Владеет данными.** формой ответов и их совместимостью

**Публичный интерфейс.** `factory.site_engine.api`

**Вход.** SiteProfile, NormalizedStore  
**Выход.** ApiResponse, OpenAPI

**События.** не выпускает

**Зависит от.** `core-contracts`, `site-configuration`, `normalized-content`

**Запрещённые зависимости.** `provider-adapters`, `content-ingestion`, `renderer-adapters`

**Ошибки.** `ApiDisabled`

**Метрики.** `api_requests`  
**Теги кэша.** —

