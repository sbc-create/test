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


def зов(метод: str, путь: str, тело=None, служба: str = "architect",
        доп: dict | None = None, с_заголовками: bool = False):
    заг = {"Content-Type": "application/json"}
    if ТОКЕНЫ.get(служба):
        заг["Authorization"] = "Bearer " + ТОКЕНЫ[служба]
    заг.update(доп or {})
    r = urllib.request.Request(
        Б + путь, method=метод, headers=заг,
        data=json.dumps(тело, ensure_ascii=False).encode() if тело is not None
        else None)
    try:
        with urllib.request.urlopen(r, timeout=20) as о:
            код, т, h = о.status, json.loads(о.read() or b"{}"), dict(о.headers)
    except urllib.error.HTTPError as e:
        сырое = e.read() or b"{}"
        h = dict(e.headers or {})
        try:
            код, т = e.code, json.loads(сырое)
        except ValueError:
            код, т = e.code, {"raw": сырое.decode("utf-8", "replace")[:300]}
    return (код, т, h) if с_заголовками else (код, т)


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
        raise AssertionError("список наборов отдан без токена")
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


# --- версия ресурса как условие запроса --------------------------------------

def _создать_набор():
    к, т = зов("POST", "/api/v1/changesets", заявка())
    assert к == 201, т
    return т["changeset_id"]


def test_http_etag_отдаёт_версию_ресурса():
    cid = _создать_набор()
    к, т, h = зов("GET", f"/api/v1/changesets/{cid}", с_заголовками=True)
    assert к == 200, т
    assert h.get("ETag") == f'"{т["version"]}"', (h.get("ETag"), т["version"])


def test_http_устаревший_if_match_отклоняется():
    cid = _создать_набор()
    к, т, h = зов("GET", f"/api/v1/changesets/{cid}", с_заголовками=True)
    версия = т["version"]
    к, т = зов("POST", f"/api/v1/changesets/{cid}/validate", {},
               доп={"If-Match": f'"{версия - 1}"'})
    assert к == 409, т
    assert т["error_code"] == "VERSION_CONFLICT", т
    # Отказ не сдвинул состояние: набор остался предложением.
    к, после = зов("GET", f"/api/v1/changesets/{cid}")
    assert после["status"] == "PROPOSED", после["status"]
    assert после["version"] == версия, после["version"]


def test_http_совпавший_if_match_пропускает():
    """Отмена выбрана намеренно: она не ходит в реестр.

    Проверяется условие запроса, а не доступность витрин, и действие, которое
    здесь отказало бы по своей причине, ответ на этот вопрос только затемнит.
    """
    cid = _создать_набор()
    к, т, h = зов("GET", f"/api/v1/changesets/{cid}", с_заголовками=True)
    assert к == 200, т
    к, т = зов("POST", f"/api/v1/changesets/{cid}/cancel",
               {"reason": "проверка условия запроса"}, доп={"If-Match": h["ETag"]})
    assert к == 200, т
    к, после = зов("GET", f"/api/v1/changesets/{cid}")
    assert после["status"] == "CANCELLED", после["status"]


def test_http_расхождение_if_match_и_поля_отклоняется():
    """Два разных намерения в одном запросе — не повод выбрать любое."""
    cid = _создать_набор()
    к, т = зов("POST", f"/api/v1/changesets/{cid}/validate",
               {"expected_resource_version": 1}, доп={"If-Match": '"9"'})
    assert к == 422, т
    assert т["error_code"] == "EXPECTED_VERSION_INVALID", т


def test_http_нечисловой_if_match_отклоняется():
    cid = _создать_набор()
    # Значение латиницей не из придирчивости: в заголовок HTTP кириллица не
    # укладывается, и запрос упал бы у клиента, не дойдя до проверки.
    к, т = зов("POST", f"/api/v1/changesets/{cid}/cancel", {},
               доп={"If-Match": '"not-a-version"'})
    assert к == 422, т
    assert т["error_code"] == "EXPECTED_VERSION_INVALID", т


