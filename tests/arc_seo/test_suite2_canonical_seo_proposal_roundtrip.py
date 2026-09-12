"""Suite 2: canonical_seo_proposal_roundtrip.

Полный положительный путь на одной устойчивой витрине испытаний:

снимок фактов реестра → замысел авторства → детерминированный черновик →
каноническое предложение → проверка и устойчивая запись Control Plane →
канонический набор изменений → событие журнала → рабочая проекция.

Производственный код, эфемерные хранилища. Ни одной прямой записи в базу из
самой проверки: всё идёт через канонический путь.
"""
from __future__ import annotations

import json
import sqlite3

import pytest

from factory.site_engine.changeset import audit_bridge as AB
from factory.site_engine.changeset import model as CM
from factory.site_engine.changeset import store as CS
from factory.site_engine.seo_authoring import schema as SCH
from factory.site_engine.seo_authoring.schema import ProposalRejected
from factory.site_engine.seo_authoring.service import FactPackStore
from factory.site_engine.seo_authoring.testing import (
    замысел, собрать_заявку)

САЙТ = "arc-seo-test-0001"


def подать(служба, заявка, *, служба_имя="seo"):
    return служба.принять(заявка, requester_service=служба_имя,
                          actor_id=f"service:{служба_имя}", actor_type="SERVICE")


# --- полный путь -------------------------------------------------------------

def test_s2_01_полный_путь_даёт_ровно_один_эффект(
        служба, бд, реестр, артефакты, модель, поверхность, двигатель):
    """Снимок фактов → замысел → черновик → предложение → набор → событие.

    Путь заканчивается там, где кончается ответственность этой задачи:
    каноническая запись, канонический набор изменений и событие журнала.
    Одобрение и применение принадлежат уже проверенному контуру CORE-003 и
    требуют выделенной службы подписи, которая читает КАНОНИЧЕСКОЕ
    состояние. Направить её на эфемерные данные значило бы втянуть в
    испытание чужую рабочую службу — и доказать не то.
    """
    з = замысел(САЙТ)
    поверхность.посеять(САЙТ, f"{з['entity_id']}:{з['surface']}:{з['locale']}",
                        {"title": "старое"})
    заявка = собрать_заявку(реестр=реестр, артефакты=артефакты, модель=модель,
                            зам=з, idempotency_key="s2-01")
    итог = подать(служба, заявка)

    assert итог["idempotent_replay"] is False
    assert итог["resource_kind"] == SCH.RESOURCE_KIND
    assert итог["target_environment"] == "test"

    # Предложение устойчиво записано и читается обратно.
    запись = служба.получить(итог["proposal_id"])
    assert запись is not None
    assert запись["durable_writer"] == "control-plane"
    assert запись["content_author"] == "qwen"
    assert запись["requester_service"] == "seo"
    assert запись["owner_service"] == "seo"

    # Канонический набор изменений создан и принадлежит control-plane.
    набор = CS.получить(бд, итог["changeset_id"])
    assert набор is not None
    assert набор["producer_service"] == "control-plane"
    assert набор["resource_type"] == SCH.RESOURCE_KIND
    assert набор["target_site_ids"] == [САЙТ]
    assert набор["status"] == CM.PROPOSED

    # Ровно один положительный эффект: одна запись, один набор, одно событие
    # предложения. Ни одного изменения поверхности — его здесь и не должно
    # быть, применение отдельная стадия.
    assert бд.execute("SELECT count(*) FROM seo_content_proposal"
                      ).fetchone()[0] == 1
    assert бд.execute("SELECT count(*) FROM changeset").fetchone()[0] == 1
    assert бд.execute(
        "SELECT count(*) FROM changeset_outbox WHERE event_type=?",
        ("seo.changeset.proposed.v1",)).fetchone()[0] == 1
    assert поверхность.эффектов() == 0

    # Набор проходит каноническую валидацию: план строится, сухой прогон
    # эффектов не создаёт.
    сводка = двигатель.валидировать(итог["changeset_id"],
                                    actor_id="service:control-plane",
                                    служба="control-plane")
    assert сводка["dry_run_effects"] == 0
    assert сводка["environments"] == ["test"]
    assert поверхность.эффектов() == 0
    assert CS.получить(бд, итог["changeset_id"])["status"] == CM.VALIDATED


