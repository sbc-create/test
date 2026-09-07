# Домен `provisioning`

> Собирается из `config/domains.yaml`.
> Правка этого файла руками бессмысленна: проверка сверит его с реестром.

## Назначение

Заведение новой витрины через публичные контракты остальных доменов, без обходных путей.

## Что держит

* `site_requests`
* `provisioning_jobs`

## Разрешённые пути

* `factory/site_engine/site_provision.py`
* `factory/site_engine/site_request.py`
* `factory/site_engine/scaffold.py`
* `factory/contracts/`

## Публичный интерфейс

Снаружи домена берут только это. Всё остальное — устройство,
и гейт границ проверяет именно это разделение.

* `factory.site_engine.site_provision`

## Запрещённые зависимости

* `store`
* `editorial`

## Как проверить

```
pytest tests/unit -k "provision or scaffold or site_request"
```

## Как откатить

заведение идемпотентно; незавершённое заведение не оставляет витрины
