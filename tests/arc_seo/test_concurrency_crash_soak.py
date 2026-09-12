"""Конкуренция, аварийные окна и длительный прогон.

Проверяется не «работает под нагрузкой», а инвариант: сколько бы раз и
одновременно ни пришёл один и тот же запрос, устойчивый результат один.
"""
from __future__ import annotations

import concurrent.futures as fut
import sqlite3

import pytest

from factory.site_engine.changeset import store as CS
from factory.site_engine.seo_authoring.schema import ProposalRejected
from factory.site_engine.seo_authoring.service import (
    ArtifactStore, SeoProposalService)
from factory.site_engine.seo_authoring.testing import (
    DeterministicQwen, FakeRegistry, замысел, собрать_заявку)

САЙТ = "arc-seo-test-0001"
ПАРАЛЛЕЛЬНЫХ = 16
SOAK_ЦИКЛОВ = 20


def служба_на(путь, реестр, артефакты) -> tuple:
    соед = CS.открыть(путь)
    return соед, SeoProposalService(соед, реестр=реестр, артефакты=артефакты)


@pytest.fixture()
def окружение(tmp_path, monkeypatch):
    monkeypatch.setenv("CHANGESET_APPROVAL_KEY", "conc-ключ-0123456789")
    monkeypatch.setenv("APPROVAL_CALLER", "control-plane")
    реестр, артефакты, модель = FakeRegistry(), ArtifactStore(), DeterministicQwen()
    return {"путь": tmp_path / "cs.sqlite3", "реестр": реестр,
            "артефакты": артефакты, "модель": модель}


def подсчёт(путь) -> dict:
    c = sqlite3.connect(f"file:{путь}?mode=ro", uri=True)
    try:
        предложений = c.execute(
            "SELECT count(*) FROM seo_content_proposal").fetchone()[0]
        наборов = c.execute("SELECT count(*) FROM changeset").fetchone()[0]
        событий = c.execute(
            "SELECT count(*) FROM changeset_outbox WHERE event_type=?",
            ("seo.changeset.proposed.v1",)).fetchone()[0]
        задолженность = c.execute(
            "SELECT count(*) FROM changeset_outbox WHERE published_at IS NULL"
        ).fetchone()[0]
    finally:
        c.close()
    return {"proposals": предложений, "changesets": наборов,
            "events": событий, "backlog": задолженность}


# --- конкуренция -------------------------------------------------------------

def test_c01_шестнадцать_одновременных_одинаковых_запросов(окружение):
    заявка = собрать_заявку(реестр=окружение["реестр"],
                            артефакты=окружение["артефакты"],
                            модель=окружение["модель"], idempotency_key="c01")
    # Таблицы создаются заранее: гонка проверяется на приёме, а не на схеме.
    соед, _ = служба_на(окружение["путь"], окружение["реестр"],
                        окружение["артефакты"])
    соед.close()

    def подать(_):
        соед, служба = служба_на(окружение["путь"], окружение["реестр"],
                                 окружение["артефакты"])
        try:
            return служба.принять(заявка, requester_service="seo",
                                  actor_id="service:seo", actor_type="SERVICE")
        except ProposalRejected as e:
            return {"error": e.error_code}
        finally:
            соед.close()

    with fut.ThreadPoolExecutor(max_workers=ПАРАЛЛЕЛЬНЫХ) as п:
        ответы = list(п.map(подать, range(ПАРАЛЛЕЛЬНЫХ)))

    ошибки = [о for о in ответы if "error" in о]
    assert not ошибки, f"отказы при конкуренции: {ошибки[:3]}"
    предложения = {о["proposal_id"] for о in ответы}
    наборы = {о["changeset_id"] for о in ответы}
    победителей = sum(1 for о in ответы if о["idempotent_replay"] is False)
    assert len(предложения) == 1, f"разных предложений: {len(предложения)}"
    assert len(наборы) == 1, f"разных наборов: {len(наборы)}"
    assert победителей == 1, f"победителей: {победителей}"

    итог = подсчёт(окружение["путь"])
    assert итог["proposals"] == 1 and итог["changesets"] == 1
    assert итог["events"] == 1, f"событий предложения: {итог['events']}"


