"""B16 — гейт пакета владельца на выкат.

Паспорт: ANIMEDIA_BLOCK_SPEC_V1/B16. Выкат здесь не выполняется и выполняться
не может: это действие владельца. Проверяется другое — что пакет и запись
артефакта не разошлись с деревом и друг с другом.

Без такой проверки пакет тихо стареет: один коммит в шаблон меняет цифру
артефакта, разрешение владельца остаётся привязанным к прежней цифре, и выкат
уходит не на то, что приняли.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EV = ROOT / "artifacts/evidence/animedia-blockwise-parity-03-2026-09-20"
ПАКЕТ = EV / "03-blocks" / "B16_OWNER_DEPLOY_PACKET.md"
ЗАПИСЬ = EV / "03-blocks" / "B16_ARTIFACT.json"
АРТЕФАКТ = ROOT / "automation/host/lords-frontend.py"
CONTRACT_SHA = (EV / "00-contract" / "CONTRACT_SHA256.txt").read_text(
    encoding="utf-8").strip()


@pytest.fixture(scope="module")
def запись() -> dict:
    assert ЗАПИСЬ.is_file(), "нет записи артефакта B16"
    return json.loads(ЗАПИСЬ.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def пакет() -> str:
    assert ПАКЕТ.is_file(), "нет пакета владельца B16"
    return ПАКЕТ.read_text(encoding="utf-8")


def _цифра() -> str:
    return hashlib.sha256(АРТЕФАКТ.read_bytes()).hexdigest()


def test_contract_digest_unchanged() -> None:
    assert CONTRACT_SHA == (
        "5f2112e25ef974333c388bad405abfae3c3d460a713b028afa3c0e549b8eaeb3")


def test_artifact_record_matches_the_tree(запись):
    assert запись["artifact"]["artifact_sha256"] == _цифра(), (
        "запись артефакта устарела: пересоберите её после последнего коммита "
        "в automation/host/lords-frontend.py")
    assert запись["artifact"]["bytes"] == АРТЕФАКТ.stat().st_size


def test_packet_names_the_same_digest(пакет):
    цифры = set(re.findall(r"\b[0-9a-f]{64}\b", пакет))
    assert _цифра() in цифры, (
        "пакет владельца называет другую цифру артефакта, чем лежит в дереве")


def test_owner_approval_is_bound_to_the_digest(запись):
    assert запись["owner_approval_required"] is True
    assert запись["owner_approval_bound_to"] == _цифра()


def test_nothing_was_deployed_or_mutated(запись):
    for поле in ("deploy_performed", "restart_performed", "dns_mutations",
                 "indexability_mutations", "push_performed", "merge_performed"):
        assert запись[поле] == 0, поле


def test_release_gate_result_is_recorded_and_green(запись):
    гейт = запись["release_gate"]
    assert гейт["ok"] is True
    assert гейт["flags"]["RUNTIME_DOWNGRADE"] == 0
    assert гейт["flags"]["RUNTIME_COMPATIBLE"] == 1
    assert гейт["flags"]["CONTENT_SNAPSHOT_DIGEST_MATCH"] == 1
    assert гейт["flags"]["CATALOG_DETAILS_SKEW"] == 0


def test_indexability_before_is_recorded_closed(запись):
    for домен, состояние in запись["live_before"].items():
        assert "noindex" in состояние["x_robots"], домен


def test_rollback_target_reproduces_the_live_artifact(запись):
    """Цель откáта обязана быть тем, что отдаётся сейчас, а не «чем-то рабочим».

    Прежняя цель `legacy-b32438c91aaa` содержала сборку с линии Lords: она
    поднимается, но на отсутствующем маршруте отдаёт 503 вместо 404. Откат на
    неё вернул бы не сегодняшнее состояние, а регрессию. Живой артефакт
    воспроизводится из git, поэтому цель собрана из коммита.
    """
    откат = запись["rollback"]
    assert откат["target_release"].startswith("/srv/lords/.frontend/releases/")
    assert откат["artifact_sha256"] == (
        "d2e9628f2a4b14c56ef28a6814b53f49cdb4017db1ab8ddebebb79aaad39e908")
    assert откат["reproduces_live_artifact_byte_for_byte"] is True
    assert откат["verified"] is True
    assert откат["verified_how"]
    отклонённая = откат["previous_target_rejected"]
    assert "legacy-b32438c91aaa" in отклонённая["release"]
    assert "503" in отклонённая["why"]


def test_scope_is_animedia_only(запись):
    assert запись["deploy_scope"] == ["animedia.icu", "animedia.space"]
    соседи = set(запись["out_of_scope_sites_sharing_the_runtime"])
    assert соседи == {"lords-01", "lords-02", "lords-03", "zona-01"}


def test_packet_states_that_a_restart_is_not_a_no_op(пакет):
    assert "не пустая операция" in пакет
    assert "b32438c91aaa" in пакет


def test_packet_does_not_claim_a_deploy_happened(пакет):
    for ложь in ("выкат выполнен", "DEPLOY_PERFORMED=1", "RESTART_PERFORMED=1"):
        assert ложь not in пакет, ложь
    # Пакет обязан прямо называть, что осталось несделанным. Сейчас это
    # перезапуск: назначение и подпись витрины уже переключены парой.
    assert "осталась одна команда: перезапуск" in пакет
    assert "systemctl restart nova-animedia-01.service" in пакет
    assert "DEPLOY_PERFORMED=0" in пакет


def test_baseline_manifest_untouched_by_this_stage():
    """Манифест владения этой стадией не правился — только записан конфликт."""
    import subprocess

    изменён = subprocess.run(
        ["git", "log", "--oneline", "de477ec..HEAD", "--",
         "config/TEMPLATE-BASELINE-MANIFEST.json"],
        cwd=str(ROOT), capture_output=True, text=True).stdout.strip()
    assert изменён == "", f"манифест правился: {изменён}"
    план = EV.parent / "animedia-cursor-reconciliation-01" / "SHARED_WRITER_TRANSFER_PLAN.md"
    assert план.is_file(), "нет плана переноса в каноническую линию"


def test_canary_is_armed_as_a_pair_and_only_on_one_site(запись):
    """Манифест и назначение переключены вместе, и только у канарейки.

    Порознь их переключать нельзя: новый код со старой подписью заставил бы
    витрину объявлять не то, что она исполняет. Вторая витрина остаётся
    сравнением, иначе канарейка не канарейка.
    """
    ст = запись["staged_deploy"]
    assert ст["candidate_release"].startswith("/srv/lords/.frontend/releases/")
    assert ст["candidate_release_files"]["lords-frontend.py"] == _цифра()
    assert ст["candidate_boots"] is True
    assert ст["candidate_reports_new_identity_with_candidate_manifest"] is True
    assert ст["symlink_armed"] is True
    assert ст["armed_site"] == "animedia-01"
    assert ст["animedia_02_untouched"] is True
    пара = ст["armed_pair"]
    assert пара["manifest_build_id"] in пара["symlink"]
    assert пара["manifest_backup"].endswith(".before-b16")
    assert пара["manifest_owner_note"]
    assert ст["remaining_owner_action"] == "systemctl restart nova-animedia-01.service"
    assert ст["restart_denied_by_profile"]


def test_arming_did_not_change_the_live_state(запись):
    """Код выбирается при старте процесса, поэтому зарядка ничего не меняет."""
    живое = запись["live_after_arming"]["animedia.icu"]
    assert живое["build_id"] == "20260920T102102Z-89666321-nova"
    assert живое["artifact_sha256"] == (
        "d2e9628f2a4b14c56ef28a6814b53f49cdb4017db1ab8ddebebb79aaad39e908")
    assert "noindex" in живое["x_robots"]


def test_rollback_drill_was_performed_end_to_end(запись):
    учение = запись["rollback"]["drill"]
    assert учение["performed"] is True
    assert учение["manifest_restored_byte_for_byte"] is True
    assert учение["rollback_target_reproduces_live_artifact"] is True
    assert учение["live_unchanged_during_drill"] is True


def test_earlier_wrong_statement_is_corrected(запись):
    """Прежний пакет утверждал, что вернуться в текущее live невозможно."""
    assert "8966632" in запись["correction_of_earlier_statement"]
