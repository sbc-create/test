"""Масштаб: добавление витрины и сотня одновременных действий.

Две разные проверки. Первая — о том, что рост парка не требует правки кода:
статический список витрин где-нибудь в исходниках означает, что N+1 — это
работа программиста, а не запись в реестре. Вторая — о том, что сотня
одновременных действий укладывается в объявленный бюджет и не оставляет
частичных записей.
"""
from __future__ import annotations

import concurrent.futures as fut
import re
import time
import uuid
from pathlib import Path

import pytest

from factory.site_engine.changeset import model as M
from factory.site_engine.changeset import store as S
from factory.site_engine.changeset import engine as E
from factory.site_engine.changeset.testing import FakeRegistry, заявка

КОРЕНЬ = Path(__file__).resolve().parents[2]
ПАКЕТ = КОРЕНЬ / "factory/site_engine/changeset"

#: Бюджет на сотню одновременных подач. Взят с запасом к измеренному: проверка
#: должна ловить изменение ПОРЯДКА величины, а не дрожание нагруженного хоста.
БЮДЖЕТ_СЕК = 90.0
СКОЛЬКО = 100


def _с_витринами(реестр, доп: dict) -> FakeRegistry:
    """Тот же реестр плюс витрины.

    Версия берётся у переданного: подписант читает НАСТОЯЩИЙ реестр, и план,
    построенный по выдуманной версии, он отвергнет — отказом про версию, а не
    про то, что проверяется.
    """
    сайты = {с["site_id"]: с for с in реестр.сайты()}
    сайты.update(доп)
    return FakeRegistry(версия=реестр.версия(), сайты=сайты)


# --- N+1 ---------------------------------------------------------------------

def test_добавление_витрины_не_требует_правки_кода(бд, адаптер, реестр):
    """Витрина, которой контур никогда не видел, принимается как обычная."""
    новая = "test-newcomer-9999"
    расширенный = _с_витринами(реестр, {новая: {
        "site_id": новая, "environment": "test",
        "lifecycle_state": "ACTIVE"}})
    двигатель = E.Engine(бд, адаптер=адаптер, реестр=расширенный,
                         требовать_журнал=False)
    адаптер.посеять(новая, "res-1", {"title": "старое"})
    cid = S.создать(бд, заявка(target_site_ids=[новая]),
                    producer_service="templates",
                    actor_id="service:templates",
                    actor_type="SERVICE")["changeset_id"]
    итог = двигатель.валидировать(cid, actor_id="service:control-plane",
                                  служба="control-plane")
    assert итог["changeset_id"] == cid
    assert S.получить(бд, cid)["status"] == M.VALIDATED


def test_в_коде_контура_нет_списка_витрин():
    """Ни одного жёстко вписанного идентификатора рабочей витрины.

    Проверяется не «нет строки с доменом», а отсутствие самого способа
    перечислить парк в исходниках: именно он превращает N+1 в правку кода.
    """
    # Отрицательный просмотр вперёд обязателен: без него "contracts.site-"
    # из адреса схемы считается доменом витрины.
    домен = re.compile(r"\b[a-z0-9-]+\.(space|biz|online|icu|site|org)(?![\w-])")
    рабочие = re.compile(r"\b(lords|zona|animedia|yummyani)-\d+\b")
    нарушения = []
    for ф in sorted(ПАКЕТ.glob("*.py")):
        if ф.name == "testing.py":
            continue  # оснастка испытаний: её витрины заведомо не рабочие
        текст = ф.read_text("utf-8")
        for строка_n, строка in enumerate(текст.splitlines(), 1):
            if домен.search(строка) or рабочие.search(строка):
                нарушения.append(f"{ф.name}:{строка_n}: {строка.strip()[:80]}")
    assert not нарушения, нарушения


def test_оснастка_испытаний_не_пересекается_с_рабочим_парком():
    """Испытательные витрины обязаны не совпасть ни с одной настоящей.

    Совпадение однажды привело бы к тому, что проверка изменила бы что-то у
    живой витрины, и узнали бы об этом по последствиям.
    """
    from factory.site_engine.changeset.testing import САЙТЫ
    чужие = [s for s in САЙТЫ if not s.startswith("test-")]
    assert not чужие, чужие


