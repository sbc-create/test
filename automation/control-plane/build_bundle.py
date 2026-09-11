#!/usr/bin/env python3
"""Сборка канонического contract bundle Control Plane.

Bundle один и версионирован целиком. Отдельные схемы тоже версионированы, но
вместе они образуют согласованный набор: несовместимость между ними — это
несовместимость bundle, а не частная проблема одной схемы.

Здесь генерируются только артефакты. Ничего не поднимается и не объявляется
работающим: статус AVAILABLE ставится отдельным шагом и только после живой
проверки.
"""
from __future__ import annotations

import datetime as dt, hashlib, json, pathlib

ВЕРСИЯ = "1.0.0"
КОРЕНЬ = pathlib.Path("/srv/site-factory/control-plane-contracts") / ВЕРСИЯ
БАЗА_ID = "https://contracts.site-factory.internal/fleet/1.0.0"
СЕЙЧАС = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def схема(имя: str, заголовок: str, описание: str, свойства: dict,
          обязательные: list[str], owner: str, *,
          доп: dict | None = None) -> dict:
    d = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"{БАЗА_ID}/schemas/{имя}.json",
        "title": заголовок,
        "description": описание,
        "x-owner": owner,
        "x-schema-version": "1.0.0",
        "x-lifecycle": "ACTIVE",
        "x-created-at": СЕЙЧАС,
        "x-updated-at": СЕЙЧАС,
        "x-compatibility": "BACKWARD_COMPATIBLE_ADDITIVE",
        "type": "object",
        "properties": свойства,
        "required": обязательные,
        # Неизвестные необязательные поля потребитель обязан терпеть: иначе
        # любое аддитивное расширение производителя станет ломающим.
        "additionalProperties": True,
    }
    if доп:
        d.update(доп)
    return d


СТРОКА = {"type": "string"}
ВРЕМЯ = {"type": "string", "format": "date-time"}
ЦЕЛОЕ = {"type": "integer"}

