"""REQ-DLE-PATHS, REQ-CRON: пути и cron не угадываются."""
import yaml

from factory import blueprint
from factory.errors import BlockedInput
from factory.paths import PATHS

import pytest


def test_template_is_marked_as_requiring_official_source():
    data = yaml.safe_load((PATHS.blueprints / "dle20" / "profiles" / "paths.template.yaml").read_text(encoding="utf-8"))
    assert data["source_required"] is True
    for key in ("writable_paths", "immutable_paths", "shared_paths", "installer_entrypoints", "public_deny_paths"):
        assert data[key] == [], f"{key} обязан оставаться пустым до получения официального источника"


def test_profile_absent_blocks_install():
    status = blueprint.check("dle20")
    assert not status.ready
    with pytest.raises(BlockedInput) as exc:
        blueprint.require_ready("dle20")
    assert exc.value.status == "BLOCKED_INPUT"
    assert "документац" in exc.value.required_input.lower()


def test_incomplete_profile_lists_every_missing_field(tmp_path, monkeypatch):
    profile = PATHS.blueprints / "dle20" / "profiles" / "paths.yaml"
    profile.write_text(yaml.safe_dump({"schema_version": 1, "dle_version": "20.0", "source_required": False,
                                       "source_reference": "", "runtime": {"php": {}, "database": {}},
                                       "writable_paths": [], "immutable_paths": [], "shared_paths": [],
                                       "installer_entrypoints": [], "public_deny_paths": [],
                                       "permissions": {"writable_mode": "0750"}}), encoding="utf-8")
    try:
        status = blueprint.check("dle20")
        assert not status.ready
        assert any("writable_paths" in p for p in status.problems)
        assert any("source_reference" in p for p in status.problems)
        assert any("php.min_version" in p for p in status.problems)
    finally:
        profile.unlink()


def test_world_writable_mode_is_rejected():
    profile = PATHS.blueprints / "dle20" / "profiles" / "paths.yaml"
    profile.write_text(yaml.safe_dump({"schema_version": 1, "source_required": False, "source_reference": "doc",
                                       "runtime": {"php": {"min_version": "8.2"}, "database": {"engine": "mysql"}},
                                       "writable_paths": ["/uploads"], "immutable_paths": ["/engine"],
                                       "shared_paths": ["/uploads"], "installer_entrypoints": ["/install.php"],
                                       "public_deny_paths": ["/engine/data"],
                                       "permissions": {"writable_mode": "0777"}}), encoding="utf-8")
    try:
        status = blueprint.check("dle20")
        assert any("777" in p for p in status.problems)
    finally:
        profile.unlink()


def test_cron_manifest_template_is_declarative():
    data = yaml.safe_load((PATHS.blueprints / "dle20" / "cron" / "jobs.template.yaml").read_text(encoding="utf-8"))
    assert data["source_required"] is True and data["jobs"] == []


def test_cron_jobs_require_lock_timeout_and_log():
    path = PATHS.blueprints / "dle20" / "cron" / "jobs.yaml"
    path.write_text(yaml.safe_dump({"schema_version": 1, "jobs": [{"id": "a", "schedule": "* * * * *", "command": "php x"}]}), encoding="utf-8")
    try:
        with pytest.raises(BlockedInput):
            blueprint.cron_jobs("dle20")
    finally:
        path.unlink()


def test_duplicate_cron_ids_are_rejected():
    path = PATHS.blueprints / "dle20" / "cron" / "jobs.yaml"
    job = {"id": "a", "schedule": "* * * * *", "command": "php x", "lock": "/l", "timeout_seconds": 60, "log": "/log"}
    path.write_text(yaml.safe_dump({"schema_version": 1, "jobs": [job, dict(job)]}), encoding="utf-8")
    try:
        with pytest.raises(BlockedInput):
            blueprint.cron_jobs("dle20")
    finally:
        path.unlink()
