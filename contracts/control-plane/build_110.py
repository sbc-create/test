#!/usr/bin/env python3
"""Сборка bundle 1.1.0: добавление Audit Ledger к контрактам control plane.

1.1.0, а не 1.0.2: добавлены новые ресурсы, каналы и коды ошибок. Ничего из
1.0.1 не удалено и не переименовано, поэтому старшая цифра не растёт.
"""
from __future__ import annotations
import hashlib, json, shutil, sys
from pathlib import Path

БАЗА = Path(__file__).resolve().parent
ИСТ, НОВ = БАЗА / "1.0.1", БАЗА / "1.1.0"
if НОВ.exists():
    shutil.rmtree(НОВ)
shutil.copytree(ИСТ, НОВ)
ВЕРСИЯ = "1.1.0"
С = "https://contracts.site-factory.internal/1.1.0"


def записать(путь: Path, данные) -> None:
    путь.write_text(json.dumps(данные, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


# Перечни берутся из кода хранилища, а не переписываются сюда руками. Ручная
# копия расходится с реальностью молча — именно так в схему попали фазы и
# результаты, которых служба не знает, и значения, которых схема не знала.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from factory.site_engine.audit import ledger_store as _store

ФАЗЫ = list(_store.ФАЗЫ)
РЕЗУЛЬТАТЫ = list(_store.РЕЗУЛЬТАТЫ)
ТИПЫ_АКТОРОВ = list(_store.ТИПЫ_АКТОРОВ)
ПОЛНОМОЧИЯ = list(_store.ПОЛНОМОЧИЯ)
#: Проверяется в `ledger_store.append`: иных значений служба не принимает.
ОБЛАСТИ = ["SITE", "FLEET"]

# --- схемы -------------------------------------------------------------------
ВРЕМЯ = {"type": "string", "format": "date-time"}
СТРОКА = {"type": ["string", "null"]}
ХЭШ = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
записать(НОВ / "schemas" / "AuditEvent.v1.json", {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": f"{С}/schemas/AuditEvent.v1.json",
    "title": "AuditEvent.v1",
    "description": ("Неизменяемая запись журнала: состоявшийся факт, а не "
                    "желаемое состояние. Журнал не является ни реестром "
                    "сайтов, ни источником истины об их текущем виде. "
                    "Перечень полей совпадает со столбцами хранилища: "
                    "контракт описывает то, что отдаётся, а не то, что "
                    "хотелось бы отдавать."),
    "type": "object",
    "required": ["ledger_seq", "event_id", "schema_version", "event_type",
                 "phase", "result", "received_at", "stored_at",
                 "producer_service", "actor_id", "actor_type", "authority",
                 "scope", "correlation_id", "idempotency_key", "payload_hash",
                 "prev_hash", "event_hash"],
    "additionalProperties": False,
    "properties": {
        "ledger_seq": {"type": "integer", "minimum": 1,
                       "description": "Позиция в журнале; курсор чтения и ключ порядка."},
        "event_id": {"type": "string"},
        "schema_version": {"type": "string"},
        "event_type": {"type": "string"},
        "phase": {"enum": ФАЗЫ},
        "result": {"enum": РЕЗУЛЬТАТЫ, "description": (
            "PENDING и NOT_APPLICABLE — отдельные значения, а не синонимы "
            "FAILURE и не 0: «ещё не известно» и «неприменимо» различаются.")},
        "error_code": СТРОКА,
        "occurred_at": {
            "type": ["string", "null"], "format": "date-time",
            "description": (
                "Когда факт случился у производителя. null означает, что "
                "производитель времени не сообщил; received_at заменой не "
                "является и в это поле не подставляется — иначе время приёма "
                "выдавалось бы за время события.")},
        "received_at": dict(ВРЕМЯ, description="Когда журнал получил запрос."),
        "stored_at": dict(ВРЕМЯ, description="Когда запись зафиксирована. Не подменяет occurred_at."),
        "producer_service": {"type": "string"},
        "producer_instance": СТРОКА,
        "actor_id": {"type": "string"},
        "actor_type": {"enum": ТИПЫ_АКТОРОВ},
        "authority": {"enum": ПОЛНОМОЧИЯ},
        "scope": {"enum": ОБЛАСТИ},
        "environment": СТРОКА,
        "site_id": dict(СТРОКА, description=(
            "Единственный межсервисный ключ сайта. Домен ключом не является "
            "и сюда не пишется.")),
        "resource_type": СТРОКА,
        "resource_id": СТРОКА,
        "resource_owner": СТРОКА,
        "action_id": СТРОКА,
        "change_set_id": СТРОКА,
        "correlation_id": {"type": "string"},
        "causation_id": СТРОКА,
        "idempotency_key": {"type": "string"},
        "prompt_id": СТРОКА,
        "prompt_rev": СТРОКА,
        "run_id": СТРОКА,
        "summary": СТРОКА,
        "before_hash": СТРОКА,
        "after_hash": СТРОКА,
        "commit_sha": СТРОКА,
        "build_id": СТРОКА,
        "release_id": СТРОКА,
        "approval_ref": СТРОКА,
        "rollback_ref": СТРОКА,
        "evidence_refs": {"type": "array", "items": {
            "$ref": f"{С}/schemas/EvidenceRef.json"}},
        "corrects_event_id": dict(СТРОКА, description=(
            "Исправление выполняется новым событием со ссылкой на прежнее: "
            "запись не правится.")),
        "supersedes_event_id": СТРОКА,
        "payload_hash": dict(ХЭШ, description=(
            "Хэш канонического содержимого. Само содержимое в записи не "
            "хранится — это удерживает секреты вне журнала.")),
        "prev_hash": ХЭШ,
        "event_hash": ХЭШ,
    },
})

записать(НОВ / "schemas" / "AuditCheckpoint.v1.json", {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": f"{С}/schemas/AuditCheckpoint.v1.json",
    "title": "AuditCheckpoint.v1",
    "description": ("Подписанная хешем отметка состояния цепи. Уровень защиты "
                    "LOCAL_HASH_CHAIN: обнаруживает изменение задним числом, "
                    "но не защищает от того, кто перепишет всю цепь целиком."),
    "type": "object",
    "required": ["checkpoint_id", "ledger_seq", "chain_root", "event_count",
                 "created_at", "tamper_evidence_level"],
    "additionalProperties": False,
    "properties": {
        "checkpoint_id": {"type": "string"},
        "ledger_seq": {"type": "integer", "minimum": 0},
        "chain_root": ХЭШ,
        "event_count": {"type": "integer", "minimum": 0},
        "created_at": {"type": "string", "format": "date-time"},
        "tamper_evidence_level": {"const": "LOCAL_HASH_CHAIN"},
    },
})

записать(НОВ / "schemas" / "AuditIntegrityReport.v1.json", {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": f"{С}/schemas/AuditIntegrityReport.v1.json",
    "title": "AuditIntegrityReport.v1",
    "type": "object",
    "required": ["ok", "checked_events", "tamper_evidence_level"],
    "additionalProperties": False,
    "properties": {
        "ok": {"type": "boolean"},
        "checked_events": {"type": "integer", "minimum": 0},
        "broken_at_seq": {"type": ["integer", "null"],
                          "description": "Первая позиция, где цепь не сходится."},
        "reason": {"type": ["string", "null"]},
        "tamper_evidence_level": {"const": "LOCAL_HASH_CHAIN"},
        "checked_at": {"type": "string", "format": "date-time"},
    },
})

# --- OpenAPI -----------------------------------------------------------------
oa = json.loads((НОВ / "openapi.json").read_text(encoding="utf-8"))
oa["info"]["version"] = ВЕРСИЯ
ссылка = lambda имя: {"$ref": f"{С}/schemas/{имя}.json"}
проблема = {"content": {"application/problem+json": {"schema": ссылка("Problem.v1")}}}


def ответ(описание, схема=None):
    о = {"description": описание}
    if схема:
        о["content"] = {"application/json": {"schema": схема}}
    return о


oa["paths"]["/api/v1/audit/events"] = {
    "get": {
        "operationId": "listAuditEvents",
        "summary": "Страница журнала по возрастанию ledger_seq",
        "description": ("Фильтрация выполняется на сервере. Неизвестный "
                        "параметр — 422, а не молчаливое игнорирование: "
                        "провайдер не рекламирует того, чего не делает."),
        "parameters": [
            {"name": n, "in": "query", "schema": {"type": "string"}} for n in
            ("site_id", "producer_service", "actor_id", "actor_type", "phase",
             "result", "scope", "event_type", "correlation_id", "action_id",
             "resource_type", "resource_id", "occurred_from", "occurred_to")
        ] + [{"name": "after", "in": "query", "schema": {"type": "integer"}},
             {"name": "limit", "in": "query",
              "schema": {"type": "integer", "minimum": 1, "maximum": 1000}}],
        "responses": {
            "200": ответ("Страница событий", {
                "type": "object",
                "required": ["items", "count"],
                "properties": {
                    "items": {"type": "array", "items": ссылка("AuditEvent.v1")},
                    "count": {"type": "integer"},
                    "next_cursor": {"type": ["integer", "null"]},
                    "has_more": {"type": "boolean"}}}),
            "422": dict(проблема, description="Неизвестный, пустой или противоречивый фильтр"),
        }},
    "post": {
        "operationId": "appendAuditEvent",
        "summary": "Добавить событие",
        "description": ("Идемпотентно по (producer_service, idempotency_key). "
                        "Повтор того же содержимого — 200 с тем же event_id; "
                        "другое содержимое под тем же ключом — 409."),
        "requestBody": {"required": True, "content": {
            "application/json": {"schema": ссылка("AuditEvent.v1")}}},
        "responses": {
            "201": ответ("Событие добавлено"),
            "200": ответ("Идемпотентный повтор; событие уже существует"),
            "401": dict(проблема, description="Нет или неизвестен токен службы"),
            "403": dict(проблема, description="IDENTITY_SPOOF, AUTHORITY_DENIED или MODEL_PHASE_DENIED"),
            "409": dict(проблема, description="IDEMPOTENCY_CONFLICT"),
            "422": dict(проблема, description="SITE_ID_UNKNOWN, SECRET_IN_PAYLOAD или нарушение схемы"),
        }},
    "put": {"operationId": "auditEventsPutDenied", "summary": "Запрещено",
            "description": "Журнал только на добавление.",
            "responses": {"405": dict(проблема, description="APPEND_ONLY")}},
    "patch": {"operationId": "auditEventsPatchDenied", "summary": "Запрещено",
              "description": "Журнал только на добавление.",
              "responses": {"405": dict(проблема, description="APPEND_ONLY")}},
    "delete": {"operationId": "auditEventsDeleteDenied", "summary": "Запрещено",
               "description": "Журнал только на добавление.",
               "responses": {"405": dict(проблема, description="APPEND_ONLY")}},
}
oa["paths"]["/api/v1/audit/events/{event_id}"] = {"get": {
    "operationId": "getAuditEvent",
    "parameters": [{"name": "event_id", "in": "path", "required": True,
                    "schema": {"type": "string"}}],
    "responses": {"200": ответ("Событие", ссылка("AuditEvent.v1")),
                  "404": dict(проблема, description="Не найдено")}}}
oa["paths"]["/api/v1/audit/correlations/{correlation_id}"] = {"get": {
    "operationId": "getAuditCorrelation",
    "summary": "Полная нить действия в порядке фаз",
    "parameters": [{"name": "correlation_id", "in": "path", "required": True,
                    "schema": {"type": "string"}}],
    "responses": {"200": ответ("Нить событий")}}}
oa["paths"]["/api/v1/audit/actions/{action_id}"] = {"get": {
    "operationId": "getAuditAction",
    "parameters": [{"name": "action_id", "in": "path", "required": True,
                    "schema": {"type": "string"}}],
    "responses": {"200": ответ("События действия")}}}
oa["paths"]["/api/v1/audit/integrity"] = {"get": {
    "operationId": "getAuditIntegrity",
    "summary": "Проверка цепи хешей",
    "responses": {"200": ответ("Отчёт", ссылка("AuditIntegrityReport.v1"))}}}
oa["paths"]["/api/v1/audit/checkpoints/latest"] = {"get": {
    "operationId": "getLatestAuditCheckpoint",
    "responses": {"200": ответ("Отметка", ссылка("AuditCheckpoint.v1"))}}}
oa["paths"]["/api/v1/audit/health"] = {"get": {
    "operationId": "getAuditHealth",
    "summary": "Готовность журнала",
    "description": ("Плоскость обслуживания не обязана дожидаться этого "
                    "ответа: недоступность журнала не должна гасить сайты."),
    "responses": {"200": ответ("Состояние")}}}
oa["paths"]["/api/v1/audit/evidence/{evidence_id}/metadata"] = {"get": {
    "operationId": "getEvidenceMetadata",
    "summary": "Метаданные доказательства и результат сверки контрольной суммы",
    "parameters": [{"name": "evidence_id", "in": "path", "required": True,
                    "schema": {"type": "string"}}],
    "responses": {
        "200": ответ("Метаданные; verified=false при расхождении суммы"),
        "403": dict(проблема, description="EVIDENCE_PATH_DENIED"),
        "404": dict(проблема, description="Не найдено")}}}
записать(НОВ / "openapi.json", oa)

# --- AsyncAPI ----------------------------------------------------------------
aa = json.loads((НОВ / "asyncapi.json").read_text(encoding="utf-8"))
aa["info"]["version"] = ВЕРСИЯ
КАНАЛЫ = {
    "audit.event.appended.v1": (
        "Журнал добавил событие. Порождается самим журналом и НИКОГДА не "
        "поглощается им обратно: иначе каждая запись порождала бы запись о "
        "записи и журнал рос бы от самого себя."),
    "audit.integrity.failed.v1":
        "Цепь хешей не сошлась; указана первая расходящаяся позиция.",
    "audit.ingest.failed.v1":
        "Событие производителя не принято и отправлено в DLQ с кодом причины.",
    "audit.action.stalled.v1": (
        "Действие начато, но не завершилось ни успехом, ни откатом за "
        "отведённое время. Это наблюдение, а не вывод о причине."),
    "audit.reconciliation.failed.v1":
        "Сверка с производителем нашла пропуски или дубли.",
    "audit.backup.stale.v1":
        "Последняя проверенная копия старше допустимого возраста.",
}
# Форма канала повторяет 1.0.1: AsyncAPI 2.6 со `subscribe` и x-полями.
# Свой диалект внутри одного бандла заставил бы каждого потребителя разбирать
# два формата.
ПОТРЕБИТЕЛИ = ["architect", "monitoring", "backup", "qwen"]
for имя, описание in КАНАЛЫ.items():
    aa.setdefault("channels", {})[f"fleet/{имя}"] = {
        "subscribe": {
            "operationId": имя.replace(".", "_"),
            "description": описание,
            "x-owner": "architect",
            "x-consumers": ПОТРЕБИТЕЛИ,
            "x-aggregate-key": "correlation_id",
            "x-order-key": "ledger_seq",
            "x-status": "AVAILABLE",
            "x-dedup-key": "event_id",
            "x-retryable": имя != "audit.event.appended.v1",
            "x-evidence-required": имя in ("audit.integrity.failed.v1",
                                           "audit.reconciliation.failed.v1"),
            "x-self-event": имя == "audit.event.appended.v1",
            "message": {
                "name": имя,
                "contentType": "application/json",
                "payload": {"$ref": f"{С}/schemas/EventEnvelope.v1.json"},
            },
        }
    }
aa.setdefault("x-self-event-policy", {
    "suppressed_types": ["audit.event.appended.v1"],
    "rule": ("События, которые журнал порождает о собственной работе, "
             "публикуются в ленту, но не принимаются обратно на запись."),
    "delivery": "at-least-once",
    "consumption": "idempotent",
    "note": ("Ровно-однократная доставка не заявляется: она недостижима, и "
             "обещание её означало бы, что потребители не сделают приём "
             "идемпотентным."),
})
записать(НОВ / "asyncapi.json", aa)

# --- ownership, capabilities, errors -----------------------------------------
om = json.loads((НОВ / "ownership-matrix.json").read_text(encoding="utf-8"))
om.setdefault("resources", []).append({
    "resource": "audit.event",
    "fields": ["event_id", "ledger_seq", "event_type", "phase", "result",
               "scope", "site_id", "actor_id", "authority", "correlation_id",
               "prev_hash", "event_hash"],
    # Единственный писатель — Audit API. Остальные службы добавляют события
    # ЧЕРЕЗ него и в хранилище не пишут: иначе проверять личность и цепь было
    # бы негде.
    "single_writer": "architect",
    "readers": ["architect", "registry", "templates", "seo", "content",
                "monitoring", "backup", "qwen"],
    "commands": ["append"],
    "emits": sorted(КАНАЛЫ),
    "consumes": ["site.registered.v1", "site.updated.v1", "site.activated.v1",
                 "site.retired.v1"],
    "source_of_truth": "audit_ledger.sqlite3 (architect)",
    "retention_owner": "architect",
    "secret_class": "NONE",
    "mutation_policy": ("append-only; UPDATE и DELETE запрещены триггерами БД "
                        "и отвечают 405 APPEND_ONLY"),
    "note": ("Реестр остаётся источником истины о сайтах. Журнал хранит факты "
             "о произошедшем и вторым реестром не является."),
})
записать(НОВ / "ownership-matrix.json", om)

cc = json.loads((НОВ / "capability-catalog.json").read_text(encoding="utf-8"))
cc.setdefault("capabilities", []).extend([
    {"id": "audit.append", "status": "AVAILABLE",
     "description": "Идемпотентное добавление события с проверкой личности и полномочий."},
    {"id": "audit.query", "status": "AVAILABLE",
     "description": "Серверная фильтрация и курсорная разбивка по ledger_seq."},
    {"id": "audit.correlation", "status": "AVAILABLE",
     "description": "Сборка нити действия по correlation_id и action_id."},
    {"id": "audit.integrity", "status": "AVAILABLE",
     "description": "Проверка цепи хешей, уровень LOCAL_HASH_CHAIN."},
    {"id": "audit.backup.local", "status": "AVAILABLE",
     "description": "Копия и проверенное восстановление в изоляции на этом хосте."},
    {"id": "audit.backup.off_host", "status": "PLANNED",
     "description": ("Копия вне хоста. Останется PLANNED, пока восстановление "
                     "на другом хосте не выполнено и не измерено.")},
    {"id": "audit.autonomous_apply", "status": "PLANNED",
     "description": "Автономное применение в production. Владельцем не включено."},
])
записать(НОВ / "capability-catalog.json", cc)

ec = json.loads((НОВ / "error-catalog.json").read_text(encoding="utf-8"))
ec.setdefault("errors", []).extend([
    {"code": "APPEND_ONLY", "http": 405,
     "meaning": "Изменение или удаление записи журнала запрещено."},
    {"code": "IDEMPOTENCY_CONFLICT", "http": 409,
     "meaning": "Ключ идемпотентности уже использован с другим содержимым."},
    {"code": "IDENTITY_SPOOF", "http": 403,
     "meaning": "Заявленная служба не совпадает с личностью, выведенной из токена."},
    {"code": "AUTHORITY_DENIED", "http": 403,
     "meaning": "У службы нет запрошенных полномочий."},
    {"code": "MODEL_PHASE_DENIED", "http": 403,
     "meaning": "Актору типа MODEL недоступны исполнительные фазы."},
    {"code": "SITE_ID_UNKNOWN", "http": 422,
     "meaning": "site_id отсутствует в реестре; домен идентификатором не считается."},
    {"code": "SECRET_IN_PAYLOAD", "http": 422,
     "meaning": "В содержимом обнаружен секрет; событие не принято."},
    {"code": "EVIDENCE_PATH_DENIED", "http": 403,
     "meaning": "Путь доказательства выходит за разрешённые корни."},
    {"code": "FILTER_UNKNOWN", "http": 422,
     "meaning": "Неизвестный параметр фильтра."},
])
записать(НОВ / "error-catalog.json", ec)

# --- наблюдаемость -----------------------------------------------------------
записать(НОВ / "observability.json", {
    "contract": "fleet-audit-observability/1.0.0",
    "metrics": [
        {"name": "audit_events_total", "type": "counter",
         "labels": ["producer_service", "phase", "result"]},
        {"name": "audit_append_rejected_total", "type": "counter",
         "labels": ["error_code"]},
        {"name": "audit_idempotent_replays_total", "type": "counter"},
        {"name": "audit_outbox_backlog", "type": "gauge",
         "note": "Неопубликованные записи ленты."},
        {"name": "audit_dlq_size", "type": "gauge"},
        {"name": "audit_chain_verified_ok", "type": "gauge",
         "note": "1 — цепь сошлась; 0 — нет. Отдельное 'не проверяли' = отсутствие метрики, не 0."},
        {"name": "audit_reconciliation_missing", "type": "gauge",
         "labels": ["producer_service"]},
        {"name": "audit_backup_age_seconds", "type": "gauge",
         "note": "Возраст последней ПРОВЕРЕННОЙ копии, а не последней снятой."},
    ],
    "alerts": [
        {"name": "AuditIntegrityFailed", "expr": "audit_chain_verified_ok == 0",
         "severity": "critical", "channel": "audit.integrity.failed.v1"},
        {"name": "AuditReconciliationGap",
         "expr": "audit_reconciliation_missing > 0", "severity": "critical",
         "channel": "audit.reconciliation.failed.v1"},
        {"name": "AuditOutboxBacklog", "expr": "audit_outbox_backlog > 100",
         "for": "15m", "severity": "warning"},
        {"name": "AuditDlqNonEmpty", "expr": "audit_dlq_size > 0",
         "severity": "warning", "channel": "audit.ingest.failed.v1"},
        {"name": "AuditBackupStale", "expr": "audit_backup_age_seconds > 172800",
         "severity": "warning", "channel": "audit.backup.stale.v1"},
    ],
    "scope": "internal",
    "note": ("Контур внутренний. Счётчики Метрики и проекты Topvisor не "
             "создаются и этим контрактом не затрагиваются."),
})

# --- манифест и контрольные суммы -------------------------------------------
m = json.loads((НОВ / "manifest.json").read_text(encoding="utf-8"))
m["version"] = ВЕРСИЯ
m["contract"] = "fleet-control-plane-contracts/1.1.0"
m.setdefault("includes", []) if isinstance(m.get("includes"), list) else None
записать(НОВ / "manifest.json", m)

суммы = {}
for p in sorted(НОВ.rglob("*")):
    if p.is_file() and p.name not in ("checksums.json", "_partial-checksums.json"):
        суммы[str(p.relative_to(НОВ))] = hashlib.sha256(p.read_bytes()).hexdigest()
записать(НОВ / "checksums.json", {"version": ВЕРСИЯ, "algorithm": "sha256",
                                  "files": суммы})
(НОВ / "_partial-checksums.json").unlink(missing_ok=True)

(НОВ / "CHANGELOG.md").write_text(
    "# CHANGELOG\n\n## 1.1.0\n\n"
    "Добавлен Audit/Action Ledger. Изменение аддитивное: ни один ресурс, путь "
    "или код ошибки версии 1.0.1 не удалён и не переименован, поэтому "
    "потребители 1.0.1 продолжают работать без правок.\n\n"
    "* схемы `AuditEvent.v1`, `AuditCheckpoint.v1`, `AuditIntegrityReport.v1`;\n"
    "* восемь путей `/api/v1/audit/*`, включая явные 405 на PUT/PATCH/DELETE;\n"
    "* шесть каналов `audit.*` и политика самоподавления `audit.event.appended.v1`;\n"
    "* ресурс `audit_event` в матрице владения, режим APPEND_ONLY;\n"
    "* девять кодов ошибок журнала;\n"
    "* `observability.json` — внутренние метрики и контракты алертов.\n\n"
    "Не заявлено: ровно-однократная доставка; защита от переписывания всей "
    "цепи целиком (уровень — LOCAL_HASH_CHAIN); копия вне хоста "
    "(`audit.backup.off_host` остаётся PLANNED).\n\n"
    + (ИСТ / "CHANGELOG.md").read_text(encoding="utf-8").replace("# CHANGELOG\n", "", 1),
    encoding="utf-8")

print(json.dumps({"version": ВЕРСИЯ, "files": len(суммы),
                  "openapi_paths": len(oa["paths"]),
                  "asyncapi_channels": len(aa["channels"]),
                  "schemas": len(list((НОВ / "schemas").glob("*.json")))},
                 ensure_ascii=False))
