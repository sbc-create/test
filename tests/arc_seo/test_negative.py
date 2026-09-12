"""Обязательные отрицательные проверки (28 случаев).

Каждая обязана отказать ДО любого эффекта: ни устойчивой записи, ни набора
изменений, ни изменения поверхности. Это проверяется отдельно в каждом
случае, а не подразумевается.
"""
from __future__ import annotations

import concurrent.futures as fut
import sqlite3

import pytest

from factory.site_engine.changeset import adapter as CA
from factory.site_engine.changeset import model as CM
from factory.site_engine.changeset import store as CS
from factory.site_engine.seo_authoring import schema as SCH
from factory.site_engine.seo_authoring.schema import ProposalRejected
from factory.site_engine.seo_authoring.testing import замысел, собрать_заявку

САЙТ = "arc-seo-test-0001"


def подать(служба, заявка, *, служба_имя="seo", actor_type="SERVICE",
           actor_id=None):
    return служба.принять(заявка, requester_service=служба_имя,
                          actor_id=actor_id or f"service:{служба_имя}",
                          actor_type=actor_type)


@pytest.fixture()
def эффектов_нет(бд, поверхность):
    """Снимок «ничего не произошло», проверяемый после каждого отказа."""
    def проверить():
        assert бд.execute("SELECT count(*) FROM seo_content_proposal"
                          ).fetchone()[0] == 0, "создана запись предложения"
        assert бд.execute("SELECT count(*) FROM changeset").fetchone()[0] == 0, \
            "создан набор изменений"
        assert бд.execute("SELECT count(*) FROM changeset_outbox"
                          ).fetchone()[0] == 0, "записано событие"
        assert поверхность.эффектов() == 0, "изменена поверхность"
    return проверить


def базовая(реестр, артефакты, модель, **kw):
    return собрать_заявку(реестр=реестр, артефакты=артефакты, модель=модель, **kw)


# --- 1–6: схема и версии -----------------------------------------------------

def test_n01_неизвестный_вид_ресурса(служба, реестр, артефакты, модель,
                                     эффектов_нет):
    з = базовая(реестр, артефакты, модель, idempotency_key="n01")
    з["resource_kind"] = "seo.audit"
    with pytest.raises(ProposalRejected) as ош:
        подать(служба, з)
    assert ош.value.error_code == "RESOURCE_KIND_UNKNOWN"
    эффектов_нет()


def test_n02_отсутствует_обязательное_поле(служба, реестр, артефакты, модель,
                                           эффектов_нет):
    з = базовая(реестр, артефакты, модель, idempotency_key="n02")
    del з["source_snapshot_sha256"]
    with pytest.raises(ProposalRejected) as ош:
        подать(служба, з)
    assert ош.value.error_code == "FIELD_REQUIRED"
    эффектов_нет()


def test_n03_лишнее_поле(служба, реестр, артефакты, модель, эффектов_нет):
    з = базовая(реестр, артефакты, модель, idempotency_key="n03")
    з["approved"] = True
    with pytest.raises(ProposalRejected) as ош:
        подать(служба, з)
    assert ош.value.error_code == "FIELD_UNKNOWN"
    эффектов_нет()


def test_n04_неверная_версия_схемы(служба, реестр, артефакты, модель,
                                   эффектов_нет):
    з = базовая(реестр, артефакты, модель, idempotency_key="n04")
    з["schema_version"] = "seo.content.proposal/2.0.0"
    with pytest.raises(ProposalRejected) as ош:
        подать(служба, з)
    assert ош.value.error_code == "SCHEMA_VERSION_UNSUPPORTED"
    эффектов_нет()


def test_n05_неверный_отпечаток_содержимого(служба, реестр, артефакты, модель,
                                            эффектов_нет):
    з = базовая(реестр, артефакты, модель, idempotency_key="n05")
    з["artifact_digest"] = "0" * 64
    with pytest.raises(ProposalRejected) as ош:
        подать(служба, з)
    assert ош.value.error_code == "ARTIFACT_DIGEST_MISMATCH"
    эффектов_нет()


def test_n06_неверный_отпечаток_снимка_фактов(служба, реестр, артефакты, модель,
                                              эффектов_нет):
    з = базовая(реестр, артефакты, модель, idempotency_key="n06")
    з["source_snapshot_sha256"] = "1" * 64
    with pytest.raises(ProposalRejected) as ош:
        подать(служба, з)
    assert ош.value.error_code == "SOURCE_SNAPSHOT_STALE"
    эффектов_нет()