def test_s2_01b_без_одобрения_применение_не_происходит(
        служба, бд, реестр, артефакты, модель, поверхность, двигатель):
    """Ворота одобрения держат. Обходить их испытание не вправе."""
    з = замысел(САЙТ)
    поверхность.посеять(САЙТ, f"{з['entity_id']}:{з['surface']}:{з['locale']}",
                        {"title": "старое"})
    заявка = собрать_заявку(реестр=реестр, артефакты=артефакты, модель=модель,
                            зам=з, idempotency_key="s2-01b")
    итог = подать(служба, заявка)
    двигатель.валидировать(итог["changeset_id"],
                           actor_id="service:control-plane",
                           служба="control-plane")
    аренда = CS.взять_аренду(бд, итог["changeset_id"], "worker-s2b")
    with pytest.raises(CS.ChangeSetError) as ош:
        двигатель.применить(итог["changeset_id"],
                            actor_id="service:control-plane",
                            служба="control-plane",
                            fencing_token=аренда["fencing_token"])
    assert ош.value.error_code in ("APPROVAL_REQUIRED", "TRANSITION_NOT_ALLOWED")
    assert поверхность.эффектов() == 0, "применение прошло без одобрения"


def test_s2_01c_адаптер_исполняется_полным_циклом(поверхность):
    """Адаптер действительно исполним: шесть операций на живом хранилище.

    Именно это делает `changeset.adapter.seo=AVAILABLE` утверждением о
    факте, а не строкой в каталоге.
    """
    site, rid = САЙТ, "anime-0001:title:ru"
    поверхность.посеять(site, rid, {"title": "старое"})
    возм = поверхность.capabilities()
    assert возм["supports_observe"] and возм["supports_dry_run"]
    assert возм["supports_rollback"] and возм["live_writes"] is False

    было = поверхность.observe(site_id=site, resource_id=rid)
    план = поверхность.plan(
        site_id=site, resource_id=rid, operation="update",
        requested_change={"operations": [{"op": "set", "path": "/title",
                                          "value_digest": "a" * 64}],
                          "artifact_digest": "b" * 64},
        observed=было)
    assert план["reversible"] and not план["empty"]

    сухо = поверхность.dry_run(site_id=site, plan=план)
    assert сухо["effects"] == 0 and поверхность.эффектов() == 0
    assert поверхность.observe(site_id=site, resource_id=rid)["state"] == \
        {"title": "старое"}, "сухой прогон изменил ресурс"

    применение = поверхность.apply(site_id=site, plan=план, fencing_token=1)
    assert применение["applied"] is True
    assert поверхность.эффектов(kind="apply") == 1

    наблюдение = поверхность.observe(site_id=site, resource_id=rid)
    проверка = поверхность.verify(site_id=site, plan=план, observed=наблюдение)
    assert проверка["ok"] is True

    # Повтор того же плана второго эффекта не создаёт.
    повтор = поверхность.apply(site_id=site, plan=план, fencing_token=2)
    assert повтор["idempotent_replay"] is True
    assert поверхность.эффектов(kind="apply") == 1

    откат = поверхность.rollback(site_id=site, plan=план,
                                 before_fingerprint=план["before_fingerprint"],
                                 fencing_token=3)
    assert откат["restored"] is True
    assert поверхность.observe(site_id=site, resource_id=rid)["state"] == \
        {"title": "старое"}


