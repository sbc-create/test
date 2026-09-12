"""Suite 3: audit_replay_recovery_rollback.

Журнал берётся настоящий — те же production-классы Audit Ledger, — но на
эфемерной базе. Канонический журнал в этих проверках не участвует.
"""
from __future__ import annotations

import json
import sqlite3

import pytest

from factory.site_engine.audit import ledger_store as LS
from factory.site_engine.audit import projection as LP
from factory.site_engine.changeset import audit_bridge as AB
from factory.site_engine.changeset import store as CS
from factory.site_engine.seo_authoring import schema as SCH
from factory.site_engine.seo_authoring.testing import замысел, собрать_заявку

САЙТ = "arc-seo-test-0001"


@pytest.fixture()
def журнал(tmp_path, monkeypatch):
    """Эфемерный Audit Ledger на production-классах."""
    путь = tmp_path / "ledger.sqlite3"
    monkeypatch.setenv("AUDIT_LEDGER_DB", str(путь))
    соед = LS.открыть(путь)
    LP.подготовить(соед)
    yield соед
    соед.close()


def подать(служба, заявка):
    return служба.принять(заявка, requester_service="seo",
                          actor_id="service:seo", actor_type="SERVICE")


def доставить(бд, журнал, *, известные_сайты=None) -> list[str]:
    """Слить ящик контура в журнал через штатный мост.

    Мост ходит по HTTP; здесь он заменён прямой записью в тот же журнал теми
    же production-классами. Подменяется транспорт, не приёмник: второго
    журнала не появляется.
    """
    доставленные = []

    def отправить(запись, **_):
        нагрузка = json.loads(запись["payload"])
        цели = нагрузка.get("target_site_ids") or []
        тело = {
            "event_type": запись["event_type"],
            "phase": AB.ФАЗА_ПО_СОСТОЯНИЮ.get(
                нагрузка.get("to_status") or нагрузка.get("status") or "", "OBSERVED"),
            "result": AB.РЕЗУЛЬТАТ_ПО_СОСТОЯНИЮ.get(
                нагрузка.get("to_status") or нагрузка.get("status") or "", "PENDING"),
            "scope": "SITE" if len(цели) == 1 else "FLEET",
            "site_id": цели[0] if len(цели) == 1 else None,
            "environment": "control-plane",
            "resource_type": нагрузка.get("resource_type"),
            "resource_id": нагрузка.get("resource_id"),
            "resource_owner": нагрузка.get("owner_service") or "control-plane",
            "correlation_id": нагрузка.get("correlation_id"),
            "causation_id": нагрузка.get("causation_id"),
            "action_id": нагрузка.get("changeset_id"),
            "idempotency_key": запись["idempotency_key"],
            "occurred_at": нагрузка.get("occurred_at") or запись["created_at"],
            "summary": AB._сводка(запись, нагрузка),
        }
        LS.append(журнал, тело, producer_service="changeset-worker",
                  actor_id="service:changeset-worker", actor_type="SERVICE",
                  authority="OBSERVE", известные_сайты=известные_сайты)
        доставленные.append(запись["idempotency_key"])
        return {"status": 201, "body": {}}

    прежний = AB.отправить
    AB.отправить = отправить
    try:
        сводка = AB.опубликовать(бд)
    finally:
        AB.отправить = прежний
    return доставленные, сводка


# --- журнал получает правильные сведения ------------------------------------

