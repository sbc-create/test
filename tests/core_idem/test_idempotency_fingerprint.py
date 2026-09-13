"""Воспроизведение дефекта: случайный proposal_id в отпечатке идемпотентности.

Служба кладёт свежесгенерированный `proposal_id` в `requested_change`, а
контур изменений сравнивает повторы именно по этому полю. Значит, два
логически одинаковых запроса с одним ключом дают РАЗНОЕ содержимое — и
второй получает 409 там, где обязан получить повтор.

Проверки написаны до исправления и на нём падают. Это условие: правка,
принятая без падавшей проверки, доказывает только то, что кто-то её написал.
"""
from __future__ import annotations

import concurrent.futures as fut
import sqlite3
import uuid

import pytest

from factory.site_engine.changeset import store as CS
from factory.site_engine.seo_authoring.service import (
    ArtifactStore, SeoProposalService)
from factory.site_engine.seo_authoring.testing import (
    DeterministicQwen, FakeRegistry, собрать_заявку)


@pytest.fixture()
def окружение(tmp_path, monkeypatch):
    monkeypatch.setenv("CHANGESET_DB", str(tmp_path / "cs.sqlite3"))
    monkeypatch.setenv("CHANGESET_APPROVAL_KEY", "idem004-ключ-0123456789")
    monkeypatch.setenv("APPROVAL_CALLER", "control-plane")
    return {"путь": tmp_path / "cs.sqlite3", "реестр": FakeRegistry(),
            "артефакты": ArtifactStore(), "модель": DeterministicQwen()}


def служба_на(о):
    соед = CS.открыть(о["путь"])
    return соед, SeoProposalService(соед, реестр=о["реестр"],
                                    артефакты=о["артефакты"])


def подсчёт(путь) -> dict:
    c = sqlite3.connect(f"file:{путь}?mode=ro", uri=True)
    try:
        return {
            "proposals": c.execute(
                "SELECT count(*) FROM seo_content_proposal").fetchone()[0],
            "changesets": c.execute(
                "SELECT count(*) FROM changeset").fetchone()[0],
            "outbox": c.execute(
                "SELECT count(*) FROM changeset_outbox").fetchone()[0],
        }
    finally:
        c.close()


def test_идентификатор_выводится_из_намерения_а_не_из_случайности(окружение):
    """Прямая проверка инварианта, а не пропуск при отсутствии помощника.

    Идентификатор предложения обязан быть функцией намерения: иначе два
    логически одинаковых запроса несравнимы по построению.
    """
    from factory.site_engine.seo_authoring.service import устойчивый_идентификатор

    a = устойчивый_идентификатор("seo", "ключ-1")
    b = устойчивый_идентификатор("seo", "ключ-1")
    c = устойчивый_идентификатор("seo", "ключ-2")
    d = устойчивый_идентификатор("architect", "ключ-1")
    assert a == b, "один и тот же замысел дал разные идентификаторы"
    assert a != c and a != d, "разные замыслы совпали идентификатором"
    assert a.startswith("scp-") and len(a) == 24


def test_содержимое_заявки_не_несёт_серверных_идентификаторов(окружение):
    """По этому полю контур отличает повтор от новой заявки.

    Любое серверное значение внутри него делает сравнение невозможным, и
    проверять надо именно то, что записано, а не то, что задумано.
    """
    import json as _json

    соед, служба = служба_на(окружение)
    заявка = собрать_заявку(реестр=окружение["реестр"],
                            артефакты=окружение["артефакты"],
                            модель=окружение["модель"], idempotency_key="r0")
    try:
        итог = служба.принять(заявка, requester_service="seo",
                              actor_id="service:seo", actor_type="SERVICE")
        строка = соед.execute(
            "SELECT requested_change FROM changeset WHERE changeset_id=?",
            (итог["changeset_id"],)).fetchone()[0]
    finally:
        соед.close()
    содержимое = _json.loads(строка)
    assert "proposal_id" not in содержимое, \
        "серверный идентификатор попал в основу сравнения повторов"
    assert "changeset_id" not in содержимое
    # И то, что осталось, — намерение клиента целиком.
    assert set(содержимое) == {"entity_id", "entity_kind", "surface", "locale",
                               "artifact_digest", "operations"}, содержимое


def test_последовательный_повтор_возвращает_тот_же_результат(окружение):
    соед, служба = служба_на(окружение)
    заявка = собрать_заявку(реестр=окружение["реестр"],
                            артефакты=окружение["артефакты"],
                            модель=окружение["модель"], idempotency_key="r2")
    try:
        первый = служба.принять(заявка, requester_service="seo",
                                actor_id="service:seo", actor_type="SERVICE")
        второй = служба.принять(заявка, requester_service="seo",
                                actor_id="service:seo", actor_type="SERVICE")
    finally:
        соед.close()
    assert первый["proposal_id"] == второй["proposal_id"]
    assert первый["changeset_id"] == второй["changeset_id"]
    assert второй["idempotent_replay"] is True
    assert подсчёт(окружение["путь"])["proposals"] == 1