def test_s2_02_повтор_возвращает_те_же_идентификаторы(
        служба, бд, реестр, артефакты, модель):
    заявка = собрать_заявку(реестр=реестр, артефакты=артефакты, модель=модель,
                            idempotency_key="s2-02")
    первый = подать(служба, заявка)
    второй = подать(служба, заявка)
    третий = подать(служба, dict(заявка))

    assert первый["proposal_id"] == второй["proposal_id"] == третий["proposal_id"]
    assert первый["changeset_id"] == второй["changeset_id"] == третий["changeset_id"]
    assert второй["idempotent_replay"] and третий["idempotent_replay"]

    # Ничего не выросло.
    предложений = бд.execute(
        "SELECT count(*) FROM seo_content_proposal").fetchone()[0]
    наборов = бд.execute("SELECT count(*) FROM changeset").fetchone()[0]
    событий = бд.execute("SELECT count(*) FROM changeset_outbox").fetchone()[0]
    assert предложений == 1 and наборов == 1
    assert событий == 2, f"событий {событий}: ожидались proposed набора и SEO"


def test_s2_03_отпечатки_устойчивы(реестр, артефакты, модель):
    """Один замысел — один черновик — один отпечаток, от прогона к прогону."""
    a = собрать_заявку(реестр=реестр, артефакты=артефакты, модель=модель,
                       idempotency_key="s2-03")
    b = собрать_заявку(реестр=реестр, артефакты=артефакты, модель=модель,
                       idempotency_key="s2-03")
    for поле in ("artifact_digest", "source_snapshot_sha256",
                 "draft_revision_id", "correlation_id", "intent_id"):
        assert a[поле] == b[поле], поле
    assert модель.live_calls == 0 and модель.model_downloads == 0


def test_s2_04_тот_же_ключ_другое_содержимое_конфликт(
        служба, реестр, артефакты, модель):
    заявка = собрать_заявку(реестр=реестр, артефакты=артефакты, модель=модель,
                            idempotency_key="s2-04")
    подать(служба, заявка)
    другая = собрать_заявку(реестр=реестр, артефакты=артефакты, модель=модель,
                            зам=замысел(САЙТ, entity_id="anime-0002"),
                            idempotency_key="s2-04")
    with pytest.raises(ProposalRejected) as ош:
        подать(служба, другая)
    assert ош.value.error_code == "IDEMPOTENCY_CONFLICT"
    assert ош.value.status == 409


def test_s2_05_чужая_витрина_отвергается_до_эффекта(
        служба, бд, реестр, артефакты, модель, поверхность):
    # Заявка собирается для известной витрины, а подменяется уже готовая:
    # иначе до службы дело не дойдёт — оснастка сама упрётся в неизвестный
    # site_id, и проверено окажется не то, что заявлено.
    заявка = собрать_заявку(реестр=реестр, артефакты=артефакты, модель=модель,
                            idempotency_key="s2-05")
    заявка["site_id"] = "arc-seo-unknown-9999"
    with pytest.raises(ProposalRejected) as ош:
        подать(служба, заявка)
    assert ош.value.error_code == "SITE_ID_UNKNOWN"
    assert бд.execute("SELECT count(*) FROM seo_content_proposal").fetchone()[0] == 0
    assert бд.execute("SELECT count(*) FROM changeset").fetchone()[0] == 0
    assert поверхность.эффектов() == 0


def test_s2_06_чужое_окружение_отвергается_до_эффекта(
        служба, бд, реестр, артефакты, модель, поверхность):
    заявка = собрать_заявку(реестр=реестр, артефакты=артефакты, модель=модель,
                            зам=замысел("arc-seo-prod-0004"),
                            idempotency_key="s2-06")
    with pytest.raises(ProposalRejected) as ош:
        подать(служба, заявка)
    assert ош.value.error_code == "PRODUCTION_TARGET_DENIED"
    assert бд.execute("SELECT count(*) FROM changeset").fetchone()[0] == 0
    assert поверхность.эффектов() == 0