# --- 7–12: витрина, арендатор, окружение, личность ---------------------------

def test_n07_неизвестная_витрина(служба, реестр, артефакты, модель, эффектов_нет):
    з = базовая(реестр, артефакты, модель, idempotency_key="n07")
    з["site_id"] = "arc-seo-unknown-9999"
    with pytest.raises(ProposalRejected) as ош:
        подать(служба, з)
    assert ош.value.error_code == "SITE_ID_UNKNOWN"
    эффектов_нет()


def test_n08_домен_вместо_идентификатора(служба, реестр, артефакты, модель,
                                         эффектов_нет):
    """Чужой арендатор: домен — не ключ, и подставить его нельзя."""
    з = базовая(реестр, артефакты, модель, idempotency_key="n08")
    з["site_id"] = "yummyani.org"
    with pytest.raises(ProposalRejected) as ош:
        подать(служба, з)
    assert ош.value.error_code == "SITE_ID_UNKNOWN"
    эффектов_нет()


def test_n09_подмена_окружения(служба, реестр, артефакты, модель, эффектов_нет):
    з = базовая(реестр, артефакты, модель, idempotency_key="n09")
    з["target_environment"] = "test"          # витрина test, но объявлять нельзя
    з["site_id"] = "arc-seo-np-0003"          # у неё non-production
    with pytest.raises(ProposalRejected) as ош:
        подать(служба, з)
    assert ош.value.error_code == "DERIVED_FIELD_MISMATCH"
    эффектов_нет()


def test_n10_подмена_актора(служба, реестр, артефакты, модель, эффектов_нет):
    з = базовая(реестр, артефакты, модель, idempotency_key="n10")
    з["requested_by"] = "service:architect"
    with pytest.raises(ProposalRejected) as ош:
        подать(служба, з, служба_имя="seo")
    assert ош.value.error_code == "ACTOR_SPOOFED"
    эффектов_нет()


def test_n11_подмена_владельца(служба, реестр, артефакты, модель, эффектов_нет):
    з = базовая(реестр, артефакты, модель, idempotency_key="n11")
    з["owner_service"] = "qwen"
    with pytest.raises(ProposalRejected) as ош:
        подать(служба, з)
    assert ош.value.error_code == "DERIVED_FIELD_MISMATCH"
    эффектов_нет()


def test_n12_подмена_аудитории(служба, реестр, артефакты, модель, эффектов_нет):
    з = базовая(реестр, артефакты, модель, idempotency_key="n12")
    з["audience"] = "public"
    with pytest.raises(ProposalRejected) as ош:
        подать(служба, з)
    assert ош.value.error_code == "DERIVED_FIELD_MISMATCH"
    эффектов_нет()


# --- 13–18: границы Qwen и полномочия ---------------------------------------

def test_n13_qwen_прямая_устойчивая_запись(служба, реестр, артефакты, модель,
                                           эффектов_нет):
    з = базовая(реестр, артефакты, модель, idempotency_key="n13")
    з["requested_by"] = "service:qwen"
    with pytest.raises(ProposalRejected) as ош:
        подать(служба, з, служба_имя="qwen", actor_type="MODEL")
    assert ош.value.error_code == "MODEL_DURABLE_WRITE_DENIED"
    assert ош.value.status == 403
    эффектов_нет()


def test_n14_qwen_самоодобрение(бд):
    from factory.site_engine.changeset import policy as POL
    with pytest.raises(CS.ChangeSetError) as ош:
        POL.проверить_действие_модели("MODEL", "approve")
    assert ош.value.error_code == "MODEL_ACTION_DENIED"


def test_n15_qwen_выдача_полномочий():
    from factory.site_engine.changeset import policy as POL
    with pytest.raises(CS.ChangeSetError) as ош:
        POL.проверить_действие_модели("MODEL", "grant_authority")
    assert ош.value.error_code == "MODEL_ACTION_DENIED"


def test_n16_qwen_применение_и_откат():
    from factory.site_engine.changeset import policy as POL
    for действие in ("apply", "rollback"):
        with pytest.raises(CS.ChangeSetError) as ош:
            POL.проверить_действие_модели("MODEL", действие)
        assert ош.value.error_code == "MODEL_ACTION_DENIED"


