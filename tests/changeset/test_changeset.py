"""Обязательная матрица проверок контура изменений (пункты 1–24 задания).

Пункт 25 — чистота двух полных серий — проверяется запускающим скриптом:
внутри отдельного теста он не имеет смысла, потому что измеряет состояние
канонических хранилищ ДО и ПОСЛЕ всего прогона.
"""
from __future__ import annotations

import concurrent.futures as fut
import json
import sqlite3
import uuid

import pytest

from factory.site_engine.changeset import adapter as A
from factory.site_engine.changeset import audit_bridge as AB
from factory.site_engine.changeset import engine as E
from factory.site_engine.changeset import model as M
from factory.site_engine.changeset import planner as P
from factory.site_engine.changeset import policy as POL
from factory.site_engine.changeset import store as S
from factory.site_engine.changeset import worker as WK
from factory.site_engine.changeset.testing import (
    РЕСУРС, FakeRegistry, довести_до_одобрения, заявка, создать)


# --- 1. все разрешённые переходы проходят -----------------------------------

def test_01_полный_путь_до_успеха(бд, двигатель, адаптер):
    адаптер.посеять("test-alpha-0001", "res-1", {"title": "старое"})
    cid = создать(бд)
    довести_до_одобрения(бд, двигатель, cid)
    аренда = S.взять_аренду(бд, cid, "worker-1")
    итог = двигатель.применить(cid, actor_id="service:control-plane",
                               служба="control-plane",
                               fencing_token=аренда["fencing_token"])
    assert итог["status"] == M.SUCCEEDED, итог
    набор = S.получить(бд, cid)
    путь = [t["to_status"] for t in набор["transitions"]]
    assert путь == [M.VALIDATING, M.VALIDATED, M.AWAITING_APPROVAL, M.APPROVED,
                    M.APPLYING, M.VERIFYING, M.SUCCEEDED], путь


def test_01b_каждый_переход_таблицы_достижим():
    """У каждого состояния, кроме терминальных, есть выход."""
    без_выхода = [с for с in M.СОСТОЯНИЯ
                  if с not in M.ТЕРМИНАЛЬНЫЕ and с not in M.ДОСТИЖИМЫЕ]
    assert not без_выхода, f"тупиковые нетерминальные состояния: {без_выхода}"
    недостижимые = ({п.в_состояние for п in M.ПЕРЕХОДЫ} | {M.PROPOSED}) ^ set(M.СОСТОЯНИЯ)
    assert not недостижимые, f"недостижимые состояния: {sorted(недостижимые)}"


# --- 2. запрещённые переходы отклоняются ------------------------------------

@pytest.mark.parametrize("действие", ["apply", "approve", "verify_ok",
                                      "rollback_ok", "escalate"])
def test_02_запрещённые_переходы_из_proposed(бд, действие):
    cid = создать(бд)
    with pytest.raises(S.ChangeSetError) as ош:
        S.применить_переход(бд, cid, действие, actor_id="service:architect",
                            служба="architect", роль=M.EXECUTOR)
    assert ош.value.error_code in ("TRANSITION_NOT_ALLOWED", "ROLE_DENIED")


def test_02b_из_терминального_состояния_выхода_нет(бд, двигатель, адаптер):
    адаптер.посеять("test-alpha-0001", "res-1", {"title": "старое"})
    cid = создать(бд)
    довести_до_одобрения(бд, двигатель, cid)
    аренда = S.взять_аренду(бд, cid, "worker-1")
    двигатель.применить(cid, actor_id="service:control-plane",
                        служба="control-plane",
                        fencing_token=аренда["fencing_token"])
    with pytest.raises(S.ChangeSetError) as ош:
        S.применить_переход(бд, cid, "apply", actor_id="service:architect",
                            служба="architect", роль=M.EXECUTOR)
    assert ош.value.error_code == "TRANSITION_NOT_ALLOWED"


# --- 3. прямая запись состояния невозможна ----------------------------------

def test_03_прямой_update_status_запрещён_бд(бд):
    cid = создать(бд)
    with pytest.raises(sqlite3.IntegrityError):
        бд.execute("UPDATE changeset SET status='SUCCEEDED' WHERE changeset_id=?",
                   (cid,))
    assert S.получить(бд, cid)["status"] == M.PROPOSED


def test_03b_роль_без_права_не_меняет_состояние(бд):
    cid = создать(бд)
    with pytest.raises(S.ChangeSetError) as ош:
        S.применить_переход(бд, cid, "validate", actor_id="service:qwen",
                            служба="qwen", роль=M.VALIDATOR)
    assert ош.value.error_code == "ROLE_NOT_GRANTED"


