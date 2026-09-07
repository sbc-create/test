# Домен `editorial`

> Собирается из `config/domains.yaml`.
> Правка этого файла руками бессмысленна: проверка сверит его с реестром.

## Назначение

Правки редакции поверх данных поставщика, очередь разбора и публикационный порядок.

## Что держит

* `editorial_overrides`
* `review_queue`
* `publications`

## Разрешённые пути

* `factory/site_engine/editorial/`
* `factory/site_engine/review_build.py`
* `factory/site_engine/review_queue.py`
* `factory/site_engine/publish.py`

## Публичный интерфейс

Снаружи домена берут только это. Всё остальное — устройство,
и гейт границ проверяет именно это разделение.

* `factory.site_engine.editorial`

## Запрещённые зависимости

* `providers`
* `ingestion`
* `releases`

## Как проверить

```
pytest tests/unit -k "editorial or review or publish"
```

## Как откатить

git revert; правки редакции версионируются и не теряются