def test_s2_07_прямого_обхода_хранилища_нет(служба, бд, реестр, артефакты, модель):
    """Предложение без набора изменений создать нельзя даже изнутри.

    Внешний ключ и одна транзакция — не украшение: они делают невозможным
    состояние «предложение есть, набора нет», которое выглядело бы исправным
    и разошлось бы позже.
    """
    with pytest.raises(sqlite3.IntegrityError):
        бд.execute(
            "INSERT INTO seo_content_proposal(proposal_id, schema_version, "
            "resource_kind, resource_version, changeset_id, site_id, entity_id, "
            "entity_kind, surface, locale, fact_pack_ref, "
            "source_snapshot_sha256, artifact_ref, artifact_digest, "
            "model_version, prompt_version, policy_version, content_author, "
            "requested_by, requester_service, durable_writer, owner_service, "
            "audience, target_environment, correlation_id, causation_id, "
            "idempotency_key, payload_digest, operations, accepted_at) "
            "VALUES(" + ",".join("?" * 30) + ")",
            ("обход", "v", "k", "1", "нет-такого-набора", "s", "e", "k", "s",
             "ru", "f", "0" * 64, "a", "0" * 64, "m", "p", "pol", "qwen",
             "service:qwen", "qwen", "qwen", "qwen", "internal", "test",
             "c", "c", "i", "0" * 64, "[]", "t"))


def test_s2_08_событие_предложения_уходит_штатным_ящиком(
        служба, бд, реестр, артефакты, модель, monkeypatch):
    заявка = собрать_заявку(реестр=реестр, артефакты=артефакты, модель=модель,
                            idempotency_key="s2-08")
    итог = подать(служба, заявка)
    строки = [dict(r) for r in бд.execute(
        "SELECT * FROM changeset_outbox WHERE changeset_id=? ORDER BY seq",
        (итог["changeset_id"],))]
    типы = [s["event_type"] for s in строки]
    assert "seo.changeset.proposed.v1" in типы, типы
    событие = next(s for s in строки
                   if s["event_type"] == "seo.changeset.proposed.v1")
    нагрузка = json.loads(событие["payload"])
    assert нагрузка["proposal_id"] == итог["proposal_id"]
    assert нагрузка["producer_service"] == "control-plane"
    assert нагрузка["content_author"] == "qwen"
    assert нагрузка["owner_service"] == "seo"
    assert нагрузка["correlation_id"] and нагрузка["causation_id"]
    # Доставка идёт тем же мостом, что и всё остальное; второго журнала нет.
    отправлено = []
    monkeypatch.setattr(AB, "отправить",
                        lambda з, **k: (отправлено.append(з["idempotency_key"])
                                        or {"status": 201, "body": {}}))
    сводка = AB.опубликовать(бд)
    assert сводка["backlog"] == 0 and сводка["dlq"] == 0
    assert len(отправлено) == len(set(отправлено)), "дубли ключей доставки"


def test_s2_09_снимок_фактов_связывает_предложение_с_реестром(
        служба, реестр, артефакты, модель):
    заявка = собрать_заявку(реестр=реестр, артефакты=артефакты, модель=модель,
                            idempotency_key="s2-09")
    итог = подать(служба, заявка)
    запись = служба.получить(итог["proposal_id"])
    снимок = FactPackStore(реестр).снимок(САЙТ)
    assert запись["source_snapshot_sha256"] == снимок["sha256"]
    # Факты сдвинулись — тот же снимок больше не принимается.
    реестр.сдвинуть_версию()
    новая = собрать_заявку(реестр=реестр, артефакты=артефакты, модель=модель,
                           idempotency_key="s2-09-new")
    новая["source_snapshot_sha256"] = заявка["source_snapshot_sha256"]
    with pytest.raises(ProposalRejected) as ош:
        подать(служба, новая)
    assert ош.value.error_code == "SOURCE_SNAPSHOT_STALE"


def test_s2_10_две_витрины_не_мешают_друг_другу(
        служба, бд, реестр, артефакты, модель):
    a = собрать_заявку(реестр=реестр, артефакты=артефакты, модель=модель,
                       зам=замысел("arc-seo-test-0001"), idempotency_key="s2-10-a")
    b = собрать_заявку(реестр=реестр, артефакты=артефакты, модель=модель,
                       зам=замысел("arc-seo-test-0002"), idempotency_key="s2-10-b")
    ia, ib = подать(служба, a), подать(служба, b)
    assert ia["proposal_id"] != ib["proposal_id"]
    assert ia["changeset_id"] != ib["changeset_id"]
    assert бд.execute("SELECT count(*) FROM changeset").fetchone()[0] == 2
