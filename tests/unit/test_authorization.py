"""REQ-AUTH: без явной авторизации production не мутируется."""
from factory import pipeline, validation


def test_production_without_authorization_is_blocked(temp_site):
    def mutate(package):
        package["environment"] = "production"
        package["production_authorized"] = False
    site = temp_site(mutate)
    result = validation.validate(site)
    assert result.status in ("BLOCKED_AUTHORIZATION", "BLOCKED_INPUT")


def test_pipeline_refuses_production_and_applies_no_mutation(temp_site):
    def mutate(package):
        package["environment"] = "production"
        package["production_authorized"] = False
        package["fixture"] = False
    site = temp_site(mutate)
    outcome = pipeline.run_job(site, environment="production", skip_browser=True)
    assert outcome.status.startswith("BLOCKED")
    assert outcome.base_url is None
    import json
    result = json.loads(outcome.result_path.read_text(encoding="utf-8"))
    assert result["mutations"] == [], "заблокированное задание не меняет инфраструктуру"


def test_authorized_production_still_needs_operator_flag(temp_site):
    """Даже с production_authorized оператор подтверждает выкат отдельно."""
    def mutate(package):
        package.update({
            "environment": "production", "production_authorized": True, "fixture": False,
            "dle_license_ref": "lic-absent", "dle_distribution_ref": "dist-absent",
            "dle_distribution_sha256": "a" * 64, "ssh_host_ref": "host-absent",
            "authorized_by": "operator@example.test", "authorized_at": "2026-08-21T00:00:00Z",
        })
        package["content_source"]["kind"] = "vk"
    site = temp_site(mutate)
    outcome = pipeline.run_job(site, environment="production", skip_browser=True, allow_production=False)
    assert outcome.status.startswith("BLOCKED")


def test_staging_success_is_not_production_permission(temp_site):
    site = temp_site()
    outcome = pipeline.run_job(site, environment="staging", dry_run=True, skip_browser=True)
    assert outcome.status == "BUILT"
    assert any("не является разрешением на production" in note for note in outcome.notes)
    import json
    result = json.loads(outcome.result_path.read_text(encoding="utf-8"))
    assert result["mutations"] == [], "dry-run не меняет инфраструктуру"
