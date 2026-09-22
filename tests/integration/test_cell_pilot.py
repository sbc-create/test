"""Приёмка изолированного пилота PORTABLE-SITE-CELL-01.

Доказывает: REQ-CELL-NEIGHBOR, REQ-CELL-URLS, REQ-CELL-OUTAGE.

Прогон один на весь модуль: сценарий приёмки длинный, и повторять его на каждое
утверждение значило бы платить за одно и то же по двадцать раз. Утверждения
разнесены по тестам, чтобы падение называло конкретные ворота, а не «пилот».
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from cell_pilot import run_pilot  # noqa: E402


@pytest.fixture(scope="module")
def pilot_run(tmp_path_factory):
    return run_pilot(tmp_path_factory.mktemp("cell-pilot"))


def test_no_gate_failed(pilot_run):
    failed = [g.name for g in pilot_run.gates if g.status == "FAIL"]
    assert failed == [], f"провалены ворота: {failed}"


def test_every_gate_reports_a_real_verdict(pilot_run):
    """Ворот без исхода не бывает: NOT_RUN обязан назвать причину."""
    for gate in pilot_run.gates:
        assert gate.status in ("PASS", "FAIL", "NOT_RUN"), gate.name
        if gate.status == "NOT_RUN":
            assert gate.detail.get("reason"), f"{gate.name}: NOT_RUN без причины"


def test_template_is_never_handed_to_two_sites(pilot_run):
    gate = next(g for g in pilot_run.gates if g.name == "TEMPLATE_ASSIGNMENT")
    assert gate.status == "PASS"
    assert gate.detail["unique"] == len(gate.detail["handed_out"])


def test_repeating_onboarding_spends_no_second_template(pilot_run):
    gate = next(g for g in pilot_run.gates if g.name == "ONBOARDING_RETRY")
    assert gate.status == "PASS"
    assert gate.detail["free_after_repeat"] == gate.detail["free_before"] - 1


def test_published_urls_survive_content_changes(pilot_run):
    """REQ-CELL-URLS: ни один действующий адрес не исчез и не опустел."""
    urls = next(g for g in pilot_run.gates if g.name == "URLS_BEFORE_AFTER")
    lost = next(g for g in pilot_run.gates if g.name == "LOST_URLS")
    assert urls.status == "PASS"
    assert lost.detail["lost"] == []
    assert urls.detail["after_total"] >= urls.detail["before_total"]


def test_every_catalog_record_has_its_own_page(pilot_run):
    """Совпавшие адреса не видны в сравнении инвентарей — их ловит полнота."""
    gate = next(g for g in pilot_run.gates if g.name == "CATALOG_COMPLETENESS")
    assert gate.status == "PASS"
    assert gate.detail["title_pages"] == gate.detail["catalog_records"]


def test_unknown_address_is_a_real_404(pilot_run):
    gate = next(g for g in pilot_run.gates if g.name == "UNKNOWN_ROUTE_IS_404")
    assert gate.status == "PASS"


def test_site_works_while_the_centre_is_unreachable(pilot_run):
    """REQ-CELL-OUTAGE: страницы отдаются, комментарии и голоса принимаются."""
    gate = next(g for g in pilot_run.gates if g.name == "CENTRAL_OUTAGE")
    assert gate.status == "PASS"
    assert gate.detail["pages_served"] is True
    assert gate.detail["local_writes_accepted"] is True
    # Недоступность названа недоступностью, а не нулём записей.
    assert gate.detail["upstream_reported"] is True
    assert gate.detail["last_verified_revision"] > 0


def test_delivery_resumes_without_duplicates_after_recovery(pilot_run):
    gate = next(g for g in pilot_run.gates if g.name == "RECOVERY_DELIVERY")
    assert gate.status == "PASS"
    assert gate.detail["replay_applied"] == 0
    assert gate.detail["new_title_published"] is True


def test_owners_do_not_overwrite_each_other(pilot_run):
    gate = next(g for g in pilot_run.gates if g.name == "FIELD_OWNERSHIP")
    assert gate.status == "PASS"
    assert gate.detail["seo_text_survived_catalog_update"] is True
    assert gate.detail["episodes_survived_seo_edit"] is True
    assert gate.detail["rating_and_seo_coexist"] is True


def test_targeted_release_leaves_the_neighbour_untouched(pilot_run):
    """REQ-CELL-NEIGHBOR: соседний экземпляр остаётся на прежнем digest и данных."""
    gate = next(g for g in pilot_run.gates if g.name == "NEIGHBOR_UNCHANGED")
    assert gate.status == "PASS"
    assert gate.detail["digest_before"] == gate.detail["digest_after"]
    assert gate.detail["rows_before"] == gate.detail["rows_after"]


def test_another_tenant_cannot_be_opened_or_installed_into(pilot_run):
    gate = next(g for g in pilot_run.gates if g.name == "TENANT_ACCESS_DENIED")
    assert gate.status == "PASS"
    assert gate.detail["forged_site_id_refused"] is True
    assert gate.detail["foreign_artifact_refused"] is True


def test_rollback_keeps_comments_votes_and_seo_text(pilot_run):
    gate = next(g for g in pilot_run.gates if g.name == "CUTOVER_ROLLBACK")
    assert gate.status == "PASS"
    assert gate.detail["comment_kept"] is True
    assert gate.detail["seo_text_kept"] is True
    assert gate.detail["votes_kept"] >= 1


def test_two_writing_instances_are_impossible(pilot_run):
    gate = next(g for g in pilot_run.gates if g.name == "LIVE_MUTATIONS")
    assert gate.status == "PASS"
    assert gate.detail["old_side_frozen"] is True
    # Домен не переключался, и пилот об этом говорит прямо.
    assert gate.detail["dns_switched"] is False


def test_reinstall_keeps_the_data(pilot_run):
    gate = next(g for g in pilot_run.gates if g.name == "RESTORE")
    assert gate.status == "PASS"
    assert gate.detail["reinstall_kept_data"] is True
    assert gate.detail["integrity_check"] is True


def test_release_digest_is_reproducible(pilot_run):
    gate = next(g for g in pilot_run.gates if g.name == "RELEASE_DIGEST")
    assert gate.status == "PASS"
    assert gate.detail["reproducible"] is True


def test_stale_session_cannot_overwrite_a_newer_release(pilot_run):
    gate = next(g for g in pilot_run.gates if g.name == "STALE_DEPLOY_REJECTED")
    assert gate.status == "PASS"


def test_retired_publisher_ids_never_reach_the_page(pilot_run):
    gate = next(g for g in pilot_run.gates if g.name == "PLAYER_PUBLISHER_ID")
    assert gate.detail["retired_ids_present"] is False
    assert gate.detail["publisher_id"] == "10252"


def test_each_site_has_its_own_database_outside_the_release(pilot_run):
    gate = next(g for g in pilot_run.gates if g.name == "LOCAL_DB")
    assert gate.status == "PASS"
    assert gate.detail["separate_files"] is True
    assert gate.detail["inside_release_directory"] is False


def test_seo_layer_cannot_write_catalog_fields(pilot_run):
    gate = next(g for g in pilot_run.gates if g.name == "SEO_CONTRACT")
    assert gate.status == "PASS"
    assert gate.detail["seo_cannot_write_catalog_fields"] is True


def test_deploy_is_addressed_to_one_site(pilot_run):
    gate = next(g for g in pilot_run.gates if g.name == "TARGETED_DEPLOY")
    assert gate.status == "PASS"
    assert gate.detail["sites_touched"] == ["pilot-cell"]


def test_ci_template_exists_even_though_no_remote_was_created(pilot_run):
    """Отсутствие прав на remote не отменяет шаблон CI — и не выдаётся за успех."""
    gate = next(g for g in pilot_run.gates if g.name == "REMOTE_CI")
    assert gate.status == "NOT_RUN"
    assert gate.detail["ci_template_parses"] is True
    assert gate.detail["remote_created"] is False
    assert gate.detail["reason"]


def test_os_level_isolation_is_not_claimed(pilot_run):
    """Отдельные каталоги — это не отдельные права, и путать их нельзя."""
    gate = next(g for g in pilot_run.gates if g.name == "OS_LEVEL_ISOLATION")
    assert gate.status == "NOT_RUN"
    assert gate.detail["not_attempted"]
    assert gate.detail["reason"]


def test_cross_host_and_dns_are_reported_as_not_run(pilot_run):
    """Локальная проверка не выдаётся за межсерверный перенос."""
    for name in ("CROSS_HOST_TEST", "DNS_SWITCHED"):
        gate = next(g for g in pilot_run.gates if g.name == name)
        assert gate.status == "NOT_RUN"
        assert gate.detail["reason"]
