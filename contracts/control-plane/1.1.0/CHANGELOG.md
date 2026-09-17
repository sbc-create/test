# CHANGELOG

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