def test_s3_01_событие_несёт_актора_производителя_владельца_и_витрину(
        служба, бд, журнал, реестр, артефакты, модель):
    заявка = собрать_заявку(реестр=реестр, артефакты=артефакты, модель=модель,
                            idempotency_key="s3-01")
    итог = подать(служба, заявка)
    доставленные, сводка = доставить(бд, журнал, известные_сайты={САЙТ})
    assert сводка["backlog"] == 0 and сводка["dlq"] == 0

    строки = [dict(r) for r in журнал.execute(
        "SELECT * FROM ledger_event WHERE event_type=?",
        ("seo.changeset.proposed.v1",))]
    assert len(строки) == 1, строки
    с = строки[0]
    # Контур — control-plane; публикующая личность — changeset-worker.
    # Различие намеренное: по записи видно, какой процесс её сделал.
    assert с["producer_service"] == "changeset-worker"
    assert с["actor_type"] == "SERVICE"
    assert с["resource_type"] == SCH.RESOURCE_KIND
    assert с["site_id"] == САЙТ
    assert с["resource_owner"] == "seo", "владелец домена потерян"
    assert с["action_id"] == итог["changeset_id"]
    assert с["correlation_id"] and с["causation_id"]


def test_s3_02_сырой_журнал_и_проекция_совпадают(
        служба, бд, журнал, реестр, артефакты, модель):
    подать(служба, собрать_заявку(реестр=реестр, артефакты=артефакты,
                                  модель=модель, idempotency_key="s3-02"))
    доставить(бд, журнал, известные_сайты={САЙТ})
    LP.пересобрать(журнал)
    сырых = журнал.execute("SELECT count(*) FROM ledger_event").fetchone()[0]
    исключено = len(LP.позиции_в_карантине(журнал))
    рабочих = сырых - исключено
    assert исключено == 0, "в чистом журнале нечего исключать"
    assert рабочих == сырых
    позиции_сырые = {r[0] for r in журнал.execute(
        "SELECT ledger_seq FROM ledger_event")}
    т = LP.активная(журнал)
    позиции_проекции = {r[0] for r in журнал.execute(
        f"SELECT ledger_seq FROM {т}")}
    assert позиции_сырые == позиции_проекции, "проекция разошлась с журналом"


def test_s3_03_цепь_журнала_цела(служба, бд, журнал, реестр, артефакты, модель):
    for i in range(3):
        подать(служба, собрать_заявку(реестр=реестр, артефакты=артефакты,
                                      модель=модель,
                                      зам=замысел(САЙТ, entity_id=f"anime-{i:04d}"),
                                      idempotency_key=f"s3-03-{i}"))
    доставить(бд, журнал, известные_сайты={САЙТ})
    п = LS.проверить_цепь(журнал)
    assert п["ok"] is True, п
    assert п["verified"] >= 3


# --- повтор и дубли ----------------------------------------------------------

def test_s3_04_повтор_доставки_даёт_нулевую_разницу(
        служба, бд, журнал, реестр, артефакты, модель):
    подать(служба, собрать_заявку(реестр=реестр, артефакты=артефакты,
                                  модель=модель, idempotency_key="s3-04"))
    доставить(бд, журнал, известные_сайты={САЙТ})
    было = журнал.execute("SELECT count(*) FROM ledger_event").fetchone()[0]
    корень = журнал.execute("SELECT event_hash FROM ledger_event "
                            "ORDER BY ledger_seq DESC LIMIT 1").fetchone()[0]

    # Повторная публикация: ящик уже отмечен, отправлять нечего.
    _, сводка = доставить(бд, журнал, известные_сайты={САЙТ})
    assert сводка["published"] == 0 and сводка["backlog"] == 0

    # И прямой повтор той же записи журнала поглощается идемпотентностью.
    запись = dict(журнал.execute(
        "SELECT * FROM ledger_event WHERE event_type=? LIMIT 1",
        ("seo.changeset.proposed.v1",)).fetchone())
    повтор = LS.append(журнал, {
        "event_type": запись["event_type"], "phase": запись["phase"],
        "result": запись["result"], "scope": запись["scope"],
        "site_id": запись["site_id"], "environment": запись["environment"],
        "resource_type": запись["resource_type"],
        "resource_id": запись["resource_id"],
        "resource_owner": запись["resource_owner"],
        "correlation_id": запись["correlation_id"],
        "causation_id": запись["causation_id"],
        "action_id": запись["action_id"],
        "idempotency_key": запись["idempotency_key"],
        "occurred_at": запись["occurred_at"], "summary": запись["summary"],
    }, producer_service="changeset-worker",
        actor_id="service:changeset-worker",
        actor_type="SERVICE", authority="OBSERVE",
        известные_сайты={САЙТ})
    assert повтор["idempotent_replay"] is True
    стало = журнал.execute("SELECT count(*) FROM ledger_event").fetchone()[0]
    assert стало == было, f"журнал вырос: {было} -> {стало}"
    assert журнал.execute("SELECT event_hash FROM ledger_event ORDER BY "
                          "ledger_seq DESC LIMIT 1").fetchone()[0] == корень


