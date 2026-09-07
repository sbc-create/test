# Домен `job_runtime`

> Собирается из `config/domains.yaml`.
> Правка этого файла руками бессмысленна: проверка сверит его с реестром.

## Назначение

Очередь, исполнитель, таймеры, повторы и замки. Не знает, что именно исполняет.

## Что держит

* `job_queue`
* `job_state`
* `locks`

## Разрешённые пути

* `factory/job_runtime/`
* `factory/queue.py`
* `factory/locks.py`
* `factory/state.py`
* `factory/input_request.py`

## Публичный интерфейс

Снаружи домена берут только это. Всё остальное — устройство,
и гейт границ проверяет именно это разделение.

* `factory.queue`
* `factory.locks`

## Запрещённые зависимости

* `catalog`
* `editorial`
* `templates`
* `insights`

## Как проверить

```
pytest tests/unit -k "queue or lock or retry or pipeline"
```

## Как откатить

git revert; незавершённые задания переигрываются по идемпотентности