# --- 4. двадцать параллельных одинаковых предложений ------------------------

def test_04_двадцать_параллельных_предложений(tmp_path, monkeypatch):
    monkeypatch.setenv("CHANGESET_DB", str(tmp_path / "cs.sqlite3"))
    з = заявка(idempotency_key="одинаковый-ключ-001")

    def подать(_):
        с = S.открыть(tmp_path / "cs.sqlite3")
        try:
            return S.создать(с, з, producer_service="templates",
                             actor_id="service:templates", actor_type="SERVICE")
        except S.ChangeSetError as e:
            return {"error": e.error_code}
        finally:
            с.close()

    with fut.ThreadPoolExecutor(max_workers=20) as п:
        ответы = list(п.map(подать, range(20)))
    ids = {о["changeset_id"] for о in ответы if "changeset_id" in о}
    созданий = sum(1 for о in ответы if о.get("idempotent_replay") is False)
    assert len(ids) == 1, f"создано разных наборов: {len(ids)}"
    assert созданий == 1, f"создание произошло {созданий} раз"


def test_04b_тот_же_ключ_с_другим_содержимым_конфликт(бд):
    з = заявка(idempotency_key="ключ-конфликта")
    S.создать(бд, з, producer_service="templates",
              actor_id="service:templates", actor_type="SERVICE")
    with pytest.raises(S.ChangeSetError) as ош:
        S.создать(бд, {**з, "requested_change": {"title": "другое"}},
                  producer_service="templates", actor_id="service:templates",
                  actor_type="SERVICE")
    assert ош.value.error_code == "IDEMPOTENCY_CONFLICT"


# --- 5. повтор применения не создаёт второго эффекта ------------------------

def test_05_повтор_применения_один_эффект(бд, двигатель, адаптер):
    адаптер.посеять("test-alpha-0001", "res-1", {"title": "старое"})
    cid = создать(бд)
    довести_до_одобрения(бд, двигатель, cid)
    аренда = S.взять_аренду(бд, cid, "worker-1")
    двигатель.применить(cid, actor_id="service:control-plane",
                        служба="control-plane",
                        fencing_token=аренда["fencing_token"])
    план = S.получить(бд, cid)["dry_run_result"]["per_site_plan"]["test-alpha-0001"]
    эффектов_после_первого = адаптер.эффектов(plan_hash=план["plan_hash"])
    # Повторный вызов адаптера тем же планом — как при восстановлении.
    r = адаптер.apply(site_id="test-alpha-0001", plan=план, fencing_token=999)
    assert r["idempotent_replay"] is True
    assert адаптер.эффектов(plan_hash=план["plan_hash"]) == эффектов_после_первого == 1


# --- 6. конфликтующие наборы не выполняются одновременно --------------------

def test_06_замок_целей_не_даёт_двух_активных(бд, двигатель, адаптер):
    адаптер.посеять("test-alpha-0001", "res-1", {"title": "старое"})
    первый = создать(бд)
    двигатель.валидировать(первый, actor_id="service:control-plane",
                           служба="control-plane")
    второй = создать(бд, requested_change={"title": "иное"})
    with pytest.raises(S.ChangeSetError) as ош:
        двигатель.валидировать(второй, actor_id="service:control-plane",
                               служба="control-plane")
    assert ош.value.error_code == "LOCK_CONFLICT"
    assert ош.value.status == 409


def test_06b_замок_освобождается_терминальным_состоянием(бд, двигатель, адаптер):
    адаптер.посеять("test-alpha-0001", "res-1", {"title": "старое"})
    первый = создать(бд)
    двигатель.валидировать(первый, actor_id="service:control-plane",
                           служба="control-plane")
    S.применить_переход(бд, первый, "cancel_validated",
                        actor_id="service:templates", служба="templates",
                        роль=M.PROPOSER)
    второй = создать(бд, requested_change={"title": "иное"})
    двигатель.валидировать(второй, actor_id="service:control-plane",
                           служба="control-plane")
    assert S.получить(бд, второй)["status"] == M.VALIDATED


# --- 7. потерявший аренду исполнитель огорожен ------------------------------

