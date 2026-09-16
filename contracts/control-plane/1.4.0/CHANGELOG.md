## 1.4.0 — 2026-09-16

Добавлены состояния APPLIED, VERIFIED и ROLLBACK_REQUESTED. Прежде «эффект
создан» и «эффект подтверждён наблюдением» были одним состоянием, а
различаются они последствиями: после первого нужен откат, после второго нет.

risk_class сменил значения с LOW/MEDIUM/HIGH на R0–R4. Прежняя шкала отвечала
на вопрос «сколько и где», а читалась как «что затронуто». Ширина охвата
осталась отдельным полем impact_level.

Добавлены expected_resource_version и заголовки If-Match/ETag: отправитель
теперь может сказать, на какую картину мира он опирается, и не применить
изменение поверх того, чего не видел. Добавлен request_id.

Новые коды ошибок: VERSION_CONFLICT, EXPECTED_VERSION_INVALID,
FILTER_VALUE_UNKNOWN, EVENT_VERSION_UNKNOWN, LEDGER_UNAVAILABLE_EXHAUSTED.

Замена значений risk_class — неаддитивное изменение, поэтому растёт минорная
версия. 1.3.1 остаётся на месте: читающие по нему работают, пока не перейдут.

# CHANGELOG

## 1.3.0

Контур ChangeSet/Workflow введён в строй.

Маршруты `/api/v1/changesets` и `/api/v1/workflows` и каналы `changeset.*` были объявлены заглушками со статусом PLANNED и ответом 501 ещё в 1.0.1. Здесь они НАПОЛНЯЮТСЯ, а не создаются заново: дублирующий API рядом с объявленным означал бы, что потребитель однажды выберет не тот.

* схемы `ChangeSet.v1`, `ChangeSetTarget.v1`, `ChangeSetTransition.v1`, `Approval.v1`, `AdapterCapabilities.v1`;
* семь действий над набором отдельными маршрутами; `status` в запросе не принимается, PUT/PATCH/DELETE отвечают 405 `ACTION_ONLY`;
* 19 каналов переходов переведены в AVAILABLE;
* ресурс `changeset` в матрице владения, единственный писатель — control-plane;
* двадцать один код ошибок контура.

Не заявлено и намеренно выключено: применение в production (`changeset.production_apply` — PLANNED), реальные адаптеры Templates, Content и SEO (PLANNED), необратимые операции.


## 1.2.0

Разделены сырая лента журнала и рабочая проекция.

Минорная версия, а не патч: добавлена новая внешняя возможность (`/api/v1/audit/operational/events`), добавлены события карантина, и чтение сырой ленты теперь требует роли `audit-admin` — последнее меняет поведение уже объявленного маршрута, и умолчать об этом в номере версии нельзя.

* схемы `QuarantineDecision.v1`, `ProjectionState.v1`;
* пути `/api/v1/audit/operational/events` и `/api/v1/audit/projection`;
* `include_quarantined` — только для роли `audit-admin`;
* `actions/{id}` и `correlations/{id}` по умолчанию рабочие, с полем `quarantined_count`;
* каналы `audit.event_set.quarantined.v1`, `audit.event_set.quarantine_revoked.v1`, `audit.projection.rebuilt.v1`;
* ресурс `audit.operational_projection` в матрице владения;
* коды `ROLE_DENIED` и `TOKEN_REVOKED`.

Совместимость: потребители 1.1.0, читавшие сырую ленту без токена, обязаны предъявить токен с ролью `audit-admin` либо перейти на операционную поверхность. Это единственное ломающее изменение, и оно намеренное: рабочие решения не должны приниматься по ленте, содержащей заведомо непригодные записи.


## 1.1.0

Добавлен Audit/Action Ledger. Изменение аддитивное: ни один ресурс, путь или код ошибки версии 1.0.1 не удалён и не переименован, поэтому потребители 1.0.1 продолжают работать без правок.

* схемы `AuditEvent.v1`, `AuditCheckpoint.v1`, `AuditIntegrityReport.v1`;
* восемь путей `/api/v1/audit/*`, включая явные 405 на PUT/PATCH/DELETE;
* шесть каналов `audit.*` и политика самоподавления `audit.event.appended.v1`;
* ресурс `audit_event` в матрице владения, режим APPEND_ONLY;
* девять кодов ошибок журнала;
* `observability.json` — внутренние метрики и контракты алертов.

Не заявлено: ровно-однократная доставка; защита от переписывания всей цепи целиком (уровень — LOCAL_HASH_CHAIN); копия вне хоста (`audit.backup.off_host` остаётся PLANNED).

# fleet-control-plane-contracts

## 1.0.0 — 2026-09-11T14:04:52Z

Первая версия. Ломать нечего: предыдущих версий bundle не существовало.

Включено:

* 13 базовых схем: SiteRef, ActorRef, ObservedValue, CorrelationContext,
  VersionRef, EvidenceRef, DesiredObservedState, CommandEnvelope.v1,
  CommandReceipt.v1, EventEnvelope.v1, Problem.v1, Page.v1, Capability.v1;
* OpenAPI на 22 пути, из них 8 — зарезервированные пространства имён со
  статусом PLANNED и без адресов;
* AsyncAPI на 28 каналов: 4 существующих события реестра со статусом
  AVAILABLE и 24 объявленных со статусом PLANNED;
* матрица владения на 9 ресурсов, ни у одного нет двух писателей;
* каталог возможностей: 7 AVAILABLE после живой проверки, 12 PLANNED;
* каталог ошибок и правил надёжности.

Совместимость с существующим Registry сохранена: `GET /api/v1/sites`
продолжает отдавать прежние четыре ключа, новые поля добавлены аддитивно.

### Известный разрыв

`SITES_QUERY_FILTER_NOT_APPLIED` — параметры `environment` и
`lifecycle_state` у `/api/v1/sites` объявлены, но провайдером не
применяются. Помечены в OpenAPI как PLANNED. Каноническим источником
ACTIVE production служит `/api/v1/registry/snapshot`, и референсные клиенты
берут девять сайтов именно оттуда. Исправление требует аддитивной правки
Control API и ждёт разрешения владельца.