def test_c02_разные_ключи_идут_параллельно_без_смешения(окружение):
    соед, _ = служба_на(окружение["путь"], окружение["реестр"],
                        окружение["артефакты"])
    соед.close()
    заявки = [собрать_заявку(реестр=окружение["реестр"],
                             артефакты=окружение["артефакты"],
                             модель=окружение["модель"],
                             зам=замысел(САЙТ, entity_id=f"anime-{i:04d}"),
                             idempotency_key=f"c02-{i}")
              for i in range(ПАРАЛЛЕЛЬНЫХ)]

    def подать(з):
        соед, служба = служба_на(окружение["путь"], окружение["реестр"],
                                 окружение["артефакты"])
        try:
            return служба.принять(з, requester_service="seo",
                                  actor_id="service:seo", actor_type="SERVICE")
        finally:
            соед.close()

    with fut.ThreadPoolExecutor(max_workers=ПАРАЛЛЕЛЬНЫХ) as п:
        ответы = list(п.map(подать, заявки))
    assert len({о["proposal_id"] for о in ответы}) == ПАРАЛЛЕЛЬНЫХ
    assert len({о["changeset_id"] for о in ответы}) == ПАРАЛЛЕЛЬНЫХ
    итог = подсчёт(окружение["путь"])
    assert итог["proposals"] == ПАРАЛЛЕЛЬНЫХ == итог["changesets"]


# --- аварийные окна ----------------------------------------------------------

def test_c03_авария_до_устойчивой_записи(окружение, monkeypatch):
    """Падение до записи не оставляет ни предложения, ни набора."""
    соед, служба = служба_на(окружение["путь"], окружение["реестр"],
                             окружение["артефакты"])
    заявка = собрать_заявку(реестр=окружение["реестр"],
                            артефакты=окружение["артефакты"],
                            модель=окружение["модель"], idempotency_key="c03")
    try:
        monkeypatch.setattr(CS, "создать",
                            lambda *a, **k: (_ for _ in ()).throw(
                                RuntimeError("авария до записи")))
        with pytest.raises(RuntimeError):
            служба.принять(заявка, requester_service="seo",
                           actor_id="service:seo", actor_type="SERVICE")
    finally:
        соед.close()
    итог = подсчёт(окружение["путь"])
    assert итог == {"proposals": 0, "changesets": 0, "events": 0, "backlog": 0}

    # Восстановление: повтор проходит и даёт ровно один результат.
    monkeypatch.undo()
    соед, служба = служба_на(окружение["путь"], окружение["реестр"],
                             окружение["артефакты"])
    try:
        итог2 = служба.принять(заявка, requester_service="seo",
                               actor_id="service:seo", actor_type="SERVICE")
    finally:
        соед.close()
    assert итог2["idempotent_replay"] is False
    assert подсчёт(окружение["путь"])["proposals"] == 1


def test_c04_авария_после_записи_до_подтверждения_ящика(окружение):
    """Запись прошла, ящик не подтверждён: событие ждёт, а не теряется."""
    соед, служба = служба_на(окружение["путь"], окружение["реестр"],
                             окружение["артефакты"])
    заявка = собрать_заявку(реестр=окружение["реестр"],
                            артефакты=окружение["артефакты"],
                            модель=окружение["модель"], idempotency_key="c04")
    try:
        служба.принять(заявка, requester_service="seo",
                       actor_id="service:seo", actor_type="SERVICE")
    finally:
        соед.close()
    итог = подсчёт(окружение["путь"])
    assert итог["proposals"] == 1 and итог["changesets"] == 1
    assert итог["backlog"] >= 2, "события не дождались доставки"

    # «Перезапуск»: новое соединение, тот же запрос — второго эффекта нет.
    соед, служба = служба_на(окружение["путь"], окружение["реестр"],
                             окружение["артефакты"])
    try:
        повтор = служба.принять(заявка, requester_service="seo",
                                actor_id="service:seo", actor_type="SERVICE")
    finally:
        соед.close()
    assert повтор["idempotent_replay"] is True
    assert подсчёт(окружение["путь"])["proposals"] == 1