def test_s3_05_дублей_и_сирот_нет(служба, бд, журнал, реестр, артефакты, модель):
    for i in range(4):
        подать(служба, собрать_заявку(реестр=реестр, артефакты=артефакты,
                                      модель=модель,
                                      зам=замысел(САЙТ, entity_id=f"anime-9{i:03d}"),
                                      idempotency_key=f"s3-05-{i}"))
    доставить(бд, журнал, известные_сайты={САЙТ})
    ключи = [r[0] for r in журнал.execute(
        "SELECT idempotency_key FROM ledger_event")]
    assert len(ключи) == len(set(ключи)), "дубли в журнале"

    # Сироты: предложение без набора и набор без предложения.
    сироты_предложений = бд.execute(
        "SELECT count(*) FROM seo_content_proposal p LEFT JOIN changeset c "
        "ON c.changeset_id = p.changeset_id WHERE c.changeset_id IS NULL"
    ).fetchone()[0]
    сироты_наборов = бд.execute(
        "SELECT count(*) FROM changeset c LEFT JOIN seo_content_proposal p "
        "ON p.changeset_id = c.changeset_id WHERE p.proposal_id IS NULL AND "
        "c.resource_type=?", (SCH.RESOURCE_KIND,)).fetchone()[0]
    assert сироты_предложений == 0 and сироты_наборов == 0
    assert бд.execute("SELECT count(*) FROM changeset_outbox WHERE "
                      "published_at IS NULL").fetchone()[0] == 0


# --- восстановление ----------------------------------------------------------

def test_s3_06_прерванная_доставка_восстанавливается_ящиком(
        служба, бд, журнал, реестр, артефакты, модель):
    """Падение между записью и доставкой не теряет событие."""
    подать(служба, собрать_заявку(реестр=реестр, артефакты=артефакты,
                                  модель=модель, idempotency_key="s3-06"))
    ждут = бд.execute("SELECT count(*) FROM changeset_outbox WHERE "
                      "published_at IS NULL").fetchone()[0]
    assert ждут >= 2

    # Доставка срывается на первой же записи.
    def падать(запись, **_):
        raise AB.LedgerUnavailable("журнал недоступен (испытание)")

    прежний = AB.отправить
    AB.отправить = падать
    try:
        сводка = AB.опубликовать(бд)
    finally:
        AB.отправить = прежний
    assert сводка["published"] == 0
    assert сводка["backlog"] == ждут, "событие потеряно при сбое доставки"
    assert журнал.execute("SELECT count(*) FROM ledger_event").fetchone()[0] == 0

    # Восстановление: всё доходит, задолженность обнуляется.
    _, сводка2 = доставить(бд, журнал, известные_сайты={САЙТ})
    assert сводка2["backlog"] == 0
    assert журнал.execute("SELECT count(*) FROM ledger_event").fetchone()[0] == ждут


def test_s3_07_потерянный_ответ_не_создаёт_второй_записи(
        служба, бд, реестр, артефакты, модель):
    """Клиент не увидел ответа и повторил. Записей всё равно одна."""
    заявка = собрать_заявку(реестр=реестр, артефакты=артефакты, модель=модель,
                            idempotency_key="s3-07")
    первый = подать(служба, заявка)          # ответ «потерян»
    второй = подать(служба, заявка)          # клиент повторил
    assert первый["proposal_id"] == второй["proposal_id"]
    assert первый["changeset_id"] == второй["changeset_id"]
    assert второй["idempotent_replay"] is True
    assert бд.execute("SELECT count(*) FROM seo_content_proposal"
                      ).fetchone()[0] == 1
    assert бд.execute("SELECT count(*) FROM changeset").fetchone()[0] == 1


