# Домен `fleet`

> Собирается из `config/domains.yaml`.
> Правка этого файла руками бессмысленна: проверка сверит его с реестром.

## Назначение

Какие витрины есть, чем они являются и в каком они состоянии. Домены, тенанты, назначенный шаблон, признаки и наблюдаемое состояние.

## Что держит

* `site_profiles`
* `fleet_observations`
* `site_settings`

## Разрешённые пути

* `factory/site_engine/fleet/`
* `factory/site_engine/fleet_registry.py`
* `factory/site_engine/fleet_accounts.py`
* `factory/site_engine/site_plan.py`
* `factory/site_engine/profiles.py`
* `factory/site_engine/settings_contract.py`
* `factory/site_engine/settings_view.py`
* `factory/site_engine/site_admin_contract.py`
* `factory/inventory.py`
* `factory/portfolio.py`

## Публичный интерфейс

Снаружи домена берут только это. Всё остальное — устройство,
и гейт границ проверяет именно это разделение.

* `factory.site_engine.fleet_registry`
* `factory.site_engine.settings_contract`

## Запрещённые зависимости

* `editorial`
* `job_runtime`

## Как проверить

```
pytest tests/unit -k "fleet or settings or profile"
```

## Как откатить

git revert; наблюдения пересобираются сборщиком
