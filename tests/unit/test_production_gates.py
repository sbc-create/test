"""REQ-AUTH, REQ-DLE-LICENSE: производственные ворота доказываются вызовом, а не чтением.

Мутационная проверка ревьюера показала, что оба гейта можно было удалить, не уронив
ни одного теста: схема отклоняла пакет раньше, чем срабатывала семантика.
"""
import copy
import json

import pytest
import yaml

from factory import inventory, licensing, pipeline, validation
from factory.paths import PATHS


def _production_package(base: dict, **overrides) -> dict:
    package = copy.deepcopy(base)
    package.update({
        "environment": "production",
        "production_authorized": True,
        "fixture": False,
        "domain": "example.tld",
        "canonical_url": "https://example.tld/",
        "dle_license_ref": "lic-test",
        "dle_distribution_ref": "dist-test",
        "dle_distribution_sha256": "a" * 64,
        "ssh_host_ref": "stage-test",
        "target_ref": "prod-test",
        "authorized_by": "operator@example.tld",
        "authorized_at": "2026-08-21T00:00:00Z",
    })
    package["content_source"] = {
        "kind": "vk", "catalog_ref": "content/catalog.json", "catalog_version": "2026-08-21",
        "catalog_sha256": package["content_source"]["catalog_sha256"],
        "provenance": "лицензионная выгрузка", "rights_manifest_ref": "content/rights-manifest.yaml",
        "rights_confirmed": True, "allowed_fields": ["title", "description"],
    }
    package["vk_video"] = {"enabled": True, "adapter": "official",
                           "contract_ref": "content/vk-player-contract.fixture.yaml",
                           "video_ids": ["v1"], "player_configuration": {}, "playback_mode": "embed_white_player"}
    package.update(overrides)
    return package


@pytest.fixture
def production_site(temp_site, pilot_package, monkeypatch):
    """Полностью валидный production-пакет с подставленным инвентарём."""
    monkeypatch.setattr(inventory, "target", lambda ref: {
        "ref": "prod-test", "adapter": "local_disposable", "environments": ["production"],
        "root": "var/targets/test-production", "bind_host": "127.0.0.1", "port_range": [8091, 8095],
        "production_capable": True,
    })
    monkeypatch.setattr(inventory, "ssh_host", lambda ref: {
        "ref": "stage-test", "hostname": "prod.example.tld", "deploy_user": "deploy",
        "known_hosts_entry_ref": "inventory/known_hosts.d/stage-test",
    })
    monkeypatch.setattr(inventory, "all_licenses", lambda: [
        {"ref": "lic-test", "covered_domain": "example.tld", "covers_subdomains": True, "version": "20.0"}])

    def make(**overrides):
        return temp_site(lambda pkg: pkg.update(_production_package(pilot_package, **overrides)))
    return make


def test_valid_production_package_passes_validation(production_site):
    result = validation.validate(production_site())
    assert result.status == "READY", [b.as_dict() for b in result.blockers]


def test_unauthorized_production_is_blocked_authorization(production_site):
    """Точное равенство: раньше сюда доходил BLOCKED_INPUT от схемы."""
    site = production_site(production_authorized=False, authorized_by=None, authorized_at=None)
    result = validation.validate(site)
    assert result.status == "BLOCKED_AUTHORIZATION"
    assert any(b.field == "production_authorized" for b in result.blockers)


def test_pipeline_refuses_unauthorized_production_without_mutation(production_site):
    site = production_site(production_authorized=False, authorized_by=None, authorized_at=None)
    outcome = pipeline.run_job(site, skip_browser=True, allow_production=True)
    assert outcome.status == "BLOCKED_AUTHORIZATION"
    data = json.loads(outcome.result_path.read_text(encoding="utf-8"))
    assert data["mutations"] == []


def test_pipeline_requires_operator_confirmation(production_site):
    """production_authorized: true необходим, но недостаточен."""
    site = production_site()
    outcome = pipeline.run_job(site, skip_browser=True, allow_production=False)
    assert outcome.status == "BLOCKED_AUTHORIZATION"
    assert any("подтверждения оператора" in b["reason"] for b in outcome.blockers)


def test_pipeline_blocks_production_without_license(production_site, monkeypatch):
    monkeypatch.setattr(inventory, "all_licenses", lambda: [])
    site = production_site()
    outcome = pipeline.run_job(site, skip_browser=True, allow_production=True)
    assert outcome.status == "BLOCKED_LICENSE"
    data = json.loads(outcome.result_path.read_text(encoding="utf-8"))
    assert data["mutations"] == [], "заблокированный по лицензии job не трогает инфраструктуру"


def test_pipeline_blocks_license_for_another_domain(production_site, monkeypatch):
    monkeypatch.setattr(inventory, "all_licenses", lambda: [
        {"ref": "lic-test", "covered_domain": "other.tld", "version": "20.0"}])
    outcome = pipeline.run_job(production_site(), skip_browser=True, allow_production=True)
    assert outcome.status == "BLOCKED_LICENSE"


def test_pipeline_blocks_non_production_capable_target(production_site, monkeypatch):
    monkeypatch.setattr(inventory, "target", lambda ref: {
        "ref": "prod-test", "adapter": "local_disposable", "environments": ["production"],
        "root": "var/targets/test-production", "production_capable": False,
    })
    outcome = pipeline.run_job(production_site(), skip_browser=True, allow_production=True)
    assert outcome.status == "BLOCKED_ACCESS"


def test_environment_flag_cannot_downgrade_production(production_site):
    """Подмена окружения флагом обходила бы лицензию, авторизацию и smoke."""
    site = production_site()
    outcome = pipeline.run_job(site, environment="staging", skip_browser=True)
    assert outcome.status == "BLOCKED_INPUT"
    assert any(b["field"] == "environment" for b in outcome.blockers)


def test_mock_adapters_are_rejected_in_production(production_site):
    site = production_site(vk_video={"enabled": True, "adapter": "mock",
                                     "contract_ref": "content/vk-player-contract.fixture.yaml",
                                     "video_ids": ["v1"], "player_configuration": {},
                                     "playback_mode": "embed_white_player"})
    result = validation.validate(site)
    assert result.status in ("BLOCKED_RIGHTS", "BLOCKED_INPUT")
