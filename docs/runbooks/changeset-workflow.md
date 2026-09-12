# ChangeSet/Workflow: обслуживание

## Что это

Единственный контур, через который проходят изменения. Путь набора:

```
PROPOSED → VALIDATING → VALIDATED → AWAITING_APPROVAL → APPROVED
        → APPLYING → VERIFYING → SUCCEEDED
```

Боковые исходы: `VALIDATION_FAILED`, `REJECTED`, `STALE`, `EXPIRED`,
`CANCELLED`, `APPLY_FAILED`, `ROLLING_BACK`, `ROLLED_BACK`,
`ROLLBACK_FAILED`, `MANUAL_INTERVENTION_REQUIRED`.

Переходы выполняет сервер. Поля `status` в запросе не существует: клиент
просит выполнить действие, состояние — вывод.

## Источники истины

| Вопрос | Кто отвечает |
|---|---|
| какие есть сайты и каковы они | Site Registry |
| что предложено и на какой стадии | ChangeSet Store |
| что происходило | Audit Ledger |
| каково состояние ресурса сейчас | целевой адаптер |

Ни один контур не читает базу другого. Связь — по `site_id`; домен ключом не
является.

## Где что лежит

| Что | Где | В Git |
|---|---|---|
| Код | `factory/site_engine/changeset/` | да |
| Тесты | `tests/changeset/` | да |
| Хранилище наборов | `/srv/site-factory/changeset-store/changesets.sqlite3` | **нет** |
| Замок процесса, DLQ, ящик | там же | **нет** |
| Ключ подписи одобрений | `/etc/site-factory/control-api.env` | **нет** |

## Служба

```
systemctl status  site-factory-changeset-worker
systemctl restart site-factory-changeset-worker
python -m factory.site_engine.changeset.worker once     # один проход
python -m factory.site_engine.changeset.worker status
```

Процесс держит эксклюзивный замок: второй экземпляр выходит с кодом 3.
Он сливает исходящий ящик в журнал аудита, доводит до конца прерванные
наборы, помечает устаревшие планы и истёкшие одобрения, освобождает
просроченные аренды.

## Применение

Автономное применение в production **выключено**:
`AUTONOMOUS_PRODUCTION_APPLY=DISABLED`. Разрешены окружения `test` и
`non-production`. Включение блокируют долги:

* `REGISTRY_CORE_GIT_PROVENANCE` — код реестра вне Git;
* `OFF_HOST_BACKUP` — копия вне хоста не проверена;
* `LIVE_CONSUMER_ADAPTERS` — реальные адаптеры не подключены.

## Тесты

Только через изолированный прогон:

```
python tests/changeset/run_tests_cs.py
```

Скрипт поднимает отдельный экземпляр API поверх копий баз и собственного
хранилища, а затем сверяет канонические Registry и Audit Ledger до и после.
Прямой `pytest tests/changeset/` пишет в канонические хранилища.

## Если набор требует вмешательства

`MANUAL_INTERVENTION_REQUIRED` означает, что откат не удался и ресурс остался
в неизвестном состоянии. Замок целей при этом **удерживается**: второе
изменение того же ресурса недопустимо, пока человек не разобрался. Снимать
замок вручную можно только после того, как состояние ресурса установлено.