def test_n17_отсутствующее_разрешение(служба, реестр, артефакты, модель,
                                      эффектов_нет):
    """Служба, не названная заказчиком SEO-контента, не проходит."""
    з = базовая(реестр, артефакты, модель, idempotency_key="n17")
    з["requested_by"] = "service:templates"
    with pytest.raises(ProposalRejected) as ош:
        подать(служба, з, служба_имя="templates")
    assert ош.value.error_code == "REQUESTER_NOT_ALLOWED"
    эффектов_нет()


def test_n18_отозванное_разрешение(служба, реестр, артефакты, модель,
                                   эффектов_нет):
    з = базовая(реестр, артефакты, модель, idempotency_key="n18")
    прежние = CM.ПРАВА["seo"]
    CM.ПРАВА["seo"] = set()
    try:
        with pytest.raises(ProposalRejected) as ош:
            подать(служба, з)
        assert ош.value.error_code == "ROLE_NOT_GRANTED"
        эффектов_нет()
    finally:
        CM.ПРАВА["seo"] = прежние


# --- 19–21: идемпотентность и устаревание ------------------------------------

def test_n19_тот_же_ключ_другое_содержимое(служба, бд, реестр, артефакты, модель):
    з = базовая(реестр, артефакты, модель, idempotency_key="n19")
    подать(служба, з)
    другая = базовая(реестр, артефакты, модель,
                     зам=замысел(САЙТ, entity_id="anime-0777"),
                     idempotency_key="n19")
    with pytest.raises(ProposalRejected) as ош:
        подать(служба, другая)
    assert ош.value.error_code == "IDEMPOTENCY_CONFLICT"
    assert бд.execute("SELECT count(*) FROM changeset").fetchone()[0] == 1


def test_n20_два_одновременных_одинаковых_запроса(tmp_path, monkeypatch,
                                                  реестр, артефакты, модель):
    monkeypatch.setenv("CHANGESET_APPROVAL_KEY", "n20-ключ-0123456789")
    monkeypatch.setenv("APPROVAL_CALLER", "control-plane")
    путь = tmp_path / "cs.sqlite3"
    заявка = базовая(реестр, артефакты, модель, idempotency_key="n20")

    def подать_раз(_):
        from factory.site_engine.seo_authoring.service import SeoProposalService
        соед = CS.открыть(путь)
        try:
            служба = SeoProposalService(соед, реестр=реестр, артефакты=артефакты)
            return служба.принять(заявка, requester_service="seo",
                                  actor_id="service:seo", actor_type="SERVICE")
        finally:
            соед.close()

    with fut.ThreadPoolExecutor(max_workers=2) as п:
        ответы = list(п.map(подать_раз, range(2)))
    ids = {о["proposal_id"] for о in ответы}
    созданий = sum(1 for о in ответы if о["idempotent_replay"] is False)
    assert len(ids) == 1, f"создано разных предложений: {len(ids)}"
    assert созданий == 1, f"создание произошло {созданий} раз"


def test_n21_устаревший_набор_фактов(служба, реестр, артефакты, модель,
                                     эффектов_нет):
    з = базовая(реестр, артефакты, модель, idempotency_key="n21")
    реестр.сдвинуть_версию()        # факты изменились после составления
    with pytest.raises(ProposalRejected) as ош:
        подать(служба, з)
    assert ош.value.error_code == "SOURCE_SNAPSHOT_STALE"
    эффектов_нет()


# --- 22–25: внедрение, обход, production, адаптер ----------------------------

@pytest.mark.parametrize("поле,значение", [
    ("entity_id", "../../etc/passwd"),
    ("fact_pack_ref", "http://169.254.169.254/latest/meta-data/"),
    ("artifact_ref", "file:///etc/shadow"),
    ("rationale", "x; sudo systemctl stop nginx"),
    ("rationale", "1 UNION SELECT token FROM credentials"),
])
def test_n22_содержимое_пытается_изменить_окружение(служба, реестр, артефакты,
                                                    модель, эффектов_нет,
                                                    поле, значение):
    """Полезная нагрузка — данные, а не программа.

    Ни роль, ни витрина, ни факты, ни окружение из неё не берутся; попытка
    протащить путь, адрес или команду отвергается до эффекта.
    """
    з = базовая(реестр, артефакты, модель, idempotency_key=f"n22-{поле}")
    з[поле] = значение
    with pytest.raises((ProposalRejected, CS.ChangeSetError)) as ош:
        подать(служба, з)
    assert ош.value.error_code in ("FIELD_INVALID", "ARTIFACT_NOT_FOUND",
                                   "PAYLOAD_REJECTED", "DIGEST_INVALID"), \
        f"{поле}={значение!r} принято с кодом {ош.value.error_code}"
    эффектов_нет()


