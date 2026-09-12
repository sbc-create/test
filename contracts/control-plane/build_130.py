#!/usr/bin/env python3
"""Сборка bundle 1.3.0: контур изменений переходит из PLANNED в AVAILABLE.

Изменение аддитивное. Маршруты `/api/v1/changesets` и `/api/v1/workflows` и
каналы `changeset.*` были объявлены в 1.0.1 заглушками со статусом PLANNED и
ответом 501. Здесь они наполняются, а не создаются заново: дублирующий API
рядом с объявленным означал бы, что потребитель однажды выберет не тот.
"""
from __future__ import annotations

import hashlib, json, shutil, sys
from pathlib import Path

БАЗА = Path(__file__).resolve().parent
ИСТ, НОВ = БАЗА / "1.2.0", БАЗА / "1.3.0"
if not ИСТ.exists():
    sys.exit("нет исходного бандла 1.2.0")
if НОВ.exists():
    shutil.rmtree(НОВ)
shutil.copytree(ИСТ, НОВ)
ВЕРСИЯ = "1.3.0"
С = f"https://contracts.site-factory.internal/{ВЕРСИЯ}"

sys.path.insert(0, str(БАЗА.parents[1]))
from factory.site_engine.changeset import model as M
from factory.site_engine.changeset import policy as POL