def test_07_устаревший_маркер_ограждения(бд, двигатель, адаптер):
    адаптер.посеять("test-alpha-0001", "res-1", {"title": "старое"})
    cid = создать(бд)
    довести_до_одобрения(бд, двигатель, cid)
    старая = S.взять_аренду(бд, cid, "worker-1", ttl=0.0)
    новая = S.взять_аренду(бд, cid, "worker-2")
    assert новая["fencing_token"] > старая["fencing_token"]
    with pytest.raises(S.ChangeSetError) as ош:
        двигатель.применить(cid, actor_id="service:control-plane",
                            служба="control-plane",
                            fencing_token=старая["fencing_token"])
    assert ош.value.error_code == "FENCED_OUT"
    assert адаптер.эффектов() == 0, "огороженный исполнитель всё же применил"
    # А действующий маркер работает.
    итог = двигатель.применить(cid, actor_id="service:control-plane",
                               служба="control-plane",
                               fencing_token=новая["fencing_token"])
    assert итог["status"] == M.SUCCEEDED


def test_07b_продление_аренды_чужим_маркером_не_проходит(бд):
    cid = создать(бд)
    a = S.взять_аренду(бд, cid, "worker-1")
    assert S.продлить_аренду(бд, cid, "worker-1", a["fencing_token"]) is True
    assert S.продлить_аренду(бд, cid, "worker-2", a["fencing_token"]) is False


# --- 8, 9. устаревание плана ------------------------------------------------

def test_08_смена_версии_реестра_делает_план_устаревшим(бд, двигатель, адаптер,
                                                        реестр):
    адаптер.посеять("test-alpha-0001", "res-1", {"title": "старое"})
    cid = создать(бд)
    довести_до_одобрения(бд, двигатель, cid)
    реестр.сдвинуть_версию()
    аренда = S.взять_аренду(бд, cid, "worker-1")
    with pytest.raises(S.ChangeSetError) as ош:
        двигатель.применить(cid, actor_id="service:control-plane",
                            служба="control-plane",
                            fencing_token=аренда["fencing_token"])
    assert ош.value.error_code == "PLAN_STALE"
    assert S.получить(бд, cid)["status"] == M.STALE
    assert адаптер.эффектов() == 0


def test_09_смена_отпечатка_цели_делает_план_устаревшим(бд, двигатель, адаптер):
    адаптер.посеять("test-alpha-0001", "res-1", {"title": "старое"})
    cid = создать(бд)
    довести_до_одобрения(бд, двигатель, cid)
    # Кто-то изменил ресурс в обход контура.
    адаптер.посеять("test-alpha-0001", "res-1", {"title": "вмешательство"})
    аренда = S.взять_аренду(бд, cid, "worker-1")
    with pytest.raises(S.ChangeSetError) as ош:
        двигатель.применить(cid, actor_id="service:control-plane",
                            служба="control-plane",
                            fencing_token=аренда["fencing_token"])
    assert ош.value.error_code == "PLAN_STALE"
    assert S.получить(бд, cid)["status"] == M.STALE
    assert адаптер.эффектов() == 0


# --- 10, 11. одобрение ------------------------------------------------------

def test_10_изменение_плана_после_одобрения_аннулирует_его(бд, двигатель,
                                                           адаптер):
    адаптер.посеять("test-alpha-0001", "res-1", {"title": "старое"})
    cid = создать(бд)
    довести_до_одобрения(бд, двигатель, cid)
    набор = S.получить(бд, cid)
    POL.проверить_одобрение(набор, сейчас_utc=S.сейчас())  # пока годно
    # План подменяют — одобрение обязано перестать действовать.
    бд.execute("UPDATE changeset SET plan_hash=? WHERE changeset_id=?",
               ("0" * 64, cid))
    with pytest.raises(S.ChangeSetError) as ош:
        POL.проверить_одобрение(S.получить(бд, cid), сейчас_utc=S.сейчас())
    assert ош.value.error_code == "APPROVAL_BINDING_MISMATCH"


def test_10b_изменение_целей_после_одобрения_аннулирует_его(бд, двигатель,
                                                            адаптер):
    адаптер.посеять("test-alpha-0001", "res-1", {"title": "старое"})
    cid = создать(бд)
    довести_до_одобрения(бд, двигатель, cid)
    бд.execute("UPDATE changeset SET target_site_ids=? WHERE changeset_id=?",
               (S.канон(["test-alpha-0001", "test-beta-0002"]), cid))
    with pytest.raises(S.ChangeSetError) as ош:
        POL.проверить_одобрение(S.получить(бд, cid), сейчас_utc=S.сейчас())
    assert ош.value.error_code == "APPROVAL_BINDING_MISMATCH"


