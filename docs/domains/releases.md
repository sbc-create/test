# Домен `releases`

> Собирается из `config/domains.yaml`.
> Правка этого файла руками бессмысленна: проверка сверит его с реестром.

## Назначение

Как построенное становится выложенным. Сборка, артефакт, канарейка, переключение, откат.

## Что держит

* `release_manifests`
* `release_log`
* `artifacts`

## Разрешённые пути

* `factory/lords/release_manifest.py`
* `factory/lords/refresh_release.py`
* `factory/lords/template_artifact.py`
* `factory/lords/canary.py`
* `factory/targets/`
* `factory/build.py`
* `factory/pipeline.py`
* `factory/site_engine/gate.py`

## Публичный интерфейс

Снаружи домена берут только это. Всё остальное — устройство,
и гейт границ проверяет именно это разделение.

* `factory.lords.release_manifest`
* `factory.lords.refresh_release`

## Запрещённые зависимости

* `editorial`
* `iam`

## Как проверить

```
pytest tests/unit -k "release or canary or artifact or manifest"
```

## Как откатить

цель отката записана в самом манифесте; переключение атомарно
