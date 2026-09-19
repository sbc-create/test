# Правовое основание и контракт: Shikimori ratings (GraphQL)

**Дата решения Stage 1:** 2026-09-19  
**Кто решил:** владелец продукта (запрос на централизованный ratings ingestion)  
**Что разрешено на Stage 1:** реализовать адаптер официального GraphQL API,
dry-run / read-only probe / candidate snapshot в evidence area.  
**Что НЕ разрешено на Stage 1:** production migration apply, enable systemd
timer, замена live snapshot, ежедневные 500 в production.

## Endpoint

* `POST https://shikimori.io/api/graphql`
* Документация: https://shikimori.io/api/doc и https://shikimori.io/api/doc/graphql
* REST v1/v2 для новой интеграции **не используется**

## Подтверждённый live-контракт (probe)

Поля `Anime`: `id`, `malId`, `name`, `russian`, `score`, `scoresStats{score,count}`,
`updatedAt`, `url`.

* `ids` аргумент — **String** (CSV), batch до 50 подтверждён schema/практикой
* `score` — оценка **Shikimori**, не MAL
* `malId` — идентификатор crosswalk, **не** оценка MAL
* `vote_count` = сумма `scoresStats.count`
* Документированные лимиты API: 5 rps / 90 rpm
* Наш operational cap: `RATINGS_MAX_RPS=2`, `RATINGS_MAX_REQUESTS_PER_MINUTE=60`

## User-Agent и секреты

* Обязателен зарегистрированный/идентифицируемый User-Agent приложения
* Не имитировать браузер
* OAuth/credentials только через Secret Hub / `CREDENTIALS_DIRECTORY` / файл 0600
* Authorization и токены **никогда** не пишутся в лог

## CONTRACT_GATE: атрибуция и длительное хранение

Явных правил атрибуции и длительного хранения оценок Shikimori в публичной
документации на момент Stage 1 **не найдено**. Выдумывать нельзя.

Пока gate открыт, мы обязаны хранить:

* source provenance URL
* время получения
* adapter version
* payload SHA-256
* доказательство актуального API-контракта (probe JSON)

## Запреты

* Подписывать Shikimori score как MAL score
* Безлимитные retries
* Игнорировать 429 / Retry-After
* Production mutations на Stage 1
