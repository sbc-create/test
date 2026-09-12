"""Проверки контура изменений через HTTP.

Идут против ЭФЕМЕРНОГО экземпляра Control API, который поднимает run_tests.py
поверх копий баз. Канонические Registry и Audit Ledger в этих проверках не
участвуют.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid

import pytest

Б = os.environ.get("CHANGESET_API_BASE", "")
pytestmark = pytest.mark.skipif(
    not Б, reason="эфемерный экземпляр не поднят; запускать через run_tests.py")

ТОКЕНЫ = {
    "architect": os.environ.get("AUDIT_TOKEN_ARCHITECT", ""),
    "qwen": os.environ.get("AUDIT_TOKEN_QWEN", ""),
    "templates": os.environ.get("AUDIT_TOKEN_TEMPLATES", ""),
}


def зов(метод: str, путь: str, тело=None, служба: str = "architect"):
    заг = {"Content-Type": "application/json"}
    if ТОКЕНЫ.get(служба):
        заг["Authorization"] = "Bearer " + ТОКЕНЫ[служба]
    r = urllib.request.Request(
        Б + путь, method=метод, headers=заг,
        data=json.dumps(тело, ensure_ascii=False).encode() if тело is not None
        else None)
    try:
        with urllib.request.urlopen(r, timeout=20) as о:
            return о.status, json.loads(о.read() or b"{}")
    except urllib.error.HTTPError as e:
        сырое = e.read() or b"{}"
        try:
            return e.code, json.loads(сырое)
        except ValueError:
            return e.code, {"raw": сырое.decode("utf-8", "replace")[:300]}


def заявка(**kw):
    д = {"resource_type": "fake.resource", "resource_id": "http-res",
         "operation_type": "update",
         "target_site_ids": ["test-alpha-0001"],
         "requested_change": {"title": "через HTTP"},
         "idempotency_key": "http-" + uuid.uuid4().hex[:10]}
    д.update(kw)
    return д


def test_http_маршрут_процессов_отвечает():
    к, т = зов("GET", "/api/v1/workflows")
    assert к == 200, т
    assert т["autonomous_production_apply"] == "DISABLED"
    assert т["schema_version"].startswith("fleet-changeset/")


def test_http_без_токена_отказ():
    r = urllib.request.Request(Б + "/api/v1/changesets", method="GET")
    try:
        urllib.request.urlopen(r, timeout=20)
        assert False, "список наборов отдан без токена"
    except urllib.error.HTTPError as e:
        assert e.code in (401, 403)


def test_http_состояние_нельзя_задать_в_запросе():
    к, т = зов("POST", "/api/v1/changesets",
               заявка(status="SUCCEEDED"), служба="templates")
    assert к == 422 and т["error_code"] == "STATUS_NOT_WRITABLE", т


def test_http_изменение_и_удаление_запрещены():
    for метод in ("PUT", "PATCH", "DELETE"):
        к, т = зов(метод, "/api/v1/changesets", {})
        assert к == 405, (метод, к, т)
        assert т.get("error_code") == "ACTION_ONLY", (метод, т)


def test_http_qwen_не_может_одобрять_и_применять():
    к, создан = зов("POST", "/api/v1/changesets", заявка(), служба="templates")
    assert к == 201, создан
    cid = создан["changeset_id"]
    for действие in ("approve", "apply", "rollback"):
        к, т = зов("POST", f"/api/v1/changesets/{cid}/{действие}",
                   {"expires_at": "2099-01-01T00:00:00Z"}, служба="qwen")
        assert к == 403, (действие, к, т)
        assert т["error_code"] in ("MODEL_ACTION_DENIED", "ROLE_NOT_GRANTED"), т


def test_http_qwen_может_предложить():
    к, т = зов("POST", "/api/v1/changesets", заявка(), служба="qwen")
    assert к == 201, т
    assert т["status"] == "PROPOSED"


def test_http_идемпотентное_создание():
    з = заявка(idempotency_key="http-повтор-001")
    к1, a = зов("POST", "/api/v1/changesets", з, служба="templates")
    к2, b = зов("POST", "/api/v1/changesets", з, служба="templates")
    assert к1 == 201 and к2 == 200
    assert a["changeset_id"] == b["changeset_id"]
    assert b["idempotent_replay"] is True


def test_http_фильтры_применяются_на_сервере():
    зов("POST", "/api/v1/changesets", заявка(), служба="templates")
    к, все = зов("GET", "/api/v1/changesets?limit=1000")
    к2, только = зов("GET", "/api/v1/changesets?status=PROPOSED&limit=1000")
    assert к == к2 == 200
    assert all(i["status"] == "PROPOSED" for i in только["items"])
    assert только["count"] <= все["count"]
    к3, т3 = зов("GET", "/api/v1/changesets?неизвестный=1".replace(
        "неизвестный", "unknown_filter"))
    assert к3 == 422 and т3["error_code"] == "FILTER_UNKNOWN"
    к4, т4 = зов("GET", "/api/v1/changesets?status=НЕТ".replace("НЕТ", "NOSUCH"))
    assert к4 == 422 and т4["error_code"] == "FILTER_VALUE_UNKNOWN"


def test_http_валидация_читает_настоящий_реестр():
    """Через HTTP работает настоящий реестр, а не подставной.

    Идентификаторы испытаний в нём отсутствуют — и валидация обязана это
    заметить. Успех здесь означал бы, что проверка site_id ничего не
    проверяет, а домен или выдуманная строка прошли бы наравне с настоящим
    ключом.
    """
    к, создан = зов("POST", "/api/v1/changesets", заявка(), служба="templates")
    cid = создан["changeset_id"]
    к2, т2 = зов("POST", f"/api/v1/changesets/{cid}/validate")
    assert к2 == 422, т2
    assert т2["error_code"] == "SITE_ID_UNKNOWN", т2


def test_http_домен_не_принимается_как_ключ():
    к, создан = зов("POST", "/api/v1/changesets",
                    заявка(target_site_ids=["yummyani.org"]), служба="templates")
    assert к == 201, создан
    к2, т2 = зов("POST", f"/api/v1/changesets/{создан['changeset_id']}/validate")
    assert к2 == 422 and т2["error_code"] == "SITE_ID_UNKNOWN", т2


def test_http_история_переходов_записывается():
    """Неудачная валидация тоже оставляет след: решение видно целиком."""
    к, создан = зов("POST", "/api/v1/changesets", заявка(), служба="templates")
    cid = создан["changeset_id"]
    к2, т2 = зов("GET", f"/api/v1/changesets/{cid}/transitions")
    assert к2 == 200 and т2["count"] == 0, т2
    зов("POST", f"/api/v1/changesets/{cid}/validate")
    к4, т4 = зов("GET", f"/api/v1/changesets/{cid}/transitions")
    assert [i["to_status"] for i in т4["items"]] == ["VALIDATING",
                                                     "VALIDATION_FAILED"], т4
    assert all(i["actor_role"] == "validator" for i in т4["items"]), т4