def test_n23_прямая_запись_в_обход_хранилища(служба, бд):
    """Предложение без набора изменений не создать даже изнутри процесса."""
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
            ("обход", "v", "k", "1", "нет-набора", "s", "e", "k", "s", "ru",
             "f", "0" * 64, "a", "0" * 64, "m", "p", "pol", "qwen",
             "service:qwen", "qwen", "qwen", "qwen", "internal", "test",
             "c", "c", "i", "0" * 64, "[]", "t"))


def test_n24_цель_в_production(служба, реестр, артефакты, модель, эффектов_нет):
    з = базовая(реестр, артефакты, модель,
                зам=замысел("arc-seo-prod-0004"), idempotency_key="n24")
    with pytest.raises(ProposalRejected) as ош:
        подать(служба, з)
    assert ош.value.error_code == "PRODUCTION_TARGET_DENIED"
    эффектов_нет()


def test_n25_отсутствующий_адаптер(бд, реестр, поверхность, monkeypatch):
    """Вид ресурса без подключённого адаптера не исполняется."""
    from factory.site_engine.changeset import engine as CE
    monkeypatch.setitem(CA.РЕЕСТР, "seo.content.proposal", поверхность)
    CA.РЕЕСТР.pop("нет.такого.ресурса", None)
    with pytest.raises(CA.AdapterError) as ош:
        CA.получить("нет.такого.ресурса")
    assert ош.value.error_code == "ADAPTER_UNKNOWN"


# --- 26–28: журнал, повтор, потерянный ответ ---------------------------------

def test_n26_повреждённая_цепь_журнала_обнаруживается(tmp_path):
    from factory.site_engine.audit import ledger_store as LS
    путь = tmp_path / "ledger.sqlite3"
    c = LS.открыть(путь)
    for i in range(4):
        LS.append(c, {"event_type": "test.observed.v1", "phase": "OBSERVED",
                      "result": "SUCCESS", "scope": "FLEET",
                      "correlation_id": f"c{i}", "idempotency_key": f"k{i}",
                      "summary": "проверка"},
                  producer_service="architect", actor_id="service:architect",
                  actor_type="SERVICE", authority="OBSERVE")
    assert LS.проверить_цепь(c)["ok"] is True
    c.execute("DROP TRIGGER le_no_update")
    цель = c.execute("SELECT ledger_seq FROM ledger_event ORDER BY ledger_seq "
                     "LIMIT 1 OFFSET 1").fetchone()[0]
    c.execute("UPDATE ledger_event SET summary=summary||'x' WHERE ledger_seq=?",
              (цель,))
    п = LS.проверить_цепь(c)
    c.close()
    assert п["ok"] is False and п["broken_at_seq"] == цель


def test_n27_расхождение_повтора_обнаруживается(служба, бд, реестр, артефакты,
                                                модель):
    """Повтор с тем же ключом, но иным содержимым, не проходит молча."""
    з = базовая(реестр, артефакты, модель, idempotency_key="n27")
    первый = подать(служба, з)
    подменённая = dict(з)
    подменённая["rationale"] = "иное обоснование"
    with pytest.raises(ProposalRejected) as ош:
        подать(служба, подменённая)
    assert ош.value.error_code == "IDEMPOTENCY_CONFLICT"
    # Исходная запись не тронута.
    запись = служба.получить(первый["proposal_id"])
    assert запись["idempotency_key"] == "n27"


def test_n28_потерянный_ответ_после_успешной_записи(служба, бд, реестр,
                                                    артефакты, модель):
    з = базовая(реестр, артефакты, модель, idempotency_key="n28")
    первый = подать(служба, з)
    # Ответ не дошёл до клиента; он повторяет тот же запрос.
    второй = подать(служба, з)
    assert второй["proposal_id"] == первый["proposal_id"]
    assert второй["changeset_id"] == первый["changeset_id"]
    assert второй["idempotent_replay"] is True
    assert бд.execute("SELECT count(*) FROM seo_content_proposal"
                      ).fetchone()[0] == 1
