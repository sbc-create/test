"""SUITE_2 — контракт audit.claim.erratum.v1.

Проверяются запреты, а не наличие полей: журнал, в котором исправление
возможно «почти правильно», перестаёт быть свидетельством.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import uuid

import pytest


@pytest.fixture()
def журнал(tmp_path, monkeypatch):
    """Эфемерный журнал и свой корень доказательств."""
    monkeypatch.setenv("AUDIT_EVIDENCE_ROOTS", str(tmp_path))
    from factory.site_engine.audit import ledger_store as L
    importlib.reload(L)
    соед = L.открыть(tmp_path / "ledger.sqlite3")
    yield {"соед": соед, "L": L, "tmp": tmp_path}
    соед.close()


def документ(tmp_path, утверждения: dict) -> dict:
    п = tmp_path / "claims.json"
    тело = json.dumps({"claims": утверждения}, ensure_ascii=False)
    п.write_text(тело, encoding="utf-8")
    return {"ref": str(п), "pointer": "/claims",
            "sha256": hashlib.sha256(тело.encode()).hexdigest()}


def исходное(журнал, *, producer="templates",
             тип="templates.fleet_audit.imported.v1") -> dict:
    L = журнал["L"]
    событие = {"event_id": str(uuid.uuid4()), "event_type": тип,
               "phase": "OBSERVED", "result": "SUCCESS", "scope": "FLEET",
               "environment": "production", "idempotency_key": "src-" + тип,
               "correlation_id": "c-1", "summary": "исходное утверждение"}
    итог = L.append(журнал["соед"], событие, producer_service=producer,
                    actor_id=f"service:{producer}", actor_type="SERVICE",
                    authority="OBSERVE")
    строка = журнал["соед"].execute(
        "SELECT * FROM ledger_event WHERE event_id=?",
        (итог["event_id"],)).fetchone()
    return dict(строка)


def erratum(источник: dict, пространство: dict, исправления: list,
            **прочее) -> dict:
    основа = {
        "event_id": str(uuid.uuid4()),
        "event_type": "audit.claim.erratum.v1", "phase": "SUCCEEDED",
        "result": "SUCCESS", "scope": "FLEET", "environment": "production",
        "correlation_id": "c-err",
        "idempotency_key": "err-" + str(uuid.uuid4())[:8],
        "source_event_id": источник["event_id"],
        "source_ledger_seq": источник["ledger_seq"],
        "source_event_type": источник["event_type"],
        "subject_producer": источник["producer_service"],
        "correction_actor": "architect",
        "correction_authority": "architect:contract-maintainer",
        "reason_code": "RECOMPUTED_FROM_PINNED_EVIDENCE",
        "claim_namespace": пространство,
        "claim_corrections": исправления,
        "summary": "исправление утверждений",
    }
    основа.update(прочее)
    return основа


def добавить(журнал, событие):
    return журнал["L"].append(
        журнал["соед"], событие, producer_service="architect",
        actor_id="service:architect", actor_type="SERVICE", authority="EXECUTE")


# =============================================================================
# Схема и запреты
# =============================================================================

class TestЗапреты:
    def test_исходное_событие_обязано_существовать(self, журнал):
        пр = документ(журнал["tmp"], {"a": 1})
        с = erratum({"event_id": str(uuid.uuid4()), "ledger_seq": 999,
                     "event_type": "x.v1", "producer_service": "templates"},
                    пр, [{"path": "/a", "disposition": "CORRECTED",
                          "replacement_value": 2}])
        with pytest.raises(журнал["L"].LedgerError) as ош:
            добавить(журнал, с)
        assert ош.value.error_code == "ERRATUM_SOURCE_NOT_FOUND"

    def test_событие_не_исправляет_само_себя(self, журнал):
        и = исходное(журнал)
        пр = документ(журнал["tmp"], {"a": 1})
        с = erratum(и, пр, [{"path": "/a", "disposition": "CORRECTED",
                             "replacement_value": 2}])
        с["event_id"] = и["event_id"]
        with pytest.raises(журнал["L"].LedgerError) as ош:
            добавить(журнал, с)
        assert ош.value.error_code in ("ERRATUM_SELF_REFERENCE",
                                       "IDEMPOTENCY_CONFLICT")

    def test_исправление_исправления_запрещено(self, журнал):
        и = исходное(журнал)
        пр = документ(журнал["tmp"], {"a": 1})
        первое = erratum(и, пр, [{"path": "/a", "disposition": "CORRECTED",
                                  "replacement_value": 2}])
        добавить(журнал, первое)
        строка = журнал["соед"].execute(
            "SELECT * FROM ledger_event WHERE event_id=?",
            (первое["event_id"],)).fetchone()
        второе = erratum(dict(строка), пр,
                         [{"path": "/a", "disposition": "CORRECTED",
                           "replacement_value": 3}])
        второе["subject_producer"] = "architect"
        второе["correction_actor"] = "human_owner"
        with pytest.raises(журнал["L"].LedgerError) as ош:
            добавить(журнал, второе)
        assert ош.value.error_code == "ERRATUM_CHAIN_FORBIDDEN"

    def test_исправляющий_не_выдаёт_себя_за_автора(self, журнал):
        и = исходное(журнал)
        пр = документ(журнал["tmp"], {"a": 1})
        с = erratum(и, пр, [{"path": "/a", "disposition": "CORRECTED",
                             "replacement_value": 2}],
                    correction_actor="templates")
        with pytest.raises(журнал["L"].LedgerError) as ош:
            добавить(журнал, с)
        assert ош.value.error_code == "ERRATUM_PRODUCER_IMPERSONATION"

    def test_неизвестный_путь_утверждения(self, журнал):
        и = исходное(журнал)
        пр = документ(журнал["tmp"], {"a": 1})
        с = erratum(и, пр, [{"path": "/нет-такого", "disposition": "CORRECTED",
                             "replacement_value": 2}])
        with pytest.raises(журнал["L"].LedgerError) as ош:
            добавить(журнал, с)
        assert ош.value.error_code == "ERRATUM_CLAIM_PATH_UNKNOWN"

    def test_отозванное_нельзя_заменить_числом(self, журнал):
        и = исходное(журнал)
        пр = документ(журнал["tmp"], {"a": 166})
        с = erratum(и, пр, [{"path": "/a",
                             "disposition": "WITHDRAWN_UNVERIFIED",
                             "replacement_value": 0}])
        with pytest.raises(журнал["L"].LedgerError) as ош:
            добавить(журнал, с)
        assert ош.value.error_code == "ERRATUM_REPLACEMENT_FORBIDDEN"

    def test_исправленное_требует_значения(self, журнал):
        и = исходное(журнал)
        пр = документ(журнал["tmp"], {"a": 49})
        с = erratum(и, пр, [{"path": "/a", "disposition": "CORRECTED"}])
        with pytest.raises(журнал["L"].LedgerError) as ош:
            добавить(журнал, с)
        assert ош.value.error_code == "ERRATUM_REPLACEMENT_REQUIRED"

    def test_прежнее_значение_сверяется_с_доказательством(self, журнал):
        и = исходное(журнал)
        пр = документ(журнал["tmp"], {"a": 49})
        с = erratum(и, пр, [{"path": "/a", "previous_value": 50,
                             "disposition": "CORRECTED",
                             "replacement_value": 48}])
        with pytest.raises(журнал["L"].LedgerError) as ош:
            добавить(журнал, с)
        assert ош.value.error_code == "ERRATUM_PREVIOUS_MISMATCH"

    def test_отпечаток_документа_проверяется(self, журнал):
        и = исходное(журнал)
        пр = документ(журнал["tmp"], {"a": 49})
        пр = {**пр, "sha256": "0" * 64}
        с = erratum(и, пр, [{"path": "/a", "disposition": "CORRECTED",
                             "replacement_value": 48}])
        with pytest.raises(журнал["L"].LedgerError) as ош:
            добавить(журнал, с)
        assert ош.value.error_code == "ERRATUM_NAMESPACE_HASH_MISMATCH"

    def test_документ_вне_разрешённого_корня(self, журнал, tmp_path_factory):
        чужой = tmp_path_factory.mktemp("чужой")
        и = исходное(журнал)
        пр = документ(чужой, {"a": 49})
        с = erratum(и, пр, [{"path": "/a", "disposition": "CORRECTED",
                             "replacement_value": 48}])
        with pytest.raises(журнал["L"].LedgerError) as ош:
            добавить(журнал, с)
        assert ош.value.error_code == "ERRATUM_NAMESPACE_OUTSIDE_ROOT"

    def test_неизвестный_код_причины(self, журнал):
        и = исходное(журнал)
        пр = документ(журнал["tmp"], {"a": 49})
        с = erratum(и, пр, [{"path": "/a", "disposition": "CORRECTED",
                             "replacement_value": 48}],
                    reason_code="ПОТОМУ_ЧТО")
        with pytest.raises(журнал["L"].LedgerError) as ош:
            добавить(журнал, с)
        assert ош.value.error_code == "ERRATUM_REASON_UNKNOWN"

    def test_повторный_путь_в_одном_событии(self, журнал):
        и = исходное(журнал)
        пр = документ(журнал["tmp"], {"a": 49})
        с = erratum(и, пр, [{"path": "/a", "disposition": "CORRECTED",
                             "replacement_value": 48},
                            {"path": "/a", "disposition": "CORRECTED",
                             "replacement_value": 47}])
        with pytest.raises(журнал["L"].LedgerError) as ош:
            добавить(журнал, с)
        assert ош.value.error_code == "ERRATUM_CLAIM_PATH_DUPLICATE"


# =============================================================================
# Запись, проекция, повтор
# =============================================================================

class TestЗаписьИПроекция:
    def _полный(self, журнал):
        и = исходное(журнал)
        пр = документ(журнал["tmp"], {"broken_existing_routes_reported": 49,
                                      "affected_unique_links_reported": 166,
                                      "eligible_unique_links_reported": 169})
        с = erratum(и, пр, [
            {"path": "/broken_existing_routes_reported", "previous_value": 49,
             "disposition": "CORRECTED", "replacement_value": 48},
            {"path": "/affected_unique_links_reported", "previous_value": 166,
             "disposition": "WITHDRAWN_UNVERIFIED"},
            {"path": "/eligible_unique_links_reported", "previous_value": 169,
             "disposition": "WITHDRAWN_UNVERIFIED"}])
        с["idempotency_key"] = "err-полный"
        return и, с

    def test_запись_добавляется(self, журнал):
        и, с = self._полный(журнал)
        итог = добавить(журнал, с)
        assert итог["idempotent_replay"] is False
        строка = журнал["соед"].execute(
            "SELECT corrects_event_id FROM ledger_event WHERE event_id=?",
            (с["event_id"],)).fetchone()
        assert строка["corrects_event_id"] == и["event_id"]

    def test_исходное_событие_не_изменилось(self, журнал):
        и, с = self._полный(журнал)
        до = журнал["соед"].execute(
            "SELECT event_hash, summary FROM ledger_event WHERE event_id=?",
            (и["event_id"],)).fetchone()
        добавить(журнал, с)
        после = журнал["соед"].execute(
            "SELECT event_hash, summary FROM ledger_event WHERE event_id=?",
            (и["event_id"],)).fetchone()
        assert dict(до) == dict(после), "исходная запись обязана остаться"

    def test_проекция_показывает_действующее(self, журнал):
        и, с = self._полный(журнал)
        добавить(журнал, с)
        проекция = журнал["L"].проекция_утверждений(
            журнал["соед"], и["event_id"],
            {"/broken_existing_routes_reported": 49,
             "/affected_unique_links_reported": 166,
             "/eligible_unique_links_reported": 169})
        м = проекция["/broken_existing_routes_reported"]
        assert (м["original_value"], м["disposition"], м["effective_value"]) == (
            49, "CORRECTED", 48)
        for путь in ("/affected_unique_links_reported",
                     "/eligible_unique_links_reported"):
            у = проекция[путь]
            assert у["disposition"] == "WITHDRAWN_UNVERIFIED"
            assert у["effective_value"] is None, (
                "неподтверждённое не показывается числом")
            assert у["erratum_event_id"] == с["event_id"]
            assert у["source_event_id"] == и["event_id"]
            assert у["reason_code"] == "RECOMPUTED_FROM_PINNED_EVIDENCE"

    def test_повтор_не_увеличивает_журнал(self, журнал):
        и, с = self._полный(журнал)
        первый = добавить(журнал, с)
        было = журнал["соед"].execute(
            "SELECT COUNT(*) c FROM ledger_event").fetchone()["c"]
        второй = добавить(журнал, с)
        стало = журнал["соед"].execute(
            "SELECT COUNT(*) c FROM ledger_event").fetchone()["c"]
        assert второй["idempotent_replay"] is True
        assert второй["event_id"] == первый["event_id"]
        assert стало == было

    def test_цепь_журнала_цела(self, журнал):
        и, с = self._полный(журнал)
        добавить(журнал, с)
        итог = журнал["L"].проверить_цепь(журнал["соед"])
        assert итог.get("ok") is True, итог
