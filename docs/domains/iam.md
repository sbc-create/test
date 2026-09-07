# Домен `iam`

> Собирается из `config/domains.yaml`.
> Правка этого файла руками бессмысленна: проверка сверит его с реестром.

## Назначение

Кто действует и вправе ли. Люди, роли, сессии, приглашения и машинные личности AI-клиентов.

## Что держит

* `operators`
* `sessions`
* `invites`
* `ai_identities`

## Разрешённые пути

* `factory/site_engine/iam/`
* `factory/site_engine/operators.py`
* `factory/site_engine/accounts.py`
* `factory/site_engine/account_app.py`
* `factory/site_engine/account_ui.py`
* `factory/secret_hub/`
* `factory/licensing.py`

## Публичный интерфейс

Снаружи домена берут только это. Всё остальное — устройство,
и гейт границ проверяет именно это разделение.

* `factory.site_engine.operators`
* `factory.site_engine.accounts`

## Запрещённые зависимости

* `catalog`
* `releases`
* `insights`

## Как проверить

```
pytest tests/unit -k "operator or identity or account or secret_hub"
```

## Как откатить

git revert коммита переноса; таблицы не мигрируют
