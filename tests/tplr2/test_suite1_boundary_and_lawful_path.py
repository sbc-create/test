"""SUITE_1 — граница учётных данных Templates и законный путь исполнения.

Проверяются следствия: что юнит фактически видит, какие полномочия объявлены
матрицами, доходит ли набор изменений до терминального состояния каноническими
переходами и отвергает ли адаптер исполнение при любом несовпадении притязаний.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from factory.site_engine.changeset import model as M
from factory.site_engine.changeset import store as S
from factory.site_engine.provisioner import grant as G
from factory.site_engine.provisioner.templates_executor import TemplatesExecutor

from ._путь import (выпустить_grant, довести_до_approved, запросить_grant,
                    набор_ключей, ожидания, отпечаток_реестра, собрать_цель)

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
EVIDENCE = КОРЕНЬ / "artifacts/tpl-r2/credential-boundary.json"


# =============================================================================
# 1. Граница учётных данных
# =============================================================================

@pytest.fixture(scope="module")
def граница() -> dict:
    """Снимок живого юнита. Отсутствие снимка — провал, а не пропуск."""
    assert EVIDENCE.is_file(), (
        f"нет снимка границы {EVIDENCE}: утверждать о ней нечем")
    return json.loads(EVIDENCE.read_text("utf-8"))


class TestГраницаУчётныхДанных:
    def test_служба_под_собственной_учётной_записью(self, граница):
        assert граница["user"] == "templates-cp"
        assert граница["active_state"] == "active"

    def test_общий_env_не_читается(self, граница):
        assert граница["shared_env_readers"] == 0
        assert "control-api.env" not in граница["environment_files"]

    def test_чужих_credential_нет(self, граница):
        assert граница["foreign_credential_refs"] == []

    def test_секретов_в_окружении_нет(self, граница):
        assert граница["secrets_in_env"] == []

    def test_секретов_в_аргументах_нет(self, граница):
        """Аргументы процесса видны всем, кто может читать /proc."""
        for опасное in ("token", "key=", "secret", "Bearer"):
            assert опасное not in граница["process_args"].lower()

    def test_секретов_у_потомков_нет(self, граница):
        for строка in граница["child_process_args"]:
            for опасное in ("token", "secret", "Bearer"):
                assert опасное not in строка.lower()

    @pytest.mark.parametrize("запрет", [
        "approval_private_key", "credentials_dir", "sudo",
        "site_unit_restart", "operator_home", "docker"])
    def test_запреты_действуют(self, граница, запрет):
        assert граница["denials"][запрет] is True

    def test_у_templates_нет_роли_approver_и_executor(self, граница):
        роли = set(граница["changeset_roles_templates"])
        assert роли == {"proposer"}, (
            "постоянная личность Templates предлагает и не более того")
        assert M.APPROVER not in роли and M.EXECUTOR not in роли

    def test_модель_не_одобряет_и_не_применяет(self, граница):
        assert {"approve", "apply", "rollback"} <= set(
            граница["model_forbidden_actions"])

    def test_templates_не_подписывает(self):
        """Приватный ключ подписи принадлежит одной службе, и это не Templates."""
        from factory.site_engine.approval import service as SIGNER
        assert "templates" not in SIGNER.ДОПУЩЕНЫ_К_ОДОБРЕНИЮ
        assert "templates" not in SIGNER.ДОПУЩЕНЫ_К_РАЗРЕШЕНИЮ


# =============================================================================
# 2. Законный путь до терминального состояния
# =============================================================================

class TestЗаконныйПуть:
    def test_разделение_обязанностей(self, стенд):
        цель = собрать_цель(стенд)
        cid, _ = довести_до_approved(стенд, цель)
        набор = S.получить(стенд["соед"], cid)
        assert набор["producer_service"] == "templates"
        assert набор["actor_id"] == "service:templates"
        одобрение = набор["approval"]
        assert одобрение["approver_id"] != набор["actor_id"], (
            "предложивший не может быть одобрившим")
        assert одобрение["approver_service"] == "human_owner"
        assert одобрение["approver_type"] == "HUMAN"

    def test_переходы_только_канонические(self, стенд):
        """Достигнутое состояние и путь к нему объявлены таблицей переходов."""
        цель = собрать_цель(стенд)
        cid, _ = довести_до_approved(стенд, цель)
        набор = S.получить(стенд["соед"], cid)
        assert набор["status"] == M.APPROVED
        объявленные = ({п.из_состояния for п in M.ПЕРЕХОДЫ}
                       | {п.в_состояние for п in M.ПЕРЕХОДЫ})
        assert набор["status"] in объявленные
        assert set(M.СОСТОЯНИЯ) >= объявленные, (
            "таблица переходов ссылается на необъявленное состояние")
        # Несуществующего действия машина не выполняет.
        with pytest.raises(S.ChangeSetError) as ош:
            S.применить_переход(стенд["соед"], cid, "выдуманное-действие",
                                actor_id="service:control-plane",
                                служба="control-plane", роль=M.EXECUTOR)
        assert ош.value.error_code in ("TRANSITION_NOT_ALLOWED",
                                       "TRANSITION_UNKNOWN")

    def test_статус_напрямую_не_записывается(self, стенд):
        """Хранилище не даёт менять состояние мимо машины переходов."""
        цель = собрать_цель(стенд)
        cid, _ = довести_до_approved(стенд, цель)
        import sqlite3
        with pytest.raises(sqlite3.IntegrityError):
            стенд["соед"].execute(
                "UPDATE changeset SET status='SUCCEEDED' WHERE changeset_id=?",
                (cid,))

    def test_исполнение_доходит_до_терминального_состояния(self, стенд):
        цель = собрать_цель(стенд)
        cid, движок = довести_до_approved(стенд, цель)
        аренда = S.взять_аренду(стенд["соед"], cid, "changeset-worker")
        итог = движок.применить(cid, actor_id="service:control-plane",
                                служба="control-plane",
                                fencing_token=аренда["fencing_token"])
        assert итог["status"] == M.SUCCEEDED
        assert M.SUCCEEDED in M.ТЕРМИНАЛЬНЫЕ
        assert цель["мир"].эффектов("create") == 1


# =============================================================================
# 3. Граница разрешения на адаптере: семь отрицательных случаев
# =============================================================================

def _подготовить(стенд):
    цель = собрать_цель(стенд)
    cid, движок = довести_до_approved(стенд, цель)
    аренда = S.взять_аренду(стенд["соед"], cid, "changeset-worker")
    набор = S.получить(стенд["соед"], cid)
    план = набор["dry_run_result"]["per_site_plan"][стенд["site_id"]]
    основа = {
        "changeset_id": cid, "site_id": стенд["site_id"],
        "plan_hash": набор["plan_hash"],
        "artifact_digest": план["expected_fingerprint"],
        "registry_fingerprint": отпечаток_реестра(стенд),
        "fencing_token": аренда["fencing_token"]}
    исполнитель = TemplatesExecutor(
        стенд["tmp"] / "exec.sqlite3", цель["адаптер"], набор_ключей(стенд),
        наблюдатель=lambda s: цель["витрина"].мир.объекты.get(
            f"template:counter_tag:{s}") and f"template:counter_tag:{s}")
    return цель, план, основа, исполнитель


class TestГраницаРазрешения:
    def test_00_законное_разрешение_исполняется(self, стенд):
        """Отрицательные случаи бессмысленны, если не работает законный."""
        цель, план, основа, исп = _подготовить(стенд)
        подпись, полезное = выпустить_grant(стенд, **основа)
        исход = исп.выполнить(подпись=подпись, полезное=полезное,
                              ожидания=ожидания(**основа), план=план,
                              idempotency_key="lawful-1")
        assert исход.applied and исход.effects == 1
        assert цель["мир"].эффектов("create") == 1

    def test_01_разрешение_отсутствует(self, стенд):
        цель, план, основа, исп = _подготовить(стенд)
        with pytest.raises(G.GrantError) as ош:
            исп.выполнить(подпись="", полезное={}, ожидания=ожидания(**основа),
                          план=план, idempotency_key="neg-1")
        assert ош.value.error_code == "GRANT_MISSING"
        assert цель["мир"].эффектов("create") == 0

    def test_02_чужая_аудитория(self, стенд):
        цель, план, основа, исп = _подготовить(стенд)
        подпись, полезное = выпустить_grant(стенд, **основа,
                                            audience="changeset-worker")
        with pytest.raises(G.GrantError) as ош:
            исп.выполнить(подпись=подпись, полезное=полезное,
                          ожидания=ожидания(**основа), план=план,
                          idempotency_key="neg-2")
        assert ош.value.error_code == "GRANT_AUDIENCE_MISMATCH"
        assert цель["мир"].эффектов("create") == 0

    def test_03_другой_site_id(self, стенд):
        цель, план, основа, исп = _подготовить(стенд)
        подпись, полезное = выпустить_grant(стенд, **{**основа,
                                                      "site_id": "другой-сайт"})
        with pytest.raises(G.GrantError) as ош:
            исп.выполнить(подпись=подпись, полезное=полезное,
                          ожидания=ожидания(**основа), план=план,
                          idempotency_key="neg-3")
        assert ош.value.error_code == "GRANT_SITE_MISMATCH"
        assert цель["мир"].эффектов("create") == 0

    def test_04_другой_plan_hash(self, стенд):
        цель, план, основа, исп = _подготовить(стенд)
        подпись, полезное = выпустить_grant(
            стенд, **{**основа, "plan_hash": "подменённый-план"})
        with pytest.raises(G.GrantError) as ош:
            исп.выполнить(подпись=подпись, полезное=полезное,
                          ожидания=ожидания(**основа), план=план,
                          idempotency_key="neg-4")
        assert ош.value.error_code == "GRANT_PLAN_MISMATCH"
        assert цель["мир"].эффектов("create") == 0

    def test_05_другой_артефакт(self, стенд):
        цель, план, основа, исп = _подготовить(стенд)
        подпись, полезное = выпустить_grant(
            стенд, **{**основа, "artifact_digest": "sha256:" + "0" * 32})
        with pytest.raises(G.GrantError) as ош:
            исп.выполнить(подпись=подпись, полезное=полезное,
                          ожидания=ожидания(**основа), план=план,
                          idempotency_key="neg-5")
        assert ош.value.error_code == "GRANT_ARTIFACT_MISMATCH"
        assert цель["мир"].эффектов("create") == 0

    def test_06_другая_версия_реестра(self, стенд):
        цель, план, основа, исп = _подготовить(стенд)
        подпись, полезное = выпустить_grant(
            стенд, **{**основа, "registry_fingerprint": "устаревший"})
        with pytest.raises(G.GrantError) as ош:
            исп.выполнить(подпись=подпись, полезное=полезное,
                          ожидания=ожидания(**основа), план=план,
                          idempotency_key="neg-6")
        assert ош.value.error_code == "GRANT_REGISTRY_STALE"
        assert цель["мир"].эффектов("create") == 0

    def test_07_истёкшее_разрешение(self, стенд):
        цель, план, основа, исп = _подготовить(стенд)
        подпись, полезное = выпустить_grant(стенд, **основа, срок_сек=-5)
        with pytest.raises(G.GrantError) as ош:
            исп.выполнить(подпись=подпись, полезное=полезное,
                          ожидания=ожидания(**основа), план=план,
                          idempotency_key="neg-7")
        assert ош.value.error_code == "GRANT_EXPIRED"
        assert цель["мир"].эффектов("create") == 0

    def test_08_подделанное_разрешение(self, стенд):
        """Подпись проверяется до притязаний: иначе сверялось бы враньё."""
        цель, план, основа, исп = _подготовить(стенд)
        подпись, полезное = выпустить_grant(стенд, **основа)
        полезное = {**полезное, "site_id": стенд["site_id"] + "-подмена"}
        with pytest.raises(G.GrantError) as ош:
            исп.выполнить(подпись=подпись, полезное=полезное,
                          ожидания=ожидания(**основа), план=план,
                          idempotency_key="neg-8")
        assert ош.value.error_code == "APPROVAL_SIGNATURE_INVALID"
        assert цель["мир"].эффектов("create") == 0

    def test_09_отказ_не_оставляет_притязания(self, стенд):
        """Отклонённый вызов не должен выглядеть как начатая работа."""
        цель, план, основа, исп = _подготовить(стенд)
        подпись, полезное = выпустить_grant(стенд, **основа, срок_сек=-5)
        with pytest.raises(G.GrantError):
            исп.выполнить(подпись=подпись, полезное=полезное,
                          ожидания=ожидания(**основа), план=план,
                          idempotency_key="neg-9")
        assert исп.притязание("neg-9") is None
        assert исп.незавершённые() == []


# =============================================================================
# 4. Недостающая способность службы подписи
# =============================================================================

class TestНедостающаяСпособность:
    def test_служба_не_выдаёт_разрешение_templates_executor(self, стенд):
        """Зафиксированный блокер: механизм работает, аудитории нет."""
        цель = собрать_цель(стенд)
        cid, _ = довести_до_approved(стенд, цель)
        аренда = S.взять_аренду(стенд["соед"], cid, "changeset-worker")
        код, тело = запросить_grant(стенд, cid, audience=G.АУДИТОРИЯ,
                                    fencing_token=аренда["fencing_token"])
        assert код == 403
        assert тело["error_code"] == "AUDIENCE_NOT_ALLOWED"

    def test_механизм_при_этом_исправен(self, стенд):
        цель = собрать_цель(стенд)
        cid, _ = довести_до_approved(стенд, цель)
        аренда = S.взять_аренду(стенд["соед"], cid, "changeset-worker")
        код, тело = запросить_grant(стенд, cid, audience="changeset-worker",
                                    fencing_token=аренда["fencing_token"])
        assert код == 200 and тело["grant"]["typ"] == "execution-grant"

    def test_выдаваемое_разрешение_неполно_для_адаптера(self, стенд):
        """Даже допустимой аудитории не хватает притязаний."""
        цель = собрать_цель(стенд)
        cid, _ = довести_до_approved(стенд, цель)
        аренда = S.взять_аренду(стенд["соед"], cid, "changeset-worker")
        _, тело = запросить_grant(стенд, cid, audience="changeset-worker",
                                  fencing_token=аренда["fencing_token"])
        нет = [п for п in G.ОБЯЗАТЕЛЬНЫЕ if not тело["grant"].get(п)]
        assert set(нет) >= {"jti", "resource_kind", "artifact_digest"}


# =============================================================================
# 5. Расхождение, компенсация и возврат к точному baseline
# =============================================================================

class TestРасхождениеИКомпенсация:
    """Расхождение возникает между применением и подтверждением.

    Откатить набор из SUCCEEDED машина состояний не даёт — и правильно: после
    успеха компенсация идёт отдельным набором. Поэтому расхождение создаётся
    там, где оно случается в жизни: цель приняла эффект, но встала не в то
    состояние, и подтверждение обязано это увидеть ДО объявления успеха.
    """

    def test_расхождение_обнаружено_и_компенсировано(self, стенд):
        from factory.site_engine.provisioner.providers import fake as F
        цель = собрать_цель(стенд)
        cid, движок = довести_до_approved(стенд, цель)
        аренда = S.взять_аренду(стенд["соед"], cid, "changeset-worker")
        маркер = аренда["fencing_token"]
        набор = S.получить(стенд["соед"], cid)
        план = набор["dry_run_result"]["per_site_plan"][стенд["site_id"]]
        baseline = план["before_fingerprint"]

        цель["мир"].сломать(F.ИСКАЖЕНИЕ_ПОСЛЕ_ПРИМЕНЕНИЯ)
        итог = движок.применить(cid, actor_id="service:control-plane",
                                служба="control-plane", fencing_token=маркер)

        assert итог["status"] == M.ROLLED_BACK, (
            "подтверждение обязано отвергнуть успех при расхождении")
        assert итог.get("canary_failed") == стенд["site_id"]
        сверка = итог["results"][стенд["site_id"]]["verify"]
        assert сверка["ok"] is False and сверка["mismatch"]

        после = цель["адаптер"].observe(
            site_id=стенд["site_id"], resource_id=набор["resource_id"])
        assert после["fingerprint"] == baseline, (
            "компенсация обязана вернуть цель к точному исходному отпечатку")
        assert цель["мир"].эффектов("create") == 1
        assert цель["мир"].эффектов("delete") == 1

    def test_повторная_доставка_не_повторяет_ни_apply_ни_rollback(self, стенд):
        from factory.site_engine.provisioner.providers import fake as F
        import pytest as _pytest
        цель = собрать_цель(стенд)
        cid, движок = довести_до_approved(стенд, цель)
        аренда = S.взять_аренду(стенд["соед"], cid, "changeset-worker")
        маркер = аренда["fencing_token"]
        цель["мир"].сломать(F.ИСКАЖЕНИЕ_ПОСЛЕ_ПРИМЕНЕНИЯ)
        движок.применить(cid, actor_id="service:control-plane",
                         служба="control-plane", fencing_token=маркер)
        создано, удалено = (цель["мир"].эффектов("create"),
                            цель["мир"].эффектов("delete"))
        assert (создано, удалено) == (1, 1)

        # Повтор доставки завершённого набора отвергает машина состояний —
        # до адаптера вызов не доходит, и второго эффекта быть не может.
        with _pytest.raises(S.ChangeSetError) as ош:
            движок.применить(cid, actor_id="service:control-plane",
                             служба="control-plane", fencing_token=маркер)
        assert ош.value.error_code == "TRANSITION_NOT_ALLOWED"
        assert цель["мир"].эффектов("create") == создано
        assert цель["мир"].эффектов("delete") == удалено
