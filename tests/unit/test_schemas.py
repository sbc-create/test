"""REQ-PACKAGE, REQ-DLE-VERSION, REQ-DLE-ISOLATION: строгая схема входа."""
import copy
import json

import jsonschema
import pytest

from factory.paths import PATHS
from factory import validation


@pytest.fixture(scope="module")
def schema():
    return json.loads((PATHS.schemas / "site-package.schema.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def validator(schema):
    return jsonschema.Draft202012Validator(schema)


def test_schema_itself_is_valid(schema):
    jsonschema.Draft202012Validator.check_schema(schema)


def test_pilot_package_is_valid(validator, pilot_package):
    assert list(validator.iter_errors(pilot_package)) == []


def _errors(validator, package):
    return [f"{'/'.join(str(p) for p in e.absolute_path)}: {e.message}" for e in validator.iter_errors(package)]


@pytest.mark.parametrize("field", [
    "domain", "canonical_url", "environment", "production_authorized", "target_ref",
    "brand", "theme_ref", "metadata", "seo", "navigation", "legal", "content_source",
    "runtime", "backup_policy", "acceptance", "rollback_policy", "requested_by",
])
def test_missing_required_field_is_rejected(validator, pilot_package, field):
    package = copy.deepcopy(pilot_package)
    package.pop(field)
    assert _errors(validator, package), f"отсутствие {field} обязано быть ошибкой"


def test_unknown_field_is_rejected(validator, pilot_package):
    package = copy.deepcopy(pilot_package)
    package["shadow_setting"] = True
    assert _errors(validator, package)


def test_dle_version_is_pinned(validator, pilot_package):
    package = copy.deepcopy(pilot_package)
    package["dle_version"] = "20.1"
    assert _errors(validator, package), "автопереход на другую версию DLE запрещён"


def test_production_requires_authorization_and_license(validator, pilot_package):
    package = copy.deepcopy(pilot_package)
    package["environment"] = "production"
    package["production_authorized"] = False
    errors = _errors(validator, package)
    assert any("production_authorized" in e or "dle_license_ref" in e for e in errors)


def test_production_forbids_fixture(validator, pilot_package):
    package = copy.deepcopy(pilot_package)
    package.update({"environment": "production", "production_authorized": True, "fixture": True,
                    "dle_license_ref": "lic-1", "dle_distribution_ref": "dist-1",
                    "dle_distribution_sha256": "a" * 64, "ssh_host_ref": "h1",
                    "authorized_by": "x", "authorized_at": "2026-08-21T00:00:00Z"})
    assert any("fixture" in e for e in _errors(validator, package))


def test_vk_source_requires_rights_fields(validator, pilot_package):
    package = copy.deepcopy(pilot_package)
    package["content_source"] = {"kind": "vk", "rights_confirmed": True}
    errors = _errors(validator, package)
    assert any(k in " ".join(errors) for k in ("catalog_ref", "rights_manifest_ref", "catalog_sha256"))


def test_advertising_enabled_requires_contract(validator, pilot_package):
    package = copy.deepcopy(pilot_package)
    package["advertising"] = {"enabled": True, "provider": "vk_adman_adtech", "adapter": "official"}
    assert any("contract_ref" in e or "placements" in e for e in _errors(validator, package))


def test_pagination_template_is_constrained(validator, pilot_package):
    package = copy.deepcopy(pilot_package)
    package["seo"]["pagination_template"] = "/p/{n}"
    assert _errors(validator, package), "смешение схем пагинации запрещено"


def test_database_isolation_fields_exist(schema):
    db = schema["properties"]["runtime"]["properties"]["database"]["properties"]
    assert {"name", "user", "password_secret_ref"} <= set(db), "у каждого сайта своя БД и свой пользователь"


def test_job_result_schema_is_valid():
    schema = json.loads((PATHS.schemas / "job-result.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    check = schema["properties"]["checks"]["items"]
    assert set(check["required"]) == {"id", "command", "exit_code", "passed", "artifact"}, \
        "проверка без команды, кода возврата и артефакта не может считаться выполненной"
