"""Публичная поверхность чтения состояния индексации.

Зачем она понадобилась. Состояние было реализовано, контракт объявлен, но
точки входа у него не было: `прочитать()` принимал соединение с базой. Значит
потребитель обязан был либо открыть хранилище Core напрямую, либо втянуть его
внутренние модули к себе в процесс.

Оба пути плохи по одной причине. Потребитель, знающий схему хранения, привязан
к ней навсегда — и Core перестаёт быть волен её менять. Потребитель, собирающий
состояние из ленты событий, повторяет логику Core, то есть становится вторым
вычислителем того же состояния. Второй вычислитель — это второй ответ на вопрос
«открыт ли сайт», и расходиться они начнут в первый же день.

Здесь проверяется то, что отличает поверхность чтения от дырки в стене: она
отдаёт состояние и ревизию **вместе**, отказывается менять что-либо, различает
«не знаем такого сайта» и «решили не индексировать», и называет отказ отказом.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid

import pytest

from factory.site_engine.audit import indexing as idx
from factory.site_engine.audit import indexing_contract as contract
from factory.site_engine.audit import ledger_api as api
from factory.site_engine.audit import ledger_store as store

ДЕВЯТЬ = {
    "lords-01", "lords-02", "lords-03",
    "yummyani-site", "yummyani-org", "yummyani-biz",
    "zona-01", "animedia-01", "animedia-02",
}
ОТКРЫТЫЙ = "yummyani-site"

#: Заголовок опознания читателя. Значение — локальный токен стенда, не секрет:
#: сервер сверяет его отпечаток из каталога учётных данных, который создаётся
#: тут же во временном каталоге.
ЧИТАТЕЛЬ = {"authorization": "Bearer reg-local-token"}


@pytest.fixture
def стенд(tmp_path, monkeypatch):
    """Свой журнал и свой реестр. Канонических не касаемся."""
    журнал = tmp_path / "ledger.sqlite3"
    реестр = tmp_path / "registry.sqlite3"

    с = sqlite3.connect(реестр)
    с.execute("CREATE TABLE site(site_id TEXT PRIMARY KEY, domain TEXT)")
    с.executemany("INSERT INTO site(site_id, domain) VALUES(?,?)",
                  [(s, f"{s}.example") for s in sorted(ДЕВЯТЬ)])
    с.commit()
    с.close()

    # Личности выдаются отпечатками токенов через каталог учётных данных, а не
    # переменными окружения: передача служебных токенов окружением запрещена
    # самим слоем опознания. Готовим их тем же способом, что и штатный стенд
    # tests/audit/run_tests.py.
    креды = tmp_path / "credentials"
    креды.mkdir()
    токены = {"registry": "reg-local-token", "architect": "arch-local-token"}
    (креды / "audit-token-fingerprints").write_text(
        json.dumps({"services": {имя: hashlib.sha256(зн.encode()).hexdigest()
                                 for имя, зн in токены.items()},
                    "revoked": []}),
        encoding="utf-8")

    monkeypatch.setenv("AUDIT_LEDGER_DB", str(журнал))
    monkeypatch.setenv("REGISTRY_DB", str(реестр))
    monkeypatch.setenv("CREDENTIALS_DIRECTORY", str(креды))

    соед = store.открыть(журнал)
    idx.подготовить(соед)
    соед.close()
    return {"журнал": журнал, "реестр": реестр}


def открыть_сайт(стенд, site_id: str = ОТКРЫТЫЙ) -> dict:
    """Owner-команда через журнал: разрешение владельца и исполнение."""
    соед = store.открыть(стенд["журнал"])
    idx.подготовить(соед)
    ап = store.append(
        соед,
        {"event_type": idx.ТИП_ОТКРЫТЬ, "phase": "AUTHORIZED", "result": "SUCCESS",
         "scope": "SITE", "site_id": site_id, "idempotency_key": str(uuid.uuid4()),
         "correlation_id": "c", "occurred_at": "2026-09-16T00:00:00.000000Z"},
        producer_service="human_owner", actor_id="owner", actor_type="HUMAN",
        authority="AUTHORIZE", известные_сайты=ДЕВЯТЬ)["event_id"]
    итог = idx.открыть_индексацию(
        соед, site_id=site_id, expected_revision=0, approval_id=ап,
        reason="решение владельца", idempotency_key=str(uuid.uuid4()),
        correlation_id="c", producer_service="architect", actor_id="i",
        actor_type="SERVICE", authority="EXECUTE", известные_сайты=ДЕВЯТЬ,
        occurred_at="2026-09-16T00:00:00.000000Z")
    соед.close()
    return итог


def GET(путь: str, заголовки: dict | None = None):
    return api.обработать("GET", путь, headers=заголовки if заголовки is not None
                          else ЧИТАТЕЛЬ)


# --- поверхность существует и отдаёт атомарный ответ ---------------------------

def test_снимок_отдаётся_одним_ответом(стенд) -> None:
    открыть_сайт(стенд)
    код, тело = GET("/api/v1/indexing/state")
    assert код == 200, тело
    assert тело["contract_version"] == contract.ВЕРСИЯ_КОНТРАКТА
    assert тело["schema_version"] == idx.СХЕМА_СОСТОЯНИЯ
    assert тело["provider_health"] == contract.ЗДОРОВ
    assert тело["snapshot_digest"], "снимок без отпечатка нечем подтвердить"
    сайт = next(с for с in тело["sites"] if с["site_id"] == ОТКРЫТЫЙ)
    assert сайт["desired_state"] == idx.OPEN
    assert сайт["revision"] == 1


def test_состояние_и_ревизия_приходят_вместе(стенд) -> None:
    """Два запроса — два разных момента; склеенный из них ответ не
    соответствует ни одному."""
    открыть_сайт(стенд)
    _, тело = GET("/api/v1/indexing/state")
    for с in тело["sites"]:
        assert "desired_state" in с and "revision" in с
        assert "snapshot_digest" in с


def test_поля_контракта_на_месте(стенд) -> None:
    открыть_сайт(стенд)
    _, тело = GET("/api/v1/indexing/state")
    сайт = тело["sites"][0]
    обязательные = {"site_id", "domain", "desired_state", "revision",
                    "last_known_good_revision", "updated_at", "source_event_id",
                    "approval_ref", "reason", "snapshot_digest",
                    "schema_version", "registered"}
    нет = обязательные - set(сайт)
    assert not нет, f"контракт не отдаёт поля: {sorted(нет)}"


def test_домен_производный_из_реестра(стенд) -> None:
    открыть_сайт(стенд)
    _, тело = GET("/api/v1/indexing/state")
    сайт = next(с for с in тело["sites"] if с["site_id"] == ОТКРЫТЫЙ)
    assert сайт["domain"] == f"{ОТКРЫТЫЙ}.example"


def test_ответ_сериализуется_детерминированно(стенд) -> None:
    открыть_сайт(стенд)
    первый = GET("/api/v1/indexing/state")[1]
    второй = GET("/api/v1/indexing/state")[1]
    # taken_at отличается по определению; решения обязаны совпасть побайтово
    assert json.dumps(первый["sites"], sort_keys=True, ensure_ascii=False) == \
        json.dumps(второй["sites"], sort_keys=True, ensure_ascii=False)
    assert первый["snapshot_digest"] == второй["snapshot_digest"]


# --- один сайт -----------------------------------------------------------------

def test_состояние_одного_сайта(стенд) -> None:
    открыть_сайт(стенд)
    код, тело = GET(f"/api/v1/indexing/state/{ОТКРЫТЫЙ}")
    assert код == 200
    assert тело["site"]["desired_state"] == idx.OPEN
    assert тело["site"]["revision"] == 1


def test_зарегистрированный_но_закрытый(стенд) -> None:
    код, тело = GET(f"/api/v1/indexing/state/{'lords-01'}")
    assert код == 200
    assert тело["site"]["desired_state"] == idx.CLOSED
    assert тело["site"]["registered"] is False
    assert тело["site"]["reason"] == idx.БЕЗ_РЕШЕНИЯ


def test_неизвестный_сайт_это_ошибка_а_не_closed(стенд) -> None:
    """«Не знаем такого» и «решили не индексировать» — разные ответы."""
    код, тело = GET("/api/v1/indexing/state/нет-такого")
    assert код == 404
    assert тело["error_code"] == "SITE_ID_UNKNOWN"


# --- только чтение -------------------------------------------------------------

@pytest.mark.parametrize("метод", ["POST", "PUT", "PATCH", "DELETE"])
def test_изменение_через_эту_поверхность_невозможно(стенд, метод: str) -> None:
    код, тело = api.обработать(метод, "/api/v1/indexing/state",
                               headers=ЧИТАТЕЛЬ, body={"desired_state": "OPEN"})
    assert код == 405
    assert тело["error_code"] == "READ_ONLY"


def test_чтение_требует_опознания(стенд) -> None:
    код, _ = GET("/api/v1/indexing/state", {})
    assert код in (401, 403), "неопознанный читатель не должен получать состояние"


def test_чужой_маршрут_под_префиксом_не_отвечает(стенд) -> None:
    код, _ = GET("/api/v1/indexing/whatever")
    assert код == 404


# --- отказ называется отказом --------------------------------------------------

def test_недоступное_хранилище_не_выдаётся_за_пустую_матрицу(стенд, monkeypatch) -> None:
    """Пустой снимок означал бы «все закрыты» и закрыл бы живую витрину."""
    открыть_сайт(стенд)

    def падает(*_a, **_k):
        raise sqlite3.OperationalError("хранилище недоступно")

    monkeypatch.setattr(contract, "прочитать", падает)
    код, тело = GET("/api/v1/indexing/state")
    assert код == 503
    assert тело["error_code"] == "PROVIDER_UNAVAILABLE"
    assert "sites" not in тело


# --- изменение по-прежнему только owner-командой -------------------------------

def test_поверхность_чтения_не_меняет_состояние(стенд) -> None:
    открыть_сайт(стенд)
    до = GET("/api/v1/indexing/state")[1]["snapshot_digest"]
    for _ in range(5):
        GET("/api/v1/indexing/state")
        GET(f"/api/v1/indexing/state/{ОТКРЫТЫЙ}")
    после = GET("/api/v1/indexing/state")[1]["snapshot_digest"]
    assert до == после


def test_у_модуля_чтения_нет_команд_изменения() -> None:
    запретные = [имя for имя in dir(contract)
                 if any(k in имя.lower() for k in
                        ("open_index", "close_index", "set_", "mutate", "apply_"))]
    assert not запретные, f"в поверхности чтения появился писатель: {запретные}"
