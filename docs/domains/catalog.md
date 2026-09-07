# Домен `catalog`

> Собирается из `config/domains.yaml`.
> Правка этого файла руками бессмысленна: проверка сверит его с реестром.

## Назначение

Содержимое и его тождество. Записи, идентификаторы, вид произведения, рейтинги и состояние воспроизведения.

## Что держит

* `titles`
* `external_title_ids`
* `rating_observations`
* `current_ratings`
* `enrichment_jobs`

## Разрешённые пути

* `factory/site_engine/catalog_identity.py`
* `factory/site_engine/content_identity.py`
* `factory/site_engine/content_kind.py`
* `factory/site_engine/store.py`
* `factory/site_engine/ingestion.py`
* `factory/site_engine/providers.py`
* `factory/site_engine/rating_feed.py`
* `factory/site_engine/rating_enrichment.py`
* `factory/site_engine/rating_sources.py`
* `factory/site_engine/rating_discovery.py`
* `factory/site_engine/playback_policy.py`
* `factory/site_engine/title_normalize.py`
* `factory/site_engine/identity_resolver.py`
* `factory/site_engine/catalog_snapshot.py`
* `factory/site_engine/kind_overlay.py`
* `factory/recs/`

## Публичный интерфейс

Снаружи домена берут только это. Всё остальное — устройство,
и гейт границ проверяет именно это разделение.

* `factory.site_engine.store`
* `factory.site_engine.catalog_identity`
* `factory.site_engine.catalog_snapshot`

## Запрещённые зависимости

* `templates`
* `releases`
* `control_plane`

## Как проверить

```
pytest tests/unit -k "catalog or rating or identity or ingestion"
```

## Как откатить

git revert; наблюдения рейтингов только добавляются, не переписываются
