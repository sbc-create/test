"""REQ-DRYRUN: plan и dry-run не меняют инфраструктуру."""
import json

from factory import build as build_mod
from factory import inventory, pipeline
from factory.targets import build_target


def _target_state_snapshot(root):
    if not root.exists():
        return set()
    return {str(p.relative_to(root)) for p in root.rglob("*")}


def test_plan_does_not_mutate(pilot_package):
    conf = inventory.target(pilot_package["target_ref"])
    target = build_target(conf, pilot_package)
    before = _target_state_snapshot(target.root)
    plan = target.plan(build_mod.latest_build("pilot-local"), "any-build-id")
    after = _target_state_snapshot(target.root)
    assert before == after, "plan обязан быть чистой функцией от состояния"
    assert plan.mutations > 0, "план обязан честно перечислять будущие мутации"


def test_dry_run_deploy_applies_nothing(pilot_package):
    conf = inventory.target(pilot_package["target_ref"])
    target = build_target(conf, pilot_package)
    build_dir = build_mod.latest_build("pilot-local")
    build_id = build_dir.name
    before = _target_state_snapshot(target.root)
    result = target.deploy(build_dir, build_id, dry_run=True)
    after = _target_state_snapshot(target.root)
    assert before == after
    assert result.mutations == []


def test_pipeline_dry_run_records_zero_mutations(temp_site):
    site = temp_site()
    outcome = pipeline.run_job(site, dry_run=True, skip_browser=True)
    assert outcome.status == "BUILT"
    data = json.loads(outcome.result_path.read_text(encoding="utf-8"))
    assert data["mutations"] == []
    assert any(step["id"] == "deploy" and step["status"] == "skipped" for step in data["steps"])