def test_10c_предложивший_не_может_одобрить(бд, двигатель, адаптер):
    адаптер.посеять("test-alpha-0001", "res-1", {"title": "старое"})
    cid = S.создать(бд, заявка(), producer_service="architect",
                    actor_id="service:architect",
                    actor_type="SERVICE")["changeset_id"]
    двигатель.валидировать(cid, actor_id="service:control-plane",
                           служба="control-plane")
    двигатель.запросить_одобрение(cid, actor_id="service:architect",
                                  служба="architect",
                                  expires_at="2099-01-01T00:00:00Z")
    with pytest.raises(S.ChangeSetError) as ош:
        двигатель.одобрить(cid, approver_id="service:architect",
                           служба="architect", actor_type="SERVICE",
                           expires_at="2099-01-01T00:00:00Z")
    assert ош.value.error_code == "SEPARATION_OF_DUTIES"


def test_11_истёкшее_одобрение_блокирует_применение(бд, двигатель, адаптер):
    адаптер.посеять("test-alpha-0001", "res-1", {"title": "старое"})
    cid = создать(бд)
    довести_до_одобрения(бд, двигатель, cid, срок="2000-01-01T00:00:00Z")
    аренда = S.взять_аренду(бд, cid, "worker-1")
    with pytest.raises(S.ChangeSetError) as ош:
        двигатель.применить(cid, actor_id="service:control-plane",
                            служба="control-plane",
                            fencing_token=аренда["fencing_token"])
    assert ош.value.error_code == "APPROVAL_EXPIRED"
    assert адаптер.эффектов() == 0


def test_11b_отозванное_одобрение_блокирует_применение(бд, двигатель, адаптер):
    адаптер.посеять("test-alpha-0001", "res-1", {"title": "старое"})
    cid = создать(бд)
    довести_до_одобрения(бд, двигатель, cid)
    двигатель.отозвать_одобрение(cid, actor_id="human:owner")
    аренда = S.взять_аренду(бд, cid, "worker-1")
    with pytest.raises(S.ChangeSetError) as ош:
        двигатель.применить(cid, actor_id="service:control-plane",
                            служба="control-plane",
                            fencing_token=аренда["fencing_token"])
    assert ош.value.error_code == "APPROVAL_REVOKED"
    assert адаптер.эффектов() == 0


# --- 12. Qwen ---------------------------------------------------------------

@pytest.mark.parametrize("действие", ["approve", "apply", "rollback"])
def test_12_qwen_не_вправе(действие):
    with pytest.raises(S.ChangeSetError) as ош:
        POL.проверить_действие_модели("MODEL", действие)
    assert ош.value.error_code == "MODEL_ACTION_DENIED"
    assert ош.value.status == 403


def test_12b_у_qwen_только_роль_предлагающего():
    assert M.роли_службы("qwen") == frozenset({M.PROPOSER})
    for роль in (M.APPROVER, M.EXECUTOR, M.VALIDATOR, M.OPERATOR):
        assert роль not in M.роли_службы("qwen")


def test_12c_qwen_может_предложить_но_не_одобрить(бд, двигатель, адаптер):
    адаптер.посеять("test-alpha-0001", "res-1", {"title": "старое"})
    cid = S.создать(бд, заявка(), producer_service="qwen",
                    actor_id="service:qwen", actor_type="MODEL")["changeset_id"]
    двигатель.валидировать(cid, actor_id="service:control-plane",
                           служба="control-plane")
    двигатель.запросить_одобрение(cid, actor_id="service:qwen", служба="qwen",
                                  expires_at="2099-01-01T00:00:00Z")
    with pytest.raises(S.ChangeSetError) as ош:
        двигатель.одобрить(cid, approver_id="service:qwen", служба="qwen",
                           actor_type="MODEL",
                           expires_at="2099-01-01T00:00:00Z")
    assert ош.value.error_code == "MODEL_ACTION_DENIED"


# --- 13. сухой прогон -------------------------------------------------------

def test_13_сухой_прогон_без_эффектов(бд, двигатель, адаптер):
    адаптер.посеять("test-alpha-0001", "res-1", {"title": "старое"})
    cid = создать(бд)
    итог = двигатель.валидировать(cid, actor_id="service:control-plane",
                                  служба="control-plane")
    assert итог["dry_run_effects"] == 0
    assert адаптер.эффектов() == 0
    наблюдение = адаптер.observe(site_id="test-alpha-0001", resource_id="res-1")
    assert наблюдение["state"] == {"title": "старое"}, "сухой прогон изменил ресурс"