def test_http_личность_из_тела_не_даёт_полномочий():
    """Кем себя назвал отправитель — не довод. Личность берётся из токена.

    Поля вроде actor_id или approved_by в теле выглядят как обычные данные и
    потому опаснее подделанного заголовка: их легко принять к сведению.
    """
    з = заявка()
    з.update(actor_id="human:owner", actor_type="HUMAN",
             producer_service="human_owner", approved_by="human:owner",
             authority="owner")
    к, т = зов("POST", "/api/v1/changesets", з, служба="qwen")
    assert к == 201, т
    к, набор = зов("GET", f"/api/v1/changesets/{т['changeset_id']}")
    assert набор["actor_id"] != "human:owner", набор["actor_id"]
    assert набор["actor_type"] == "MODEL", набор["actor_type"]
    assert набор["producer_service"] == "qwen", набор["producer_service"]
    assert not набор.get("approval"), набор.get("approval")


def test_http_класс_риска_фильтруется_по_перечислению():
    """Опечатка в значении фильтра не должна выглядеть как «ничего нет»."""
    к, т = зов("GET", "/api/v1/changesets?risk_class=HIGH")
    assert к == 422, т
    assert т["error_code"] == "FILTER_VALUE_UNKNOWN", т
    к, т = зов("GET", "/api/v1/changesets?risk_class=R2")
    assert к == 200, т


# --- эталонный клиент против живого контура ----------------------------------

def _клиент(служба: str = "architect"):
    import importlib.util
    from pathlib import Path as _P
    путь = (_P(__file__).resolve().parents[2]
            / "contracts/control-plane/clients/changeset_client.py")
    спец = importlib.util.spec_from_file_location("changeset_client", путь)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м, м.КлиентИзменений(Б, ТОКЕНЫ[служба])


def test_http_эталонный_клиент_проводит_набор():
    """Совпадения имён мало: клиент обязан работать против настоящего контура.

    Клиент, сверенный только по описанию, расходится с ним ровно там, где
    описание неполно, — и узнаёт об этом тот, кто им пользуется.
    """
    м, к = _клиент()
    создан = к.предложить(заявка(), request_id="req-client-1")
    cid = создан["changeset_id"]

    набор, версия = к.получить(cid)
    assert набор["status"] == "PROPOSED", набор["status"]
    assert версия >= 1, версия

    # Устаревшая версия отклоняется разобранной ошибкой, а не текстом.
    try:
        к.отменить(cid, reason="проверка", версия=версия - 1)
        raise AssertionError("устаревшая версия принята")
    except м.ОшибкаКонтура as ош:
        assert ош.статус == 409, ош.статус
        assert ош.error_code == "VERSION_CONFLICT", ош.error_code
        assert ош.повторяем is True

    итог = к.отменить(cid, reason="проверка клиента", версия=версия)
    assert итог["status"] == "CANCELLED", итог

    история = к.история(cid)
    assert история["count"] >= 1, история
    assert [п["to_status"] for п in история["items"]][-1] == "CANCELLED"


def test_http_клиент_отвергает_неизвестное_действие():
    """Опечатка в имени действия ловится у клиента, а не 404 от сервера."""
    м, к = _клиент()
    cid = к.предложить(заявка())["changeset_id"]
    try:
        к._действие(cid, "approove")
        raise AssertionError("неизвестное действие принято")
    except ValueError as e:
        assert "не предусмотрено" in str(e), str(e)


def test_http_клиент_видит_фильтры_сервера():
    м, к = _клиент()
    к.предложить(заявка())
    отобрано = к.список(status="PROPOSED", limit=5)
    assert отобрано["filters_applied"]["status"] == "PROPOSED", отобрано
    try:
        к.список(risk_class="HIGH")
        raise AssertionError("значение вне перечисления принято")
    except м.ОшибкаКонтура as ош:
        assert ош.error_code == "FILTER_VALUE_UNKNOWN", ош.error_code


def test_http_клиент_отказывает_в_непригодном_идентификаторе():
    """Отказ должен называть причину, а не всплывать из глубины urllib."""
    м, к = _клиент()
    cid = к.предложить(заявка())["changeset_id"]
    try:
        к.отменить(cid, request_id="запрос-1")
        raise AssertionError("непригодный идентификатор принят")
    except ValueError as e:
        assert "latin-1" in str(e), str(e)
