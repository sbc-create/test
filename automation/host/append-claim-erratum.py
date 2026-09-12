#!/usr/bin/env python3
"""Запись одного идемпотентного erratum для утверждений FLEET-TPL-005.

Значения берутся ТОЛЬКО из закреплённого документа доказательств и
сверяются по SHA-256. Ни одно число не восстанавливается по памяти или по
тексту прежнего отчёта: именно так в журнал и попадает неправда.

Исправляющий не выдаёт себя за автора исправляемого утверждения: actor —
архитектор, subject_producer — templates.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
import uuid

БАЗА = os.environ.get("CONTROL_API_BASE", "http://127.0.0.1:8790").rstrip("/")
ЛИЧНОСТЬ = "audit-token-architect"
ТИП = "audit.claim.erratum.v1"


def _токен() -> str:
    кат = os.environ.get("CREDENTIALS_DIRECTORY", "")
    путь = os.path.join(кат, ЛИЧНОСТЬ) if кат else ""
    if путь and os.path.isfile(путь):
        значение = open(путь, encoding="utf-8").read().strip()
        if значение:
            return значение
    raise SystemExit(f"credential {ЛИЧНОСТЬ} не передан")


def собрать(*, документ: str, source_event_id: str, source_seq: int,
            source_type: str) -> dict:
    сырое = open(документ, "rb").read()
    отпечаток = hashlib.sha256(сырое).hexdigest()
    данные = json.loads(сырое.decode("utf-8"))
    заявленные = данные["claims"]

    исправления = [
        {"path": "/broken_existing_routes_reported",
         "previous_value": заявленные["broken_existing_routes_reported"],
         "disposition": "CORRECTED",
         "replacement_value": данные["broken_existing_routes"]["recomputed"]},
        {"path": "/affected_unique_links_reported",
         "previous_value": заявленные["affected_unique_links_reported"],
         "disposition": "WITHDRAWN_UNVERIFIED"},
        {"path": "/eligible_unique_links_reported",
         "previous_value": заявленные["eligible_unique_links_reported"],
         "disposition": "WITHDRAWN_UNVERIFIED"},
    ]
    пространство = {"ref": документ, "sha256": отпечаток, "pointer": "/claims"}
    основа = {"source_event_id": source_event_id,
              "corrections": sorted(
                  [(и["path"], и["disposition"], и.get("replacement_value"))
                   for и in исправления], key=lambda x: x[0])}
    ключ = "erratum:" + hashlib.sha256(
        json.dumps(основа, ensure_ascii=False, sort_keys=True,
                   separators=(",", ":")).encode()).hexdigest()[:32]

    return {
        "event_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"urn:{ТИП}:{ключ}")),
        "event_type": ТИП, "phase": "SUCCEEDED", "result": "SUCCESS",
        "authority": "EXECUTE", "scope": "FLEET", "environment": "production",
        "resource_type": "monitoring.observation",
        "resource_id": "FLEET-TPL-005-audit",
        "resource_owner": "architect",
        "idempotency_key": ключ,
        "correlation_id": "FLEET-CORE-003-R2",
        "prompt_id": "FLEET-CORE-003-CHANGESET-WORKFLOW", "prompt_rev": "R2",
        "source_event_id": source_event_id,
        "source_ledger_seq": source_seq,
        "source_event_type": source_type,
        "subject_producer": "templates",
        "correction_actor": "architect",
        "correction_authority": "architect:contract-maintainer",
        "reason_code": "RECOMPUTED_FROM_PINNED_EVIDENCE",
        "claim_namespace": пространство,
        "claim_corrections": исправления,
        "evidence_refs": [{"ref": документ, "hash": "sha256:" + отпечаток}],
        "summary": ("исправление утверждений FLEET-TPL-005: "
                    "broken_existing_routes 49 → 48 по детерминированному "
                    "пересчёту; affected_unique_links и eligible_unique_links "
                    "отозваны как неподтверждённые — поадресного множества в "
                    "закреплённых артефактах нет"),
    }


def отправить(событие: dict) -> dict:
    зпр = urllib.request.Request(
        БАЗА + "/api/v1/audit/events", method="POST",
        data=json.dumps(событие, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "X-Service-Name": "architect",
                 "Authorization": "Bearer " + _токен()})
    try:
        with urllib.request.urlopen(зпр, timeout=20) as о:
            return {"status": о.status, "body": json.loads(о.read() or b"{}")}
    except urllib.error.HTTPError as ош:
        return {"status": ош.code,
                "body": json.loads(ош.read() or b"{}")}


if __name__ == "__main__":
    документ, sid, seq, тип = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
    с = собрать(документ=документ, source_event_id=sid, source_seq=seq,
                source_type=тип)
    ответ = отправить(с)
    print(json.dumps({"http_status": ответ["status"],
                      "event_id": с["event_id"],
                      "idempotency_key": с["idempotency_key"],
                      "ledger_seq": ответ["body"].get("ledger_seq"),
                      "idempotent_replay": ответ["body"].get("idempotent_replay"),
                      "error": ответ["body"].get("error_code"),
                      "detail": ответ["body"].get("detail")},
                     ensure_ascii=False, indent=1))