# --- 14. канарейка ----------------------------------------------------------

def test_14_отказ_канарейки_не_трогает_остальных(бд, двигатель, адаптер):
    for s in ("test-alpha-0001", "test-beta-0002", "test-gamma-0003"):
        адаптер.посеять(s, "res-1", {"title": "старое"})
    cid = создать(бд, target_site_ids=["test-alpha-0001", "test-beta-0002",
                                       "test-gamma-0003"],
                  canary_site_ids=["test-alpha-0001"])
    довести_до_одобрения(бд, двигатель, cid)
    адаптер.сломать("verify")
    аренда = S.взять_аренду(бд, cid, "worker-1")
    итог = двигатель.применить(cid, actor_id="service:control-plane",
                               служба="control-plane",
                               fencing_token=аренда["fencing_token"])
    assert итог["canary_failed"] == "test-alpha-0001"
    assert set(итог["untouched_targets"]) == {"test-beta-0002", "test-gamma-0003"}
    for s in ("test-beta-0002", "test-gamma-0003"):
        н = адаптер.observe(site_id=s, resource_id="res-1")
        assert н["state"] == {"title": "старое"}, f"{s} изменён вопреки отказу канарейки"


# --- 15, 16. проверка и откат ----------------------------------------------

def test_15_проверка_читает_наблюдаемое_состояние(бд, двигатель, адаптер):
    адаптер.посеять("test-alpha-0001", "res-1", {"title": "старое"})
    cid = создать(бд)
    довести_до_одобрения(бд, двигатель, cid)
    набор = S.получить(бд, cid)
    план = набор["dry_run_result"]["per_site_plan"]["test-alpha-0001"]
    # Наблюдаемое не совпадает с ожидаемым — проверка обязана это увидеть,
    # независимо от того, что «сказал» бы исполнитель.
    подделка = {"site_id": "test-alpha-0001", "resource_id": "res-1",
                "state": {"title": "чужое"}, "revision": 7,
                "fingerprint": "0" * 64, "exists": True}
    итог = адаптер.verify(site_id="test-alpha-0001", plan=план,
                          observed=подделка)
    assert итог["ok"] is False
    assert итог["observed_fingerprint"] != итог["expected_fingerprint"]


def test_16_отказ_проверки_приводит_к_успешному_откату(бд, двигатель, адаптер):
    адаптер.посеять("test-alpha-0001", "res-1", {"title": "старое"})
    cid = создать(бд)
    довести_до_одобрения(бд, двигатель, cid)
    адаптер.сломать("verify")
    аренда = S.взять_аренду(бд, cid, "worker-1")
    итог = двигатель.применить(cid, actor_id="service:control-plane",
                               служба="control-plane",
                               fencing_token=аренда["fencing_token"])
    assert итог["status"] == M.ROLLED_BACK, итог
    н = адаптер.observe(site_id="test-alpha-0001", resource_id="res-1")
    assert н["state"] == {"title": "старое"}, "откат не вернул прежнее состояние"
    путь = [t["to_status"] for t in S.получить(бд, cid)["transitions"]]
    assert M.ROLLING_BACK in путь and путь[-1] == M.ROLLED_BACK


# --- 17. неудачный откат ----------------------------------------------------

def test_17_неудачный_откат_требует_вмешательства(бд, двигатель, адаптер):
    адаптер.посеять("test-alpha-0001", "res-1", {"title": "старое"})
    cid = создать(бд)
    довести_до_одобрения(бд, двигатель, cid)
    адаптер.сломать("verify")
    адаптер.сломать("rollback")
    аренда = S.взять_аренду(бд, cid, "worker-1")
    итог = двигатель.применить(cid, actor_id="service:control-plane",
                               служба="control-plane",
                               fencing_token=аренда["fencing_token"])
    assert итог["status"] == M.MANUAL_INTERVENTION_REQUIRED, итог
    набор = S.получить(бд, cid)
    путь = [t["to_status"] for t in набор["transitions"]]
    assert M.ROLLBACK_FAILED in путь
    assert набор["status"] == M.MANUAL_INTERVENTION_REQUIRED
    # Замок удерживается: пока человек не разобрался, второе изменение того же
    # ресурса недопустимо.
    занят = бд.execute("SELECT count(*) c FROM changeset_lock WHERE "
                       "changeset_id=?", (cid,)).fetchone()["c"]
    assert занят == 1, "замок отпущен при требующем вмешательства состоянии"