def test_c05_авария_после_набора_до_публикации_журнала(окружение, monkeypatch):
    from factory.site_engine.changeset import audit_bridge as AB
    соед, служба = служба_на(окружение["путь"], окружение["реестр"],
                             окружение["артефакты"])
    заявка = собрать_заявку(реестр=окружение["реестр"],
                            артефакты=окружение["артефакты"],
                            модель=окружение["модель"], idempotency_key="c05")
    try:
        служба.принять(заявка, requester_service="seo",
                       actor_id="service:seo", actor_type="SERVICE")
        monkeypatch.setattr(AB, "отправить",
                            lambda з, **k: (_ for _ in ()).throw(
                                AB.LedgerUnavailable("журнал недоступен")))
        сводка = AB.опубликовать(соед)
        assert сводка["published"] == 0 and сводка["backlog"] > 0
        monkeypatch.undo()
        monkeypatch.setattr(AB, "отправить",
                            lambda з, **k: {"status": 201, "body": {}})
        сводка2 = AB.опубликовать(соед)
        assert сводка2["backlog"] == 0
    finally:
        соед.close()
    assert подсчёт(окружение["путь"])["proposals"] == 1


def test_c06_авария_после_эффекта_до_ответа_клиенту(окружение):
    """Клиент не получил ответа и повторил; результат остаётся один."""
    соед, служба = служба_на(окружение["путь"], окружение["реестр"],
                             окружение["артефакты"])
    заявка = собрать_заявку(реестр=окружение["реестр"],
                            артефакты=окружение["артефакты"],
                            модель=окружение["модель"], idempotency_key="c06")
    try:
        первый = служба.принять(заявка, requester_service="seo",
                                actor_id="service:seo", actor_type="SERVICE")
        # Ответ «потерян» — клиент повторяет трижды.
        повторы = [служба.принять(заявка, requester_service="seo",
                                  actor_id="service:seo", actor_type="SERVICE")
                   for _ in range(3)]
    finally:
        соед.close()
    assert all(п["proposal_id"] == первый["proposal_id"] for п in повторы)
    assert all(п["idempotent_replay"] for п in повторы)
    assert подсчёт(окружение["путь"])["proposals"] == 1


# --- длительный прогон --------------------------------------------------------

def test_c07_двадцать_полных_циклов(окружение):
    """Двадцать циклов подряд: каждый даёт ровно одно предложение и один набор."""
    соед, служба = служба_на(окружение["путь"], окружение["реестр"],
                             окружение["артефакты"])
    try:
        for i in range(SOAK_ЦИКЛОВ):
            з = собрать_заявку(реестр=окружение["реестр"],
                               артефакты=окружение["артефакты"],
                               модель=окружение["модель"],
                               зам=замысел(САЙТ, entity_id=f"soak-{i:04d}"),
                               idempotency_key=f"soak-{i}")
            первый = служба.принять(з, requester_service="seo",
                                    actor_id="service:seo", actor_type="SERVICE")
            повтор = служба.принять(з, requester_service="seo",
                                    actor_id="service:seo", actor_type="SERVICE")
            assert первый["proposal_id"] == повтор["proposal_id"]
            assert повтор["idempotent_replay"] is True
    finally:
        соед.close()
    итог = подсчёт(окружение["путь"])
    assert итог["proposals"] == SOAK_ЦИКЛОВ, итог
    assert итог["changesets"] == SOAK_ЦИКЛОВ, итог
    assert итог["events"] == SOAK_ЦИКЛОВ, итог
    assert окружение["модель"].live_calls == 0
    assert окружение["модель"].model_downloads == 0
