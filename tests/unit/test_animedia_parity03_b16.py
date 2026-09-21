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


def test_session_performed_no_forbidden_mutation(запись):
    """Что сессии запрещено — того она не делала, и это записано поимённо.

    Прежняя редакция проверяла «выката не было вовсе». После выката
    `animedia.icu` такое утверждение стало бы ложным, поэтому проверяется
    другое и более точное: перезапуск, DNS, индексация, push и merge — ноль,
    а выкат назван посайтово.
    """
    м = запись["session_mutations"]
    for поле in ("restart", "dns", "indexability", "push", "merge"):
        assert м[поле] == 0, поле
    assert запись["deploy_performed_per_site"] == {
        "animedia.icu": 1, "animedia.space": 0}


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


def test_packet_states_exactly_what_this_session_did_and_did_not_do(пакет):
    """Пакет обязан отделять сделанное сессией от сделанного владельцем.

    Первая витрина была перезапущена не сессией — `systemctl` ей закрыт.
    Писать «выката не было» значит лгать; писать «выкат выполнила сессия» —
    приписывать себе чужое действие. Названо и то, и другое.
    """
    assert "RESTART_PERFORMED_BY_SESSION=0" in пакет
    assert "Перезапуск `animedia-01` выполнен не ею" in пакет


def test_packet_leads_with_the_owner_visual_rejection(пакет):
    """Шапка пакета обязана начинаться с отказа, а не с зелёных смоуков.

    Пакет читают, чтобы решить, выкатывать ли дальше. Если отказ владельца
    спрятан ниже зелёных проверок, следующая сессия выложит отвергнутую
    сборку на вторую витрину.
    """
    шапка = пакет[:2000]
    assert "OWNER_VISUAL_ACCEPTANCE=REJECTED" in шапка
    assert "LIVE_NOT_OWNER_ACCEPTED" in шапка
    assert "не выкладывается" in шапка
    assert "отменена и повторно не запрашивается" in шапка


def test_owner_visual_acceptance_is_recorded_as_rejected(запись):
    """Технический зелёный смоук не является владельческой приёмкой.

    Владелец отверг кандидата визуально: интерфейс не соответствует оригиналу.
    Запись обязана это держать, иначе следующая сессия прочитает зелёные
    смоуки как приёмку и выложит отвергнутую сборку на вторую витрину.
    """
    в = запись["owner_visual_acceptance"]
    assert в["verdict"] == "REJECTED"
    assert в["artifact_sha256_rejected"] == _цифра()
    assert в["what_previous_tests_did_and_did_not_prove"]
    ст = запись["live_deploy_status"]
    assert ст["animedia-01"]["state"] == "LIVE_NOT_OWNER_ACCEPTED"
    assert ст["animedia-02"]["state"] == "ARMED_BUT_DEPLOY_CANCELLED_BY_OWNER"
    # Команда перезапуска второй витрины отменена — её нельзя выдавать снова.
    assert ст["animedia-02"]["remaining_owner_action"] is None


def test_record_keeps_the_live_facts_of_the_rejected_candidate(запись):
    ст = запись["live_deploy_status"]
    assert ст["animedia-01"]["served_artifact_sha256"] == _цифра()
    assert ст["animedia-01"]["template_version_endpoint_agrees"] is True
    assert "noindex" in ст["animedia-01"]["x_robots_tag"]
    assert ст["animedia-01"]["b14_footer_marker_gone_live"] is True
    # Приёмочный гейт обязан быть пройден именно в режиме deploy и дважды.
    прогоны = ст["animedia-01"]["deploy_mode_smoke"]
    assert len(прогоны) == 2
    for п in прогоны:
        assert п["mode"] == "deploy"
        assert п["SMOKE_PASS"] is True
        assert п["failures"] == []
        assert п["known_build_defects"] == []
    assert запись["restart_performed_by_this_session"] == 0


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


def test_owner_approval_names_both_domains_and_the_digest(запись):
    """Область выката — ровно то, что разрешил владелец, и ни доменом больше."""
    од = запись["owner_production_approval"]
    assert од["bound_to_artifact_sha256"] == _цифра()
    assert од["scope"] == ["animedia.icu", "animedia.space"]
    assert set(од["excluded"]) == {"lords-01", "lords-02", "lords-03", "zona-01"}