def test_шестнадцать_конкурентных_одинаковых_запросов(окружение):
    """Главное проявление дефекта.

    Гонка проходит мимо ранней проверки повтора: оба потока не находят
    записи, оба доходят до вставки, каждый со своим случайным
    идентификатором, — и проигравший получает ложный конфликт.
    """
    соед, _ = служба_на(окружение)
    соед.close()
    заявка = собрать_заявку(реестр=окружение["реестр"],
                            артефакты=окружение["артефакты"],
                            модель=окружение["модель"], idempotency_key="r3")

    def подать(_):
        соед, служба = служба_на(окружение)
        try:
            return служба.принять(заявка, requester_service="seo",
                                  actor_id="service:seo", actor_type="SERVICE")
        except Exception as e:  # noqa: BLE001
            return {"error": getattr(e, "error_code", type(e).__name__)}
        finally:
            соед.close()

    with fut.ThreadPoolExecutor(max_workers=16) as п:
        ответы = list(п.map(подать, range(16)))

    ошибки = [о for о in ответы if "error" in о]
    assert not ошибки, f"ложные отказы при конкуренции: {ошибки[:4]}"
    assert len({о["proposal_id"] for о in ответы}) == 1
    assert len({о["changeset_id"] for о in ответы}) == 1
    assert sum(1 for о in ответы if о["idempotent_replay"] is False) == 1
    итог = подсчёт(окружение["путь"])
    assert итог["proposals"] == 1 and итог["changesets"] == 1
    assert итог["outbox"] == 2, f"событий {итог['outbox']}: ожидались два"


def test_тот_же_ключ_другое_содержимое_даёт_конфликт(окружение):
    """Исправление не должно превратить конфликт в молчаливый повтор."""
    from factory.site_engine.seo_authoring.schema import ProposalRejected
    соед, служба = служба_на(окружение)
    заявка = собрать_заявку(реестр=окружение["реестр"],
                            артефакты=окружение["артефакты"],
                            модель=окружение["модель"], idempotency_key="r4")
    try:
        служба.принять(заявка, requester_service="seo",
                       actor_id="service:seo", actor_type="SERVICE")
        другая = dict(заявка, rationale="иное обоснование")
        with pytest.raises(ProposalRejected) as ош:
            служба.принять(другая, requester_service="seo",
                           actor_id="service:seo", actor_type="SERVICE")
    finally:
        соед.close()
    assert ош.value.error_code == "IDEMPOTENCY_CONFLICT"
    assert ош.value.status == 409


def test_потерянный_ответ_и_повтор(окружение):
    соед, служба = служба_на(окружение)
    заявка = собрать_заявку(реестр=окружение["реестр"],
                            артефакты=окружение["артефакты"],
                            модель=окружение["модель"], idempotency_key="r5")
    try:
        первый = служба.принять(заявка, requester_service="seo",
                                actor_id="service:seo", actor_type="SERVICE")
        повторы = [служба.принять(заявка, requester_service="seo",
                                  actor_id="service:seo", actor_type="SERVICE")
                   for _ in range(4)]
    finally:
        соед.close()
    assert all(п["proposal_id"] == первый["proposal_id"] for п in повторы)
    assert all(п["idempotent_replay"] for п in повторы)
    assert подсчёт(окружение["путь"])["proposals"] == 1


def test_восстановление_после_аварии_не_плодит_записей(окружение, monkeypatch):
    """Падение между созданием набора и вставкой предложения."""
    соед, служба = служба_на(окружение)
    заявка = собрать_заявку(реестр=окружение["реестр"],
                            артефакты=окружение["артефакты"],
                            модель=окружение["модель"], idempotency_key="r6")
    настоящий = CS._в_ящик

    def падать(*a, **k):
        raise RuntimeError("авария между набором и предложением")

    try:
        monkeypatch.setattr(CS, "_в_ящик", падать)
        with pytest.raises(RuntimeError):
            служба.принять(заявка, requester_service="seo",
                           actor_id="service:seo", actor_type="SERVICE")
        monkeypatch.setattr(CS, "_в_ящик", настоящий)
        итог = служба.принять(заявка, requester_service="seo",
                              actor_id="service:seo", actor_type="SERVICE")
    finally:
        соед.close()
    assert итог["idempotent_replay"] is False
    сводка = подсчёт(окружение["путь"])
    assert сводка["proposals"] == 1 and сводка["changesets"] == 1
    assert сводка["outbox"] == 2


def test_общее_хранилище_не_затронуто(окружение):
    """Ни одна проверка не пишет в общее хранилище.

    Сверяется не счётчик, а точное множество идентификаторов: одинаковое
    число получилось бы и после записи с удалением.
    """
    ОБЩЕЕ = "/srv/site-factory/changeset-store/changesets.sqlite3"

    def снимок():
        c = sqlite3.connect(f"file:{ОБЩЕЕ}?mode=ro", uri=True)
        try:
            return {
                "proposals": sorted(r[0] for r in c.execute(
                    "SELECT proposal_id FROM seo_content_proposal")),
                "changesets": sorted(r[0] for r in c.execute(
                    "SELECT changeset_id FROM changeset")),
            }
        finally:
            c.close()

    до = снимок()
    соед, служба = служба_на(окружение)
    try:
        служба.принять(собрать_заявку(реестр=окружение["реестр"],
                                      артефакты=окружение["артефакты"],
                                      модель=окружение["модель"],
                                      idempotency_key="r7"),
                       requester_service="seo", actor_id="service:seo",
                       actor_type="SERVICE")
    finally:
        соед.close()
    assert снимок() == до, "проверка записала в общее хранилище"
    assert str(окружение["путь"]) != ОБЩЕЕ
