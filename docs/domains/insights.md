# Домен `insights`

> Собирается из `config/domains.yaml`.
> Правка этого файла руками бессмысленна: проверка сверит его с реестром.

## Назначение

Наблюдения о происходящем. Аналитика, здоровье SEO, доступность, состояние содержимого и журнал действий.

## Что держит

* `audit_log`
* `analytics_snapshots`
* `seo_health`

## Разрешённые пути

* `factory/analytics/`
* `factory/topvisor/`
* `factory/seo/`
* `factory/site_engine/insights/`
* `factory/site_engine/seo_binding.py`
* `factory/site_engine/freshness.py`
* `factory/site_engine/fingerprint.py`
* `factory/audit.py`
* `factory/report.py`
* `factory/verify.py`
* `factory/ads.py`

## Публичный интерфейс

Снаружи домена берут только это. Всё остальное — устройство,
и гейт границ проверяет именно это разделение.

* `factory.audit`
* `factory.site_engine.seo_binding`

## Запрещённые зависимости

* `releases`
* `job_runtime`

## Как проверить

```
pytest tests/unit -k "seo or analytics or audit or freshness"
```

## Как откатить

git revert; наблюдения только добавляются