def test_both_sites_are_armed_as_pairs(запись):
    """Манифест и назначение переключены вместе — у каждой витрины.

    Порознь их переключать нельзя: новый код со старой подписью заставил бы
    витрину объявлять не то, что она исполняет. Владелец подтвердил выкат на
    обе витрины, поэтому канарейка одной витриной больше не действует — и
    прежнее состояние сохранено в записи как история, а не переписано.
    """
    ст = запись["staged_deploy"]
    assert ст["candidate_release"].startswith("/srv/lords/.frontend/releases/")
    assert ст["candidate_release_files"]["lords-frontend.py"] == _цифра()
    assert ст["candidate_boots"] is True
    assert ст["candidate_reports_new_identity_with_candidate_manifest"] is True
    assert ст["symlink_armed"] is True
    assert ст["armed_sites"] == ["animedia-01", "animedia-02"]
    assert ст["history_canary_only"]["armed_site"] == "animedia-01"

    профили = set()
    for sid in ("animedia-01", "animedia-02"):
        пара = ст["armed_pairs"][sid]
        assert пара["manifest_build_id"] in пара["symlink"]
        assert пара["manifest_artifact_sha256"] == _цифра()
        assert пара["symlink_resolves_to_code_sha256"] == _цифра()
        assert пара["manifest_backup"].endswith(".before-b16")
        assert пара["manifest_backup_matches_pre_arm_state"] is True
        профили.add(пара["manifest_profile"])
    # Подпись каждой витрины осталась своей: общий шаблон, но не общий профиль.
    assert профили == {"animedia-icu", "animedia-space"}
    assert ст["manifest_owner_note"]
    assert ст["remaining_owner_actions"] == [
        "systemctl restart nova-animedia-01.service",
        "systemctl restart nova-animedia-02.service"]
    assert ст["restart_denied_by_profile"]


def test_candidate_was_checked_on_both_profiles_before_arming(запись):
    """Каталоги витрин различаются побайтно — значит и проверять надо обе."""
    пр = запись["staged_deploy"]["prearm_checked_on_both_profiles"]
    assert пр["PREARM_PASS"] is True
    assert пр["cells"] == 54  # 2 витрины × 9 маршрутов × 3 ширины
    assert пр["footer_build_marker_present"] is False


def test_arming_did_not_change_the_live_state(запись):
    """Код выбирается при старте процесса, поэтому зарядка ничего не меняет."""
    живое = запись["live_after_arming"]
    assert set(живое) == {"animedia.icu", "animedia.space"}
    for домен, состояние in живое.items():
        assert состояние["build_id"] == "20260920T102102Z-89666321-nova", домен
        assert состояние["http"] == "200", домен


def test_rollback_drill_covers_both_sites(запись):
    """Откат проверен на том составе витрин, который заряжен, а не на одной."""
    учение = запись["rollback"]["drill_both_sites"]
    assert учение["performed"] is True
    assert учение["rollback_restores_both_sites_exactly"] is True
    assert учение["re_arming_restores_candidate_exactly"] is True
    assert учение["state_after_drill_equals_state_before"] is True
    assert учение["live_unchanged_during_drill"] is True
    for sid in ("animedia-01", "animedia-02"):
        шаги = учение["commands"][sid]
        # Резерв обязан пережить откат: mv унёс бы его, и второй откат стало бы
        # нечем выполнять.
        assert any(с.startswith("install -m 0644") for с in шаги)
        assert not any(с.startswith("mv ") for с in шаги)
        assert шаги[-1] == f"systemctl restart nova-{sid}.service"


def test_rollback_drill_was_performed_end_to_end(запись):
    учение = запись["rollback"]["drill"]
    assert учение["performed"] is True
    assert учение["manifest_restored_byte_for_byte"] is True
    assert учение["rollback_target_reproduces_live_artifact"] is True
    assert учение["live_unchanged_during_drill"] is True


def test_earlier_wrong_statement_is_corrected(запись):
    """Прежний пакет утверждал, что вернуться в текущее live невозможно."""
    assert "8966632" in запись["correction_of_earlier_statement"]
