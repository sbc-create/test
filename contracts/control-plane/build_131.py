#!/usr/bin/env python3
"""Сборка bundle 1.3.1 — аддитивно поверх 1.3.0.

Что добавляется и почему именно так
-----------------------------------

1.3.0 объявляет событие `template.release.published.v1`, но не объявляет ни
самого РЕСУРСА `template.release`, ни разрешения на исполнение. Реализация
при этом уже умеет выдавать разрешения — то есть контракт и рантайм
расходились, и расхождение обнаруживалось только попыткой.

Изменения строго аддитивные: ничего не удаляется и не переименовывается,
поэтому мажорная версия не меняется, а патч растёт монотонно.
"""
from __future__ import annotations

import datetime as _d
import hashlib
import json
import pathlib
import shutil
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parent
ИЗ, В = "1.3.0", "1.3.1"


def sha256(п: pathlib.Path) -> str:
    return hashlib.sha256(п.read_bytes()).hexdigest()


def записать(п: pathlib.Path, данные) -> None:
    п.write_text(json.dumps(данные, ensure_ascii=False, indent=1) + "\n",
                 encoding="utf-8")


def собрать() -> dict:
    источник, цель = КОРЕНЬ / ИЗ, КОРЕНЬ / В
    if цель.exists():
        shutil.rmtree(цель)
    shutil.copytree(источник, цель)

    # --- ресурс template.release -----------------------------------------
    матрица = json.loads((цель / "ownership-matrix.json").read_text("utf-8"))
    уже = {з["resource"] for з in матрица["resources"]}
    if "template.release" not in уже:
        матрица["resources"].append({
            "resource": "template.release",
            "fields": ["site_id", "build_id", "artifact_sha256",
                       "design_version", "released_at"],
            "domain_owner": "templates",
            "proposer": "templates",
            "grant_requester": "changeset-worker",
            "grant_audience": "templates-executor",
            "executor": "templates-executor",
            # Канонические связи пишет только Registry. Templates владеет
            # доменом, но не строкой в реестре: иначе у связи стало бы два
            # писателя, и расхождение обнаруживалось бы по последствиям.
            "single_writer": "architect",
            "registry_projection_writer": "architect",
            "readers": ["architect", "templates", "seo", "monitoring", "qwen"],
            # Перечень закрыт. Подстановочный `*` означает «что угодно», а
            # ограничение, допускающее что угодно, ограничением не является.
            "commands": ["publish", "rollback"],
            "emits": ["template.release.published.v1"],
            "consumes": ["changeset.approved.v1", "execution.grant.issued.v1"],
            "source_of_truth": "registry (связь) + templates (артефакт)",
            "retention_owner": "architect",
            "secret_class": "NONE",
            "mutation_policy": "CHANGESET_ONLY",
            "forbidden": [
                "постоянный EXECUTE у templates",
                "запрос разрешения самим templates",
                "выпуск или продление разрешения исполнителем",
                "передача приватного ключа подписи templates или исполнителю",
                "приём security-critical притязаний из тела запроса",
                "прямой вызов исполнителя без разрешения",
            ],
        })
        матрица["generated_at"] = _d.datetime.now(
            _d.timezone.utc).isoformat().replace("+00:00", "Z")
        записать(цель / "ownership-matrix.json", матрица)

    # --- схема разрешения на исполнение ----------------------------------
    обязательные = [
        "typ", "issuer", "audience", "subject", "changeset_id", "site_id",
        "environment", "resource_kind", "action", "plan_hash", "approval_hash",
        "artifact_digest", "registry_fingerprint", "policy_version",
        "contract_version", "fencing_token", "jti", "idempotency_key",
        "issued_at", "not_before", "expires_at"]
    свойства = {к: {"type": "string"} for к in обязательные}
    свойства["fencing_token"] = {"type": "integer", "minimum": 1}
    свойства["audience"] = {"type": "string",
                            "enum": ["changeset-worker", "templates-executor"]}
    свойства["resource_kind"] = {"type": "string",
                                 "enum": ["fake.resource", "template.release",
                                          "template.build"]}
    свойства["action"] = {"type": "string",
                          "enum": ["publish", "rollback", "create", "update",
                                   "patch"]}
    свойства["environment"] = {"type": "string",
                               "enum": ["test", "non-production", "production"]}
    свойства["registry_version"] = {"type": ["integer", "null"]}
    свойства["build_id"] = {"type": ["string", "null"]}
    свойства["approval_ref"] = {"type": ["string", "null"]}
    свойства["target_site_ids"] = {"type": "array", "items": {"type": "string"}}
    свойства["expected_resource_fingerprint"] = {"type": ["string", "null"]}
    записать(цель / "schemas/ExecutionGrant.v1.json", {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "ExecutionGrant.v1.json",
        "title": "Разрешение на исполнение одобренного набора изменений",
        "description": "Выдаётся только службой подписи по ссылке на "
                       "канонический ChangeSet. Ни одно притязание "
                       "безопасности не является необязательным: "
                       "«опциональное» притязание однажды не придёт, и "
                       "проверка молча пропустит его.",
        "type": "object", "additionalProperties": False,
        "required": обязательные, "properties": свойства,
    })

    # --- схема erratum ----------------------------------------------------
    записать(цель / "schemas/ClaimErratum.v1.json", {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "ClaimErratum.v1.json",
        "title": "Исправление числовых утверждений прежнего события журнала",
        "description": "Журнал только дополняется: исправление — новая запись "
                       "со ссылкой на прежнюю, а не правка прежней.",
        "type": "object", "additionalProperties": True,
        "required": ["event_type", "source_event_id", "source_ledger_seq",
                     "source_event_type", "subject_producer",
                     "correction_actor", "correction_authority",
                     "idempotency_key", "reason_code", "claim_namespace",
                     "claim_corrections", "evidence_refs"],
        "properties": {
            "event_type": {"const": "audit.claim.erratum.v1"},
            "source_event_id": {"type": "string", "format": "uuid"},
            "source_ledger_seq": {"type": "integer", "minimum": 1},
            "source_event_type": {"type": "string"},
            "subject_producer": {"type": "string"},
            "correction_actor": {"type": "string"},
            "correction_authority": {"type": "string"},
            "reason_code": {"type": "string",
                            "enum": ["RECOMPUTED_FROM_PINNED_EVIDENCE",
                                     "EVIDENCE_INSUFFICIENT", "UNIT_MISMATCH",
                                     "SOURCE_DATA_LOST"]},
            "claim_namespace": {
                "type": "object", "required": ["ref", "sha256"],
                "properties": {"ref": {"type": "string"},
                               "sha256": {"type": "string"},
                               "pointer": {"type": "string"}}},
            "claim_corrections": {
                "type": "array", "minItems": 1,
                "items": {
                    "type": "object", "required": ["path", "disposition"],
                    "properties": {
                        "path": {"type": "string", "pattern": "^/"},
                        "previous_value": {},
                        "disposition": {"type": "string",
                                        "enum": ["CORRECTED",
                                                 "WITHDRAWN_UNVERIFIED"]},
                        "replacement_value": {}},
                    "allOf": [
                        {"if": {"properties": {"disposition":
                                               {"const": "CORRECTED"}}},
                         "then": {"required": ["replacement_value"]}},
                        {"if": {"properties": {"disposition":
                                               {"const": "WITHDRAWN_UNVERIFIED"}}},
                         "then": {"not": {"required": ["replacement_value"]}}},
                    ]}},
        },
    })

    # --- каталог возможностей --------------------------------------------
    каталог = json.loads((цель / "capability-catalog.json").read_text("utf-8"))
    каталог["bundle_version"] = В
    # В 1.3.0 уживаются два вида записей: с `capability_id` и с `id`.
    # Читать только один — значит однажды добавить дубль под другим именем.
    существующие = {c.get("capability_id") or c.get("id")
                    for c in каталог["capabilities"]}
    if "changeset.execution_grant" not in существующие:
        каталог["capabilities"].append({
            "capability_id": "changeset.execution_grant",
            "owner_service": "architect",
            "version": В,
            "status": "AVAILABLE",
            "read_endpoint": "http://127.0.0.1:8795/jwks",
            "command_endpoint": "http://127.0.0.1:8795/grant",
            "event_types": [],
            "required_scopes": ["approval:grant"],
            "dependencies": ["changeset.apply"],
            "allowed_requesters": ["changeset-worker"],
            "allowed_audiences": ["changeset-worker", "templates-executor"],
            "schema": "ExecutionGrant.v1.json",
            "note": "Разрешение выдаётся только по ссылке на канонический "
                    "ChangeSet; готовое тело подписи не принимается.",
        })
    if "audit.claim.erratum" not in существующие:
        каталог["capabilities"].append({
            "capability_id": "audit.claim.erratum",
            "owner_service": "architect",
            "version": В,
            "status": "AVAILABLE",
            "read_endpoint": "/api/v1/audit/events",
            "command_endpoint": "/api/v1/audit/events",
            "event_types": ["audit.claim.erratum.v1"],
            "required_scopes": ["audit:write"],
            "dependencies": [],
            "schema": "ClaimErratum.v1.json",
            "note": "Журнал только дополняется: исходное событие не правится "
                    "и не удаляется.",
        })
    каталог["count"] = len(каталог["capabilities"])
    каталог["available"] = sum(1 for c in каталог["capabilities"]
                               if c.get("status") == "AVAILABLE")
    каталог["planned"] = sum(1 for c in каталог["capabilities"]
                             if c.get("status") == "PLANNED")
    записать(цель / "capability-catalog.json", каталог)

    # --- OpenAPI ----------------------------------------------------------
    openapi = json.loads((цель / "openapi.json").read_text("utf-8"))
    openapi.setdefault("components", {}).setdefault("schemas", {})
    openapi["components"]["schemas"]["ExecutionGrant"] = json.loads(
        (цель / "schemas/ExecutionGrant.v1.json").read_text("utf-8"))
    openapi["components"]["schemas"]["ClaimErratum"] = json.loads(
        (цель / "schemas/ClaimErratum.v1.json").read_text("utf-8"))
    openapi.setdefault("paths", {})["/grant"] = {
        "post": {
            "summary": "Выдать разрешение на исполнение одобренного набора",
            "description": "Принимается ТОЛЬКО ссылка на набор изменений. "
                           "Каноническое состояние служба читает сама.",
            "operationId": "issueExecutionGrant",
            "servers": [{"url": "http://127.0.0.1:8795"}],
            "requestBody": {"required": True, "content": {"application/json": {
                "schema": {"type": "object", "additionalProperties": False,
                           "required": ["changeset_id", "audience",
                                        "fencing_token"],
                           "properties": {
                               "changeset_id": {"type": "string"},
                               "audience": {"type": "string",
                                            "enum": ["changeset-worker",
                                                     "templates-executor"]},
                               "fencing_token": {"type": "integer"}}}}}},
            "responses": {
                "200": {"description": "разрешение выдано",
                        "content": {"application/json": {"schema": {
                            "type": "object",
                            "properties": {"grant": {"$ref":
                                "#/components/schemas/ExecutionGrant"},
                                "signature": {"type": "string"},
                                "kid": {"type": "string"}}}}}},
                "403": {"description": "аудитория, запросчик или окружение "
                                       "не допущены"},
                "409": {"description": "состояние набора или маркер не "
                                       "допускают выдачи"}},
        }}
    записать(цель / "openapi.json", openapi)

    # --- манифест и контрольные суммы -------------------------------------
    манифест = json.loads((цель / "manifest.json").read_text("utf-8"))
    манифест["version"] = В
    манифест["generated_at"] = _d.datetime.now(
        _d.timezone.utc).isoformat().replace("+00:00", "Z")
    манифест["schemas_count"] = len(list((цель / "schemas").glob("*.json")))
    записать(цель / "manifest.json", манифест)

    суммы = {"version": В, "algorithm": "sha256", "files": {}}
    for п in sorted(цель.rglob("*")):
        if п.is_file() and п.name != "checksums.json":
            суммы["files"][str(п.relative_to(цель))] = sha256(п)
    записать(цель / "checksums.json", суммы)
    return {"version": В, "files": len(суммы["files"]),
            "capabilities": каталог["count"],
            "resources": len(матрица["resources"])}


if __name__ == "__main__":
    print(json.dumps(собрать(), ensure_ascii=False, indent=1))