СХЕМЫ = {
 "SiteRef": схема("SiteRef", "Ссылка на сайт",
   "Единственный допустимый способ сослаться на сайт между сервисами. "
   "Домен приводится для читаемости, но ключом является site_id: домен "
   "может смениться, идентификатор — нет.",
   {"site_id": СТРОКА, "canonical_domain": СТРОКА, "registry_version": ЦЕЛОЕ},
   ["site_id"], "architect"),

 "ActorRef": схема("ActorRef", "Инициатор действия",
   "Кто действует. MODEL выделен отдельно от SERVICE намеренно: модель "
   "предлагает, но не обладает правами сама по себе, и её полномочия всегда "
   "делегированы через delegated_by.",
   {"actor_type": {"enum": ["SERVICE", "HUMAN", "MODEL"]},
    "actor_id": СТРОКА, "service_id": СТРОКА, "delegated_by": СТРОКА,
    "declared_scopes": {"type": "array", "items": СТРОКА}},
   ["actor_type", "actor_id"], "architect"),

 "ObservedValue": схема("ObservedValue", "Наблюдённое значение",
   "Значение вместе с состоянием знания о нём. Ноль, ложь и пустая строка "
   "суть ЗНАЧЕНИЯ и допустимы только при state=PRESENT. Незнание "
   "выражается состоянием, а не подстановкой нуля: подставленный ноль "
   "неотличим от измеренного и потому необратимо теряет правду.",
   {"state": {"enum": ["PRESENT", "UNKNOWN", "ABSENT", "STALE", "ERROR",
                       "NOT_APPLICABLE"]},
    "value": {"description": "любое значение, включая честный 0 и false"},
    "observed_at": ВРЕМЯ, "source": СТРОКА, "error_code": СТРОКА,
    "confidence": {"type": "number", "minimum": 0, "maximum": 1}},
   ["state"], "architect",
   доп={"allOf": [{"if": {"properties": {"state": {"const": "PRESENT"}}},
                   "then": {"required": ["value", "observed_at", "source"]}},
                  {"if": {"properties": {"state": {"const": "ERROR"}}},
                   "then": {"required": ["error_code"]}}]}),

 "CorrelationContext": схема("CorrelationContext", "Контекст прослеживания",
   "Сквозной контекст запроса. correlation_id связывает всю цепочку, "
   "causation_id указывает непосредственную причину конкретного шага; "
   "смешивать их нельзя, иначе граф причин выродится в список.",
   {"request_id": СТРОКА, "correlation_id": СТРОКА, "causation_id": СТРОКА,
    "trace_id": СТРОКА, "prompt_id": СТРОКА, "prompt_rev": СТРОКА,
    "run_id": СТРОКА},
   ["correlation_id"], "architect"),

 "VersionRef": схема("VersionRef", "Версия ресурса",
   "Версия конкретного ресурса. aggregate_version монотонна внутри ресурса "
   "и служит для optimistic concurrency; schema_version описывает форму, а "
   "не содержимое.",
   {"resource_type": СТРОКА, "resource_id": СТРОКА,
    "aggregate_version": ЦЕЛОЕ, "schema_version": СТРОКА,
    "build_id": СТРОКА, "release_id": СТРОКА},
   ["resource_type", "resource_id"], "architect"),

 "EvidenceRef": схема("EvidenceRef", "Ссылка на доказательство",
   "Утверждение без доказательства считается недоказанным. Ссылка обязана "
   "нести контрольную сумму: путь без неё не отличает нынешний артефакт от "
   "подменённого.",
   {"evidence_id": СТРОКА, "uri": СТРОКА, "checksum": СТРОКА,
    "media_type": СТРОКА, "produced_at": ВРЕМЯ, "producer": СТРОКА,
    "retention_class": {"enum": ["EPHEMERAL", "RUN", "RELEASE", "AUDIT"]}},
   ["evidence_id", "uri", "checksum"], "architect"),

 "DesiredObservedState": схема("DesiredObservedState", "Желаемое и наблюдаемое",
   "Два состояния хранятся раздельно и никогда не сливаются. Слияние "
   "уничтожает само понятие дрейфа: система, где желаемое равно "
   "наблюдаемому по определению, не может сообщить о расхождении.",
   {"desired_state": СТРОКА,
    "observed_state": {"$ref": f"{БАЗА_ID}/schemas/ObservedValue.json"},
    "observed_at": ВРЕМЯ, "source": СТРОКА,
    "confidence": {"type": "number"},
    "drift_status": {"enum": ["IN_SYNC", "DRIFT", "UNKNOWN"]}},
   ["desired_state", "drift_status"], "architect"),

 "CommandEnvelope.v1": схема("CommandEnvelope.v1", "Команда",
   "Просьба изменить состояние, адресованная владельцу данных. Приём "
   "команды не равен её выполнению; результат приходит отдельным событием.",
   {"command_id": СТРОКА, "command_type": СТРОКА, "schema_version": СТРОКА,
    "actor_ref": {"$ref": f"{БАЗА_ID}/schemas/ActorRef.json"},
    "target_ref": {"$ref": f"{БАЗА_ID}/schemas/SiteRef.json"},
    "idempotency_key": СТРОКА, "expected_version": ЦЕЛОЕ,
    "requested_at": ВРЕМЯ, "deadline_at": ВРЕМЯ,
    "correlation_context": {"$ref": f"{БАЗА_ID}/schemas/CorrelationContext.json"},
    "payload": {"type": "object"}},
   ["command_id", "command_type", "schema_version", "actor_ref",
    "idempotency_key", "requested_at", "correlation_context"], "architect"),

 "CommandReceipt.v1": схема("CommandReceipt.v1", "Расписка о приёме команды",
   "ACCEPTED означает «принято к исполнению», и только это. Трактовать "
   "расписку как успех — самая дорогая из возможных ошибок: операция ещё "
   "не выполнена, а вызывающий уже считает её завершённой.",
   {"operation_id": СТРОКА, "command_id": СТРОКА,
    "status": {"enum": ["ACCEPTED", "REJECTED", "BLOCKED"]},
    "accepted_at": ВРЕМЯ, "owner_service": СТРОКА, "status_url": СТРОКА,
    "problem": {"$ref": f"{БАЗА_ID}/schemas/Problem.v1.json"},
    "evidence_refs": {"type": "array",
                      "items": {"$ref": f"{БАЗА_ID}/schemas/EvidenceRef.json"}}},
   ["operation_id", "command_id", "status", "owner_service"], "architect"),

 "EventEnvelope.v1": схема("EventEnvelope.v1", "Событие",
   "Факт, уже случившийся у владельца данных. Публикуется только после "
   "устойчивой фиксации: событие о том, чего ещё нет, потребитель примет "
   "за правду и построит на нём своё состояние.",
   {"event_id": СТРОКА, "event_type": СТРОКА, "schema_version": СТРОКА,
    "producer": СТРОКА, "aggregate_type": СТРОКА, "aggregate_id": СТРОКА,
    "aggregate_version": ЦЕЛОЕ, "occurred_at": ВРЕМЯ,
    "actor_ref": {"$ref": f"{БАЗА_ID}/schemas/ActorRef.json"},
    "correlation_context": {"$ref": f"{БАЗА_ID}/schemas/CorrelationContext.json"},
    "payload": {"type": "object"},
    "evidence_refs": {"type": "array",
                      "items": {"$ref": f"{БАЗА_ID}/schemas/EvidenceRef.json"}}},
   ["event_id", "event_type", "schema_version", "producer", "aggregate_type",
    "aggregate_id", "aggregate_version", "occurred_at"], "architect"),

 "Problem.v1": схема("Problem.v1", "Ошибка",
   "Совместима с RFC 9457. safe_public_detail существует отдельно от detail "
   "потому, что подробность, полезная владельцу, часто раскрывает "
   "внутреннее устройство наружу.",
   {"type": СТРОКА, "title": СТРОКА, "status": ЦЕЛОЕ, "detail": СТРОКА,
    "instance": СТРОКА, "error_code": СТРОКА, "retryable": {"type": "boolean"},
    "owner": СТРОКА, "correlation_id": СТРОКА,
    "evidence_ref": {"$ref": f"{БАЗА_ID}/schemas/EvidenceRef.json"},
    "safe_public_detail": СТРОКА},
   ["type", "title", "status", "error_code", "retryable", "owner"],
   "architect"),

 "Page.v1": схема("Page.v1", "Страница выдачи",
   "Курсорная выдача. snapshot_version фиксирует, какую версию данных "
   "листает потребитель: без неё страницы могут склеиться из разных "
   "состояний и дать набор, которого не существовало ни в один момент.",
   {"items": {"type": "array"}, "next_cursor": СТРОКА,
    "snapshot_version": ЦЕЛОЕ, "generated_at": ВРЕМЯ},
   ["items"], "architect"),

 "Capability.v1": схема("Capability.v1", "Возможность контура",
   "Что сервис действительно умеет сейчас. AVAILABLE ставится только после "
   "живой проверки; PLANNED не имеет права нести адрес, иначе потребитель "
   "начнёт в него ходить.",
   {"capability_id": СТРОКА, "owner_service": СТРОКА, "version": СТРОКА,
    "status": {"enum": ["AVAILABLE", "DEGRADED", "BLOCKED", "PLANNED",
                        "RETIRED"]},
    "read_endpoint": {"type": ["string", "null"]},
    "command_endpoint": {"type": ["string", "null"]},
    "event_types": {"type": "array", "items": СТРОКА},
    "required_scopes": {"type": "array", "items": СТРОКА},
    "dependencies": {"type": "array", "items": СТРОКА},
    "last_verified_at": {"type": ["string", "null"], "format": "date-time"},
    "evidence_ref": {"type": ["string", "null"]}},
   ["capability_id", "owner_service", "version", "status"], "architect",
   доп={"allOf": [{"if": {"properties": {"status": {"const": "PLANNED"}}},
                   "then": {"properties": {"read_endpoint": {"const": None},
                                           "command_endpoint": {"const": None}}}},
                  {"if": {"properties": {"status": {"const": "AVAILABLE"}}},
                   "then": {"required": ["last_verified_at", "evidence_ref"]}}]}),
}


def записать(путь: pathlib.Path, данные) -> str:
    путь.parent.mkdir(parents=True, exist_ok=True)
    текст = (json.dumps(данные, ensure_ascii=False, indent=1) + "\n"
             if not isinstance(данные, str) else данные)
    путь.write_text(текст, encoding="utf-8")
    return hashlib.sha256(путь.read_bytes()).hexdigest()


if __name__ == "__main__":
    суммы = {}
    for имя, тело in СХЕМЫ.items():
        с = записать(КОРЕНЬ / "schemas" / f"{имя}.json", тело)
        суммы[f"schemas/{имя}.json"] = с
    print(f"схем записано: {len(СХЕМЫ)}")
    (КОРЕНЬ / "_partial-checksums.json").write_text(
        json.dumps(суммы, ensure_ascii=False, indent=1), encoding="utf-8")
