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


def test_rollback_is_named_and_its_limit_is_stated(запись):
    откат = запись["rollback"]
    assert откат["target_release"].startswith("/srv/lords/.frontend/releases/")
    assert откат["verified"] is False
    assert откат["verified_reason"]
    # Ограничение обязано быть названо, а не умолчано: байтов, которые
    # отдаются сейчас, на диске нет.
    assert "d2e9628f" in откат["limitation"]


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
    assert "не выкачено" in пакет


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