# --- откат и возврат вперёд --------------------------------------------------

def test_s3_08_откат_выполняется_и_состояние_проверяется(поверхность):
    site, rid = САЙТ, "anime-0001:title:ru"
    поверхность.посеять(site, rid, {"title": "исходное"})
    было = поверхность.observe(site_id=site, resource_id=rid)
    план = поверхность.plan(
        site_id=site, resource_id=rid, operation="update",
        requested_change={"operations": [{"op": "set", "path": "/title",
                                          "value_digest": "c" * 64}],
                          "artifact_digest": "d" * 64},
        observed=было)
    поверхность.apply(site_id=site, plan=план, fencing_token=1)
    после = поверхность.observe(site_id=site, resource_id=rid)
    assert после["fingerprint"] == план["expected_fingerprint"]

    откат = поверхность.rollback(site_id=site, plan=план,
                                 before_fingerprint=план["before_fingerprint"],
                                 fencing_token=2)
    assert откат["restored"] is True
    # Состояние проверяется наблюдением, а не ответом адаптера.
    проверено = поверхность.observe(site_id=site, resource_id=rid)
    assert проверено["fingerprint"] == план["before_fingerprint"]
    assert проверено["state"] == {"title": "исходное"}

    # Возврат вперёд даёт тот же результат, что и первое применение.
    поверхность.apply(site_id=site, plan=план, fencing_token=3)
    вперёд = поверхность.observe(site_id=site, resource_id=rid)
    assert вперёд["fingerprint"] == после["fingerprint"]


def test_s3_09_повторный_откат_идемпотентен(поверхность):
    site, rid = САЙТ, "anime-0002:title:ru"
    поверхность.посеять(site, rid, {"title": "исходное"})
    было = поверхность.observe(site_id=site, resource_id=rid)
    план = поверхность.plan(
        site_id=site, resource_id=rid, operation="update",
        requested_change={"operations": [{"op": "set", "path": "/title",
                                          "value_digest": "e" * 64}],
                          "artifact_digest": "f" * 64},
        observed=было)
    поверхность.apply(site_id=site, plan=план, fencing_token=1)
    поверхность.rollback(site_id=site, plan=план,
                         before_fingerprint=план["before_fingerprint"],
                         fencing_token=2)
    откатов = поверхность.эффектов(kind="rollback")
    повтор = поверхность.rollback(site_id=site, plan=план,
                                  before_fingerprint=план["before_fingerprint"],
                                  fencing_token=3)
    assert повтор["idempotent_replay"] is True
    assert поверхность.эффектов(kind="rollback") == откатов


def test_s3_10_отозванный_доступ_не_оживает(служба, реестр, артефакты, модель):
    """Служба, лишённая права подавать, не возвращает его повтором."""
    from factory.site_engine.changeset import model as CM
    заявка = собрать_заявку(реестр=реестр, артефакты=артефакты, модель=модель,
                            idempotency_key="s3-10")
    прежние = CM.ПРАВА["seo"]
    CM.ПРАВА["seo"] = set()
    try:
        with pytest.raises(SCH.ProposalRejected) as ош:
            подать(служба, заявка)
        assert ош.value.error_code == "ROLE_NOT_GRANTED"
        # Повтор того же запроса права не возвращает.
        with pytest.raises(SCH.ProposalRejected):
            подать(служба, заявка)
    finally:
        CM.ПРАВА["seo"] = прежние
    # Право вернули — и только теперь заявка проходит.
    итог = подать(служба, заявка)
    assert итог["idempotent_replay"] is False