# --- 18, 19. аварии вокруг внешнего эффекта ---------------------------------

def test_18_падение_до_эффекта_не_создаёт_эффекта(бд, двигатель, адаптер):
    адаптер.посеять("test-alpha-0001", "res-1", {"title": "старое"})
    cid = создать(бд)
    довести_до_одобрения(бд, двигатель, cid)
    адаптер.сломать("apply")
    аренда = S.взять_аренду(бд, cid, "worker-1")
    итог = двигатель.применить(cid, actor_id="service:control-plane",
                               служба="control-plane",
                               fencing_token=аренда["fencing_token"])
    assert итог["status"] == M.APPLY_FAILED
    assert адаптер.эффектов() == 0
    н = адаптер.observe(site_id="test-alpha-0001", resource_id="res-1")
    assert н["state"] == {"title": "старое"}


def test_19_падение_сразу_после_эффекта_не_повторяет_его(бд, двигатель, адаптер,
                                                         monkeypatch):
    адаптер.посеять("test-alpha-0001", "res-1", {"title": "старое"})
    cid = создать(бд)
    довести_до_одобрения(бд, двигатель, cid)
    аренда = S.взять_аренду(бд, cid, "worker-1")

    настоящий = адаптер.observe
    сорвать = {"да": True}

    def падать(*, site_id, resource_id):
        # Первый вызов после применения — «падение» до записи результата.
        если = настоящий(site_id=site_id, resource_id=resource_id)
        if сорвать["да"] and адаптер.эффектов() == 1:
            сорвать["да"] = False
            raise RuntimeError("авария сразу после эффекта")
        return если

    monkeypatch.setattr(адаптер, "observe", падать)
    with pytest.raises(RuntimeError):
        двигатель.применить(cid, actor_id="service:control-plane",
                            служба="control-plane",
                            fencing_token=аренда["fencing_token"])
    monkeypatch.setattr(адаптер, "observe", настоящий)
    assert адаптер.эффектов() == 1
    assert S.получить(бд, cid)["status"] == M.APPLYING, \
        "набор не остался в состоянии, из которого возможно возобновление"
    # Возобновление тем же путём, каким его выполняет рабочий процесс.
    итог = двигатель.применить(cid, actor_id="service:control-plane",
                               служба="control-plane",
                               fencing_token=аренда["fencing_token"])
    assert адаптер.эффектов() == 1, "эффект применён дважды"
    assert итог["status"] == M.SUCCEEDED


# --- 20, 21, 23. журнал аудита и исходящий ящик -----------------------------

def test_20_падение_до_отправки_события_восстанавливается_ящиком(бд, двигатель,
                                                                 адаптер):
    адаптер.посеять("test-alpha-0001", "res-1", {"title": "старое"})
    cid = создать(бд)
    довести_до_одобрения(бд, двигатель, cid)
    # События уже в ящике, но ещё не отправлены: именно так выглядит падение
    # между изменением состояния и доставкой.
    неотправленных = бд.execute(
        "SELECT count(*) c FROM changeset_outbox WHERE published_at IS NULL"
    ).fetchone()["c"]
    assert неотправленных >= 4, неотправленных
    переходов = бд.execute("SELECT count(*) c FROM changeset_transition "
                           "WHERE changeset_id=?", (cid,)).fetchone()["c"]
    типы = {r["event_type"] for r in бд.execute(
        "SELECT event_type FROM changeset_outbox WHERE changeset_id=?", (cid,))}
    # Событий на одно больше числа переходов: первое пишется при создании
    # набора, когда переходить ещё не из чего.
    assert переходов == 4, переходов
    assert типы == {"changeset.proposed.v1", "changeset.validating.v1",
                    "changeset.validated.v1",
                    "changeset.approval_requested.v1",
                    "changeset.approved.v1"}, типы


def test_21_недоступный_журнал_блокирует_применение(бд, адаптер, реестр,
                                                    monkeypatch):
    адаптер.посеять("test-alpha-0001", "res-1", {"title": "старое"})
    двиг = E.Engine(бд, адаптер=адаптер, реестр=реестр, требовать_журнал=True)
    cid = создать(бд)
    довести_до_одобрения(бд, двиг, cid)
    monkeypatch.setattr(AB, "доступен", lambda *a, **k: False)
    аренда = S.взять_аренду(бд, cid, "worker-1")
    with pytest.raises(S.ChangeSetError) as ош:
        двиг.применить(cid, actor_id="service:control-plane",
                       служба="control-plane",
                       fencing_token=аренда["fencing_token"])
    assert ош.value.error_code == "AUDIT_LEDGER_UNAVAILABLE"
    assert ош.value.status == 503
    assert адаптер.эффектов() == 0


