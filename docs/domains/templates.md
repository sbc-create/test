# Домен `templates`

> Собирается из `config/domains.yaml`.
> Правка этого файла руками бессмысленна: проверка сверит его с реестром.

## Назначение

Реестр шаблонов, версии, совместимость и манифесты. Не отрисовка — отрисовка принадлежит семейству витрин.

## Что держит

* `template_registry`
* `template_manifests`

## Разрешённые пути

* `factory/site_engine/template_registry.py`
* `factory/templates/`
* `factory/blueprint.py`

## Публичный интерфейс

Снаружи домена берут только это. Всё остальное — устройство,
и гейт границ проверяет именно это разделение.

* `factory.site_engine.template_registry`
* `factory.templates.digest`

## Запрещённые зависимости

* `catalog`
* `editorial`
* `insights`

## Как проверить

```
pytest tests/unit -k "template"
```

## Как откатить

git revert; реестр шаблонов только пополняется