def записать(путь: Path, данные) -> None:
    путь.write_text(json.dumps(данные, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def перецелить(узел):
    if isinstance(узел, dict):
        return {k: (v.replace("/1.2.0/", f"/{ВЕРСИЯ}/")
                    if k == "$ref" and isinstance(v, str) else перецелить(v))
                for k, v in узел.items()}
    if isinstance(узел, list):
        return [перецелить(x) for x in узел]
    return узел


for p in (НОВ / "schemas").glob("*.json"):
    d = json.loads(p.read_text(encoding="utf-8"))
    d["$id"] = d["$id"].replace("/1.2.0/", f"/{ВЕРСИЯ}/")
    записать(p, перецелить(d))

# --- схемы -------------------------------------------------------------------
записать(НОВ / "schemas" / "ChangeSet.v1.json", {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": f"{С}/schemas/ChangeSet.v1.json",
    "title": "ChangeSet.v1",
    "description": (
        "Предложение изменения и ход его исполнения. Поле status только "
        "читается: состояние вычисляет сервер по таблице переходов, и задать "
        "его в запросе нельзя — иначе машина состояний стала бы "
        "рекомендацией."),
    "type": "object",
    "required": ["changeset_id", "schema_version", "status", "version",
                 "resource_type", "resource_id", "operation_type",
                 "target_site_ids", "producer_service", "actor_id",
                 "actor_type", "idempotency_key", "correlation_id",
                 "requested_change", "created_at", "updated_at"],
    "additionalProperties": False,
    "properties": {
        "changeset_id": {"type": "string", "format": "uuid"},
        "schema_version": {"const": M.SCHEMA_VERSION},
        "status": {"enum": list(M.СОСТОЯНИЯ), "readOnly": True},
        "version": {"type": "integer", "minimum": 1,
                    "description": "Оптимистическая блокировка набора."},
        "resource_type": {"type": "string"},
        "resource_id": {"type": "string"},
        "operation_type": {"enum": sorted(M.ОПЕРАЦИИ)},
        "target_site_ids": {"type": "array", "minItems": 1,
                            "items": {"type": "string"},
                            "description": "Только site_id; домен ключом не является."},
        "canary_site_ids": {"type": "array", "items": {"type": "string"},
                            "description": "Подмножество целей, применяемое первым."},
        "producer_service": {"type": "string"},
        "actor_id": {"type": "string"},
        "actor_type": {"enum": ["SERVICE", "HUMAN", "MODEL"]},
        "idempotency_key": {"type": "string"},
        "correlation_id": {"type": "string"},
        "causation_id": {"type": ["string", "null"]},
        "base_registry_version": {"type": ["integer", "null"]},
        "expected_resource_fingerprint": {"type": ["string", "null"]},
        "requested_change": {"type": "object",
                             "description": "Данные, а не программа: команды, "
                                            "пути, адреса и SQL отклоняются."},
        "risk_class": {"type": ["string", "null"], "enum": [*M.КЛАССЫ_РИСКА, None]},
        "policy_version": {"type": ["string", "null"]},
        "plan_hash": {"type": ["string", "null"], "pattern": "^[0-9a-f]{64}$"},
        "expires_at": {"type": ["string", "null"], "format": "date-time"},
        "dry_run_result": {"type": ["object", "null"]},
        "verification_plan": {"type": ["object", "null"]},
        "rollback_plan": {"type": ["object", "null"]},
        "approval": {"anyOf": [{"$ref": f"{С}/schemas/Approval.v1.json"},
                               {"type": "null"}]},
        "evidence_refs": {"type": "array", "items": {
            "$ref": f"{С}/schemas/EvidenceRef.json"}},
        "failure_reason": {"type": ["string", "null"]},
        "targets": {"type": "array", "items": {
            "$ref": f"{С}/schemas/ChangeSetTarget.v1.json"}},
        "transitions": {"type": "array", "items": {
            "$ref": f"{С}/schemas/ChangeSetTransition.v1.json"}},
        "created_at": {"type": "string", "format": "date-time"},
        "updated_at": {"type": "string", "format": "date-time"},
    },
})

записать(НОВ / "schemas" / "ChangeSetTarget.v1.json", {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": f"{С}/schemas/ChangeSetTarget.v1.json",
    "title": "ChangeSetTarget.v1",
    "description": "Состояние одной цели. Отпечатки «до» и «после» — то, по "
                   "чему проверяется успех и строится откат.",
    "type": "object",
    "required": ["changeset_id", "site_id", "state"],
    "additionalProperties": False,
    "properties": {
        "changeset_id": {"type": "string"},
        "site_id": {"type": "string"},
        "is_canary": {"type": "integer", "enum": [0, 1]},
        "state": {"enum": ["PENDING", "APPLYING", "SUCCEEDED", "APPLY_FAILED",
                           "VERIFY_FAILED", "ROLLED_BACK", "ROLLBACK_FAILED"]},
        "before_fingerprint": {"type": ["string", "null"]},
        "after_fingerprint": {"type": ["string", "null"]},
        "attempts": {"type": "integer", "minimum": 0},
        "detail": {"type": ["string", "null"]},
        "updated_at": {"type": "string", "format": "date-time"},
    },
})

записать(НОВ / "schemas" / "ChangeSetTransition.v1.json", {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": f"{С}/schemas/ChangeSetTransition.v1.json",
    "title": "ChangeSetTransition.v1",
    "description": "Один состоявшийся переход. Записи не изменяются и не "
                   "удаляются: история решений сохраняется целиком.",
    "type": "object",
    "required": ["changeset_id", "action", "from_status", "to_status",
                 "actor_id", "actor_role", "occurred_at"],
    "additionalProperties": False,
    "properties": {
        "seq": {"type": "integer"},
        "changeset_id": {"type": "string"},
        "action": {"type": "string"},
        "from_status": {"enum": list(M.СОСТОЯНИЯ)},
        "to_status": {"enum": list(M.СОСТОЯНИЯ)},
        "actor_id": {"type": "string"},
        "actor_role": {"enum": [M.PROPOSER, M.VALIDATOR, M.APPROVER,
                                M.EXECUTOR, M.OPERATOR]},
        "reason": {"type": ["string", "null"]},
        "before_fingerprint": {"type": ["string", "null"]},
        "after_fingerprint": {"type": ["string", "null"]},
        "correlation_id": {"type": "string"},
        "causation_id": {"type": ["string", "null"]},
        "occurred_at": {"type": "string", "format": "date-time"},
    },
})

записать(НОВ / "schemas" / "Approval.v1.json", {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": f"{С}/schemas/Approval.v1.json",
    "title": "Approval.v1",
    "description": (
        "Разрешение на КОНКРЕТНЫЙ план для КОНКРЕТНЫХ целей. Поле binding "
        "перечисляет всё, изменение чего обязано аннулировать разрешение; "
        "signature связывает его арифметически, а не обещанием исполнителя."),
    "type": "object",
    "required": ["approver_id", "approver_service", "approver_type",
                 "approved_at", "expires_at", "policy_version", "binding",
                 "signature"],
    "additionalProperties": False,
    "properties": {
        "approver_id": {"type": "string"},
        "approver_service": {"type": "string"},
        "approver_type": {"enum": ["SERVICE", "HUMAN"],
                          "description": "MODEL отсутствует намеренно: "
                                         "модель не одобряет изменения."},
        "approved_at": {"type": "string", "format": "date-time"},
        "expires_at": {"type": "string", "format": "date-time"},
        "reason": {"type": ["string", "null"]},
        "policy_version": {"type": "string"},
        "binding": {"type": "object"},
        "signature": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "revoked_at": {"type": ["string", "null"], "format": "date-time"},
        "revoked_by": {"type": ["string", "null"]},
    },
})

записать(НОВ / "schemas" / "AdapterCapabilities.v1.json", {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": f"{С}/schemas/AdapterCapabilities.v1.json",
    "title": "AdapterCapabilities.v1",
    "description": "Что умеет целевой адаптер. Реальные адаптеры Templates, "
                   "Content, SEO и провайдеров в 1.3.0 не подключены.",
    "type": "object",
    "required": ["adapter", "owner_service", "resource_types", "operations",
                 "supports_dry_run", "supports_observe", "supports_rollback"],
    "additionalProperties": True,
    "properties": {
        "adapter": {"type": "string"},
        "owner_service": {"type": "string"},
        "resource_types": {"type": "array", "items": {"type": "string"}},
        "operations": {"type": "array", "items": {"type": "string"}},
        "reversible_operations": {"type": "array", "items": {"type": "string"}},
        "supports_dry_run": {"type": "boolean"},
        "supports_observe": {"type": "boolean"},
        "supports_rollback": {"type": "boolean"},
        "environment": {"type": "string"},
    },
})

# --- OpenAPI -----------------------------------------------------------------
oa = перецелить(json.loads((НОВ / "openapi.json").read_text(encoding="utf-8")))
oa["info"]["version"] = ВЕРСИЯ
ссылка = lambda имя: {"$ref": f"{С}/schemas/{имя}.json"}
проблема = {"content": {"application/problem+json": {"schema": ссылка("Problem.v1")}}}

ФИЛЬТРЫ = ("status", "resource_type", "resource_id", "producer_service",
           "actor_id", "risk_class", "site_id", "correlation_id")
oa["paths"]["/api/v1/changesets"] = {
    "get": {
        "operationId": "listChangeSets",
        "summary": "Наборы изменений",
        "x-owner": "control-plane", "x-status": "AVAILABLE",
        "description": "Фильтрация серверная; неизвестный параметр — 422.",
        "parameters": [{"name": n, "in": "query", "schema": {"type": "string"}}
                       for n in ФИЛЬТРЫ]
        + [{"name": "after", "in": "query", "schema": {"type": "integer"}},
           {"name": "limit", "in": "query", "schema": {"type": "integer"}}],
        "responses": {
            "200": {"description": "Страница наборов"},
            "401": dict(проблема, description="Токен не предъявлен"),
            "422": dict(проблема, description="Неизвестный или пустой фильтр")}},
    "post": {
        "operationId": "proposeChangeSet",
        "summary": "Предложить изменение",
        "x-owner": "control-plane", "x-status": "AVAILABLE",
        "description": (
            "Создаёт набор в состоянии PROPOSED. Идемпотентно по "
            "(producer_service, idempotency_key). Поле status в запросе не "
            "принимается."),
        "requestBody": {"required": True, "content": {
            "application/json": {"schema": ссылка("ChangeSet.v1")}}},
        "responses": {
            "201": {"description": "Набор создан"},
            "200": {"description": "Идемпотентный повтор"},
            "401": dict(проблема, description="Токен не предъявлен"),
            "403": dict(проблема, description="ROLE_NOT_GRANTED"),
            "409": dict(проблема, description="IDEMPOTENCY_CONFLICT"),
            "422": dict(проблема, description="STATUS_NOT_WRITABLE, "
                                              "FIELD_REQUIRED или PAYLOAD_REJECTED")}},
}
for метод, код in (("put", "ACTION_ONLY"), ("patch", "ACTION_ONLY"),
                   ("delete", "ACTION_ONLY")):
    oa["paths"]["/api/v1/changesets"][метод] = {
        "operationId": f"changeSets{метод.title()}Denied",
        "summary": "Запрещено",
        "description": "Набор не редактируется и не удаляется: состояние "
                       "меняется только действиями, история сохраняется.",
        "responses": {"405": dict(проблема, description=код)}}

oa["paths"]["/api/v1/changesets/{changeset_id}"] = {"get": {
    "operationId": "getChangeSet", "x-status": "AVAILABLE",
    "parameters": [{"name": "changeset_id", "in": "path", "required": True,
                    "schema": {"type": "string"}}],
    "responses": {"200": {"description": "Набор",
                          "content": {"application/json": {
                              "schema": ссылка("ChangeSet.v1")}}},
                  "404": dict(проблема, description="CHANGESET_NOT_FOUND")}}}
oa["paths"]["/api/v1/changesets/{changeset_id}/transitions"] = {"get": {
    "operationId": "listChangeSetTransitions", "x-status": "AVAILABLE",
    "summary": "История переходов набора",
    "parameters": [{"name": "changeset_id", "in": "path", "required": True,
                    "schema": {"type": "string"}}],
    "responses": {"200": {"description": "Переходы"},
                  "404": dict(проблема, description="CHANGESET_NOT_FOUND")}}}

ДЕЙСТВИЯ = {
    "validate": ("Проверить и построить план", "validator",
                 "Выполняет схемную проверку, сверку site_id с реестром, "
                 "детерминированный diff, классификацию риска, план проверки, "
                 "план отката и сухой прогон. Эффектов не создаёт."),
    "approve": ("Одобрить", "approver",
                "Требует expires_at. Одобряющий не может совпадать с "
                "предложившим. Разрешение связывается хэшем с планом и целями."),
    "reject": ("Отклонить", "approver", "Терминальное решение."),
    "revoke-approval": ("Отозвать одобрение", "approver",
                        "Запись не стирается, а помечается недействительной."),
    "apply": ("Применить", "executor",
              "Повторно проверяет одобрение, версию реестра и отпечатки целей. "
              "Канарейка применяется первой; при её отказе остальные цели не "
              "затрагиваются. Требует действующей аренды и маркера ограждения."),
    "rollback": ("Откатить", "executor",
                 "Идемпотентная компенсация с проверкой восстановленного "
                 "состояния."),
    "cancel": ("Отменить предложение", "proposer",
               "Доступно до применения."),
}
for действие, (сводка, роль, описание) in ДЕЙСТВИЯ.items():
    oa["paths"][f"/api/v1/changesets/{{changeset_id}}/{действие}"] = {"post": {
        "operationId": "changeSet" + действие.title().replace("-", ""),
        "summary": сводка, "description": описание,
        "x-required-role": роль, "x-status": "AVAILABLE",
        "parameters": [{"name": "changeset_id", "in": "path", "required": True,
                        "schema": {"type": "string"}}],
        "responses": {
            "200": {"description": "Действие выполнено"},
            "401": dict(проблема, description="Токен не предъявлен"),
            "403": dict(проблема, description="ROLE_NOT_GRANTED, "
                                              "MODEL_ACTION_DENIED, "
                                              "SEPARATION_OF_DUTIES, "
                                              "APPROVAL_EXPIRED или "
                                              "AUTONOMOUS_PRODUCTION_APPLY_DISABLED"),
            "404": dict(проблема, description="CHANGESET_NOT_FOUND"),
            "409": dict(проблема, description="TRANSITION_NOT_ALLOWED, "
                                              "LOCK_CONFLICT, FENCED_OUT, "
                                              "PLAN_STALE или VERSION_CONFLICT"),
            "422": dict(проблема, description="Нарушение валидации"),
            "503": dict(проблема, description="AUDIT_LEDGER_UNAVAILABLE или "
                                              "REGISTRY_UNAVAILABLE")}}}

oa["paths"]["/api/v1/workflows"] = {"get": {
    "operationId": "getWorkflowState",
    "summary": "Состояние контура изменений",
    "x-owner": "control-plane", "x-status": "AVAILABLE",
    "description": "Наборы по состояниям, задолженность ящика, аренды, "
                   "подключённые адаптеры и признак автономного применения.",
    "responses": {"200": {"description": "Состояние"}}}}
записать(НОВ / "openapi.json", oa)

# --- AsyncAPI ----------------------------------------------------------------
aa = перецелить(json.loads((НОВ / "asyncapi.json").read_text(encoding="utf-8")))
aa["info"]["version"] = ВЕРСИЯ
СОБЫТИЯ_ПЕРЕХОДОВ = sorted({п.событие for п in M.ПЕРЕХОДЫ if п.событие}
                           | {"changeset.proposed.v1"})
ПОТРЕБИТЕЛИ = ["architect", "templates", "seo", "content", "monitoring",
               "backup", "qwen"]
for имя in СОБЫТИЯ_ПЕРЕХОДОВ:
    ключ = f"fleet/{имя}"
    прежний = aa["channels"].get(ключ, {}).get("subscribe", {})
    aa["channels"][ключ] = {"subscribe": {
        "operationId": имя.replace(".", "_"),
        "description": прежний.get("description")
        or f"Набор изменений перешёл в состояние, соответствующее {имя}.",
        "x-owner": "control-plane",
        "x-consumers": прежний.get("x-consumers") or ПОТРЕБИТЕЛИ,
        "x-aggregate-key": "changeset_id",
        "x-order-key": "changeset_id",
        "x-status": "AVAILABLE",
        "x-dedup-key": "idempotency_key",
        "x-retryable": True,
        "x-evidence-required": имя in ("changeset.applied.v1",
                                       "changeset.succeeded.v1",
                                       "changeset.rolled_back.v1",
                                       "changeset.rollback_failed.v1"),
        "message": {"name": имя, "contentType": "application/json",
                    "payload": {"$ref": f"{С}/schemas/EventEnvelope.v1.json"}},
    }}
for имя in ("workflow.started.v1", "workflow.completed.v1",
            "workflow.blocked.v1"):
    aa["channels"][f"fleet/{имя}"]["subscribe"]["x-status"] = "AVAILABLE"
    aa["channels"][f"fleet/{имя}"]["subscribe"]["x-owner"] = "control-plane"
записать(НОВ / "asyncapi.json", aa)

# --- возможности, ошибки, владение -------------------------------------------
cc = json.loads((НОВ / "capability-catalog.json").read_text(encoding="utf-8"))
cc["capabilities"].extend([
    {"capability_id": "changeset.propose", "owner_service": "control-plane",
     "version": ВЕРСИЯ, "status": "AVAILABLE",
     "read_endpoint": "/api/v1/changesets",
     "command_endpoint": "/api/v1/changesets",
     "event_types": ["changeset.proposed.v1"],
     "required_scopes": ["changeset:propose"], "dependencies": ["registry.sites.filter"]},
    {"capability_id": "changeset.validate", "owner_service": "control-plane",
     "version": ВЕРСИЯ, "status": "AVAILABLE",
     "read_endpoint": "/api/v1/changesets/{changeset_id}",
     "command_endpoint": "/api/v1/changesets/{changeset_id}/validate",
     "event_types": ["changeset.validated.v1", "changeset.validation_failed.v1"],
     "required_scopes": ["changeset:validate"], "dependencies": []},
    {"capability_id": "changeset.approve", "owner_service": "control-plane",
     "version": ВЕРСИЯ, "status": "AVAILABLE",
     "read_endpoint": "/api/v1/changesets/{changeset_id}",
     "command_endpoint": "/api/v1/changesets/{changeset_id}/approve",
     "event_types": ["changeset.approved.v1", "changeset.rejected.v1"],
     "required_scopes": ["changeset:approve"], "dependencies": []},
    {"capability_id": "changeset.apply", "owner_service": "control-plane",
     "version": ВЕРСИЯ, "status": "AVAILABLE",
     "read_endpoint": "/api/v1/workflows",
     "command_endpoint": "/api/v1/changesets/{changeset_id}/apply",
     "event_types": ["changeset.applied.v1", "changeset.succeeded.v1"],
     "required_scopes": ["changeset:apply"],
     "dependencies": ["audit.append", "registry.sites.filter"]},
    {"capability_id": "changeset.rollback", "owner_service": "control-plane",
     "version": ВЕРСИЯ, "status": "AVAILABLE",
     "read_endpoint": "/api/v1/changesets/{changeset_id}",
     "command_endpoint": "/api/v1/changesets/{changeset_id}/rollback",
     "event_types": ["changeset.rolled_back.v1", "changeset.rollback_failed.v1"],
     "required_scopes": ["changeset:apply"], "dependencies": []},
    {"capability_id": "changeset.production_apply", "owner_service": "control-plane",
     "version": ВЕРСИЯ, "status": "PLANNED",
     "read_endpoint": None, "command_endpoint": None, "event_types": [],
     "required_scopes": ["changeset:apply:production"],
     "dependencies": list(POL.ДОЛГИ_БЛОКИРУЮЩИЕ_АВТОНОМИЮ),
     "note": "Выключено: применение в production требует закрытия долгов."},
    {"capability_id": "changeset.adapter.templates", "owner_service": "templates",
     "version": ВЕРСИЯ, "status": "PLANNED",
     "read_endpoint": None, "command_endpoint": None, "event_types": [],
     "required_scopes": [], "dependencies": ["changeset.apply"],
     "note": "Реальный адаптер не подключён."},
    {"capability_id": "changeset.adapter.content", "owner_service": "content",
     "version": ВЕРСИЯ, "status": "PLANNED",
     "read_endpoint": None, "command_endpoint": None, "event_types": [],
     "required_scopes": [], "dependencies": ["changeset.apply"],
     "note": "Реальный адаптер не подключён."},
    {"capability_id": "changeset.adapter.seo", "owner_service": "seo",
     "version": ВЕРСИЯ, "status": "PLANNED",
     "read_endpoint": None, "command_endpoint": None, "event_types": [],
     "required_scopes": [], "dependencies": ["changeset.apply"],
     "note": "Реальный адаптер не подключён."},
])
cc["bundle_version"] = ВЕРСИЯ
cc["count"] = len(cc["capabilities"])
cc["available"] = sum(1 for x in cc["capabilities"] if x.get("status") == "AVAILABLE")
cc["planned"] = sum(1 for x in cc["capabilities"] if x.get("status") == "PLANNED")
записать(НОВ / "capability-catalog.json", cc)

ec = json.loads((НОВ / "error-catalog.json").read_text(encoding="utf-8"))
ec["errors"].extend([
    {"code": "ACTION_ONLY", "http": 405,
     "meaning": "Набор изменяется только действиями; правка и удаление запрещены."},
    {"code": "STATUS_NOT_WRITABLE", "http": 422,
     "meaning": "Состояние вычисляется сервером и в запросе не задаётся."},
    {"code": "TRANSITION_NOT_ALLOWED", "http": 409,
     "meaning": "Из текущего состояния такое действие не предусмотрено."},
    {"code": "ROLE_NOT_GRANTED", "http": 403,
     "meaning": "У службы нет роли, требуемой этим действием."},
    {"code": "MODEL_ACTION_DENIED", "http": 403,
     "meaning": "Актору-модели закрыты approve, apply, rollback и выдача полномочий."},
    {"code": "SEPARATION_OF_DUTIES", "http": 403,
     "meaning": "Предложивший изменение не может сам его одобрить."},
    {"code": "APPROVAL_REQUIRED", "http": 403, "meaning": "Изменение не одобрено."},
    {"code": "APPROVAL_EXPIRED", "http": 403, "meaning": "Срок одобрения истёк."},
    {"code": "APPROVAL_REVOKED", "http": 403, "meaning": "Одобрение отозвано."},
    {"code": "APPROVAL_BINDING_MISMATCH", "http": 409,
     "meaning": "После одобрения изменился план, цели или иная связанная величина."},
    {"code": "APPROVAL_SIGNATURE_INVALID", "http": 403,
     "meaning": "Подпись одобрения не совпала."},
    {"code": "PLAN_STALE", "http": 409,
     "meaning": "Версия реестра или отпечаток цели разошлись с планом."},
    {"code": "LOCK_CONFLICT", "http": 409,
     "meaning": "Цель уже изменяется другим набором."},
    {"code": "FENCED_OUT", "http": 409,
     "meaning": "Предъявлен устаревший маркер ограждения."},
    {"code": "LEASE_HELD", "http": 409, "meaning": "Аренда у другого исполнителя."},
    {"code": "VERSION_CONFLICT", "http": 409,
     "meaning": "Версия набора изменилась между чтением и записью."},
    {"code": "IRREVERSIBLE_OPERATION", "http": 422,
     "meaning": "Необратимые операции в этой версии не выполняются."},
    {"code": "PAYLOAD_REJECTED", "http": 422,
     "meaning": "В содержимом обнаружены путь, команда, адрес или SQL."},
    {"code": "AUTONOMOUS_PRODUCTION_APPLY_DISABLED", "http": 403,
     "meaning": "Применение вне test и non-production выключено."},
    {"code": "AUDIT_LEDGER_UNAVAILABLE", "http": 503,
     "meaning": "Журнал аудита недоступен; изменения заблокированы."},
    {"code": "REGISTRY_UNAVAILABLE", "http": 503, "meaning": "Реестр недоступен."},
])
записать(НОВ / "error-catalog.json", ec)

om = json.loads((НОВ / "ownership-matrix.json").read_text(encoding="utf-8"))
om["resources"].append({
    "resource": "changeset",
    "fields": ["changeset_id", "status", "plan_hash", "approval",
               "target_site_ids", "risk_class"],
    "single_writer": "control-plane",
    "readers": ["architect", "templates", "seo", "content", "monitoring",
                "backup", "qwen"],
    "commands": sorted(ДЕЙСТВИЯ),
    "emits": СОБЫТИЯ_ПЕРЕХОДОВ,
    "consumes": ["site.registered.v1", "site.updated.v1", "site.retired.v1"],
    "source_of_truth": "changesets.sqlite3 (control-plane)",
    "retention_owner": "control-plane",
    "secret_class": "NONE",
    "mutation_policy": "только машина переходов; прямая запись status "
                       "запрещена триггером БД",
    "note": "Реестр остаётся источником истины о сайтах, журнал аудита — об "
            "истории. Хранилище наборов хранит только ход предложения.",
})
записать(НОВ / "ownership-matrix.json", om)

# --- манифест и суммы --------------------------------------------------------
m = json.loads((НОВ / "manifest.json").read_text(encoding="utf-8"))
m["version"] = ВЕРСИЯ
m["contract"] = f"fleet-control-plane-contracts/{ВЕРСИЯ}"
записать(НОВ / "manifest.json", m)

суммы = {}
for p in sorted(НОВ.rglob("*")):
    if p.is_file() and p.name != "checksums.json":
        суммы[str(p.relative_to(НОВ))] = hashlib.sha256(p.read_bytes()).hexdigest()
записать(НОВ / "checksums.json", {"version": ВЕРСИЯ, "algorithm": "sha256",
                                  "files": суммы})

(НОВ / "CHANGELOG.md").write_text(
    "# CHANGELOG\n\n## 1.3.0\n\n"
    "Контур ChangeSet/Workflow введён в строй.\n\n"
    "Маршруты `/api/v1/changesets` и `/api/v1/workflows` и каналы "
    "`changeset.*` были объявлены заглушками со статусом PLANNED и ответом "
    "501 ещё в 1.0.1. Здесь они НАПОЛНЯЮТСЯ, а не создаются заново: "
    "дублирующий API рядом с объявленным означал бы, что потребитель однажды "
    "выберет не тот.\n\n"
    "* схемы `ChangeSet.v1`, `ChangeSetTarget.v1`, `ChangeSetTransition.v1`, "
    "`Approval.v1`, `AdapterCapabilities.v1`;\n"
    "* семь действий над набором отдельными маршрутами; `status` в запросе не "
    "принимается, PUT/PATCH/DELETE отвечают 405 `ACTION_ONLY`;\n"
    f"* {len(СОБЫТИЯ_ПЕРЕХОДОВ)} каналов переходов переведены в AVAILABLE;\n"
    "* ресурс `changeset` в матрице владения, единственный писатель — "
    "control-plane;\n"
    "* двадцать один код ошибок контура.\n\n"
    "Не заявлено и намеренно выключено: применение в production "
    "(`changeset.production_apply` — PLANNED), реальные адаптеры Templates, "
    "Content и SEO (PLANNED), необратимые операции.\n\n"
    + (ИСТ / "CHANGELOG.md").read_text(encoding="utf-8").replace("# CHANGELOG\n", "", 1),
    encoding="utf-8")

print(json.dumps({"version": ВЕРСИЯ, "files": len(суммы),
                  "openapi_paths": len(oa["paths"]),
                  "asyncapi_channels": len(aa["channels"]),
                  "schemas": len(list((НОВ / "schemas").glob("*.json"))),
                  "capabilities": cc["count"],
                  "changeset_channels": len(СОБЫТИЯ_ПЕРЕХОДОВ)},
                 ensure_ascii=False))