def test_23_сверка_ящика_доводит_задолженность_до_нуля(бд, двигатель, адаптер,
                                                       monkeypatch):
    адаптер.посеять("test-alpha-0001", "res-1", {"title": "старое"})
    cid = создать(бд)
    довести_до_одобрения(бд, двигатель, cid)
    отправлено = []

    def приём(запись, **kw):
        отправлено.append(запись["idempotency_key"])
        return {"status": 201, "body": {}}

    monkeypatch.setattr(AB, "отправить", приём)
    итог = AB.опубликовать(бд)
    assert итог["backlog"] == 0, итог
    assert итог["dlq"] == 0
    # Повторный слив ничего не добавляет: ключи уникальны, записи помечены.
    повтор = AB.опубликовать(бд)
    assert повтор["published"] == 0 and повтор["backlog"] == 0
    assert len(отправлено) == len(set(отправлено)), "дубли ключей в отправке"


# --- 22. восстановление после перезапуска -----------------------------------

def test_22_восстановление_без_двойного_применения(бд, адаптер, реестр,
                                                   monkeypatch):
    адаптер.посеять("test-alpha-0001", "res-1", {"title": "старое"})
    двиг = E.Engine(бд, адаптер=адаптер, реестр=реестр, требовать_журнал=False)
    cid = создать(бд)
    довести_до_одобрения(бд, двиг, cid)
    аренда = S.взять_аренду(бд, cid, "worker-1")
    # Набор «застрял» в APPLYING: так выглядит процесс, убитый на середине.
    S.применить_переход(бд, cid, "apply", actor_id="service:control-plane",
                        служба="control-plane", роль=M.EXECUTOR,
                        fencing_token=аренда["fencing_token"])
    assert S.получить(бд, cid)["status"] == M.APPLYING

    # Исполнитель умер: его аренда просрочена и освобождается отдельным
    # шагом прохода. Без этого набор не подхватит никто, и он застрянет
    # навсегда — тихо и незаметно.
    бд.execute("UPDATE changeset_lease SET expires_at=0 WHERE changeset_id=?",
               (cid,))
    освобождено = WK.отпустить_аренды(бд)
    assert освобождено == 1, "просроченная аренда не освобождена"

    monkeypatch.setattr(WK, "WORKER_ID", "worker-recovery")
    новая = S.взять_аренду(бд, cid, "worker-recovery")
    assert новая["fencing_token"] > аренда["fencing_token"]
    двиг.применить(cid, actor_id="service:worker-recovery",
                   служба="control-plane",
                   fencing_token=новая["fencing_token"])
    assert S.получить(бд, cid)["status"] == M.SUCCEEDED
    assert адаптер.эффектов() == 1, "восстановление применило изменение дважды"
    путь = [t["to_status"] for t in S.получить(бд, cid)["transitions"]]
    assert путь.count(M.APPLYING) == 1, f"двойной переход в APPLYING: {путь}"


# --- 24. отклонение опасного содержимого ------------------------------------

@pytest.mark.parametrize("значение,ожидание", [
    ({"path": "../../etc/passwd"}, "PAYLOAD_REJECTED"),
    ({"path": "/etc/shadow"}, "PAYLOAD_REJECTED"),
    ({"cmd": "rm -rf /"}, "PAYLOAD_REJECTED"),
    ({"cmd": "x; sudo reboot"}, "PAYLOAD_REJECTED"),
    ({"q": "1 UNION SELECT password FROM users"}, "PAYLOAD_REJECTED"),
    ({"url": "http://169.254.169.254/latest/meta-data/"}, "PAYLOAD_REJECTED"),
    ({"url": "file:///etc/passwd"}, "PAYLOAD_REJECTED"),
    ({"html": "<script>alert(1)</script>"}, "PAYLOAD_REJECTED"),
])
def test_24_опасное_содержимое_отклонено(значение, ожидание):
    with pytest.raises(S.ChangeSetError) as ош:
        P.проверить_содержимое(значение)
    assert ош.value.error_code == ожидание


def test_24b_неизвестная_операция_отклонена(бд, адаптер, реестр):
    набор = {"resource_type": РЕСУРС, "resource_id": "res-1",
             "operation_type": "нечто", "target_site_ids": ["test-alpha-0001"],
             "requested_change": {}}
    with pytest.raises(S.ChangeSetError) as ош:
        P.спланировать(набор, реестр=реестр, адаптер=адаптер)
    assert ош.value.error_code == "OPERATION_UNKNOWN"