# --- N+100 -------------------------------------------------------------------

def test_сто_одновременных_подач_в_бюджете(tmp_path, monkeypatch):
    """Сотня подач сразу: все различимы, ни одной частичной записи."""
    monkeypatch.setenv("CHANGESET_DB", str(tmp_path / "нагрузка.sqlite3"))
    путь = tmp_path / "нагрузка.sqlite3"
    S.открыть(путь).close()

    def подать(n: int):
        с = S.открыть(путь)
        try:
            return S.создать(
                с, заявка(idempotency_key=f"нагрузка-{n}-{uuid.uuid4().hex[:8]}"),
                producer_service="templates", actor_id="service:templates",
                actor_type="SERVICE")
        finally:
            с.close()

    начало = time.monotonic()
    with fut.ThreadPoolExecutor(max_workers=20) as п:
        ответы = list(п.map(подать, range(СКОЛЬКО)))
    ушло = time.monotonic() - начало

    assert len(ответы) == СКОЛЬКО
    ид = {о["changeset_id"] for о in ответы}
    assert len(ид) == СКОЛЬКО, f"наборов меньше подач: {len(ид)}"
    assert not any(о["idempotent_replay"] for о in ответы)

    с = S.открыть(путь)
    try:
        всего = с.execute("SELECT count(*) c FROM changeset").fetchone()["c"]
        без_целей = с.execute(
            "SELECT count(*) c FROM changeset WHERE changeset_id NOT IN "
            "(SELECT changeset_id FROM changeset_target)").fetchone()["c"]
        без_событий = с.execute(
            "SELECT count(*) c FROM changeset WHERE changeset_id NOT IN "
            "(SELECT changeset_id FROM changeset_outbox)").fetchone()["c"]
    finally:
        с.close()
    assert всего == СКОЛЬКО, всего
    # Частичная запись — набор без целей или без события о нём.
    assert без_целей == 0, без_целей
    assert без_событий == 0, без_событий
    assert ушло < БЮДЖЕТ_СЕК, f"{СКОЛЬКО} подач заняли {ушло:.1f}с"


def test_повтор_ключа_под_нагрузкой_даёт_один_набор(tmp_path, monkeypatch):
    """Двадцать одновременных подач с ОДНИМ ключом — один набор на всех."""
    monkeypatch.setenv("CHANGESET_DB", str(tmp_path / "ключ.sqlite3"))
    путь = tmp_path / "ключ.sqlite3"
    S.открыть(путь).close()
    з = заявка(idempotency_key="один-ключ-на-всех")

    def подать(_):
        с = S.открыть(путь)
        try:
            return S.создать(с, з, producer_service="templates",
                             actor_id="service:templates", actor_type="SERVICE")
        finally:
            с.close()

    with fut.ThreadPoolExecutor(max_workers=20) as п:
        ответы = list(п.map(подать, range(20)))
    ид = {о["changeset_id"] for о in ответы}
    assert len(ид) == 1, ид
    assert sum(1 for о in ответы if not о["idempotent_replay"]) == 1, ответы


@pytest.mark.parametrize("сколько", [1, 9, 100])
def test_план_не_зависит_от_числа_витрин_в_реестре(бд, адаптер, реестр,
                                                   сколько):
    """Рост реестра не меняет того, что делает планировщик с одной целью."""
    доп = {f"test-bulk-{i:04d}": {"site_id": f"test-bulk-{i:04d}",
                                  "environment": "test",
                                  "lifecycle_state": "ACTIVE"}
           for i in range(сколько)}
    двигатель = E.Engine(бд, адаптер=адаптер, реестр=_с_витринами(реестр, доп),
                         требовать_журнал=False)
    адаптер.посеять("test-bulk-0000", "res-1", {"title": "старое"})
    cid = S.создать(бд, заявка(target_site_ids=["test-bulk-0000"]),
                    producer_service="templates",
                    actor_id="service:templates",
                    actor_type="SERVICE")["changeset_id"]
    итог = двигатель.валидировать(cid, actor_id="service:control-plane",
                                  служба="control-plane")
    assert итог["dry_run_effects"] == 0
    assert len(S.получить(бд, cid)["targets"]) == 1