def test_24c_необратимая_операция_блокируется(бд, адаптер, реестр):
    набор = {"resource_type": РЕСУРС, "resource_id": "res-1",
             "operation_type": "delete", "target_site_ids": ["test-alpha-0001"],
             "requested_change": {}}
    with pytest.raises(S.ChangeSetError) as ош:
        P.спланировать(набор, реестр=реестр, адаптер=адаптер)
    assert ош.value.error_code == "IRREVERSIBLE_OPERATION"


def test_24d_неизвестный_site_id_отклонён(бд, адаптер, реестр):
    набор = {"resource_type": РЕСУРС, "resource_id": "res-1",
             "operation_type": "update",
             "target_site_ids": ["yummyani.org"], "requested_change": {}}
    with pytest.raises(S.ChangeSetError) as ош:
        P.спланировать(набор, реестр=реестр, адаптер=адаптер)
    assert ош.value.error_code == "SITE_ID_UNKNOWN"


def test_24e_нерабочее_состояние_жизненного_цикла_отклонено(бд, адаптер, реестр):
    набор = {"resource_type": РЕСУРС, "resource_id": "res-1",
             "operation_type": "update",
             "target_site_ids": ["test-retired-0005"], "requested_change": {}}
    with pytest.raises(S.ChangeSetError) as ош:
        P.спланировать(набор, реестр=реестр, адаптер=адаптер)
    assert ош.value.error_code == "LIFECYCLE_FORBIDDEN"


def test_24f_production_цель_блокируется_выключенной_автономией(бд, двигатель,
                                                                адаптер):
    адаптер.посеять("test-prod-0004", "res-1", {"title": "старое"})
    cid = создать(бд, target_site_ids=["test-prod-0004"])
    with pytest.raises(S.ChangeSetError) as ош:
        двигатель.валидировать(cid, actor_id="service:control-plane",
                               служба="control-plane")
    assert ош.value.error_code == "AUTONOMOUS_PRODUCTION_APPLY_DISABLED"
    assert S.получить(бд, cid)["status"] == M.VALIDATION_FAILED
    assert адаптер.эффектов() == 0


# --- копия и восстановление хранилища ---------------------------------------

def test_копия_и_восстановление_заполненного_хранилища(бд, двигатель, адаптер,
                                                        tmp_path, monkeypatch):
    """Копия проверяется на хранилище С СОДЕРЖИМЫМ.

    Развернуть пустую базу и объявить восстановление работающим — значит
    проверить обёртку, а не то, ради чего копия делается.
    """
    from factory.site_engine.changeset import backup as B

    адаптер.посеять("test-alpha-0001", "res-1", {"title": "старое"})
    адаптер.посеять("test-beta-0002", "res-1", {"title": "старое"})
    успешный = создать(бд)
    довести_до_одобрения(бд, двигатель, успешный)
    аренда = S.взять_аренду(бд, успешный, "worker-1")
    двигатель.применить(успешный, actor_id="service:control-plane",
                        служба="control-plane",
                        fencing_token=аренда["fencing_token"])
    отклонённый = создать(бд, target_site_ids=["test-beta-0002"])
    двигатель.валидировать(отклонённый, actor_id="service:control-plane",
                           служба="control-plane")
    двигатель.запросить_одобрение(отклонённый, actor_id="service:templates",
                                  служба="templates",
                                  expires_at="2099-01-01T00:00:00Z")
    S.применить_переход(бд, отклонённый, "reject", actor_id="human:owner",
                        служба="human_owner", роль=M.APPROVER,
                        reason="не сейчас")

    monkeypatch.setattr(B, "КАТАЛОГ", tmp_path / "backups")
    м = B.создать()
    слепок = м["source_snapshot"]
    assert слепок["changesets"] == 2, слепок
    assert слепок["transitions"] >= 10, слепок
    assert слепок["by_status"] == {M.SUCCEEDED: 1, M.REJECTED: 1}, слепок

    r = B.восстановить(Path(B.КАТАЛОГ) / м["backup_file"])
    assert r["restore_verdict"] == "PASS", r["mismatches"]
    assert r["restored_snapshot"]["transition_digest"] == \
        слепок["transition_digest"], "история решений восстановлена не целиком"
    assert "cs_no_direct_status" in r["guards"], \
        "запрет прямой записи состояния не пережил восстановление"
