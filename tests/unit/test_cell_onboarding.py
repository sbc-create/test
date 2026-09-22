"""Заведение сайта: продолжение с места сбоя, честный частичный результат.

Доказывает: REQ-CELL-ONBOARD, REQ-CELL-DNS.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.cell import onboarding, templates
from factory.cell.onboarding import Order, StageBlocked


def _order(**kw) -> Order:
    base = {"order_id": "o-1", "site_id": "pilot-cell", "domain": "pilot-cell.test",
                "family": "lords", "content_profile": "video-showcase",
                "deploy_target": "local-disposable"}
    base.update(kw)
    return Order(**base)


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    d = tmp_path / "onboarding"
    d.mkdir()
    return d


@pytest.fixture()
def pool(tmp_path: Path) -> Path:
    path = tmp_path / "pool.json"
    path.write_text(json.dumps({
        "schema_version": "1.0",
        "templates": [{"template_id": f"lords-{i}", "family": "lords",
                       "source": f"b/{i}.yaml", "status": "free", "assignment": None}
                      for i in range(3)],
    }), encoding="utf-8")
    return path


def test_missing_input_is_blocked_not_defaulted(root: Path):
    with pytest.raises(StageBlocked, match="пустое поле"):
        onboarding.start(_order(family=""), root=root)


def test_family_is_not_guessed_from_the_domain_name(root: Path):
    """Ни семейство, ни профиль содержимого из имени домена не выводятся."""
    with pytest.raises(StageBlocked):
        onboarding.start(_order(domain="animedia.space", family="",
                                content_profile=""), root=root)


def test_progress_resumes_from_the_failed_stage(root: Path):
    calls: list[str] = []

    def ok(name):
        def runner(order):
            calls.append(name)
            return {"stage": name}
        return runner

    def broken(order):
        calls.append("repo_ready")
        raise RuntimeError("диск кончился")

    steps = {"domain_validated": ok("domain_validated"),
             "template_reserved": ok("template_reserved"),
             "repo_ready": broken}
    first = onboarding.run(_order(), root=root, steps=steps)
    assert first.by_name["domain_validated"].status == "done"
    assert first.by_name["repo_ready"].status == "failed"
    assert first.complete is False

    calls.clear()
    steps["repo_ready"] = ok("repo_ready")
    second = onboarding.run(_order(), root=root, steps=steps)
    # Пройденные этапы не переигрываются.
    assert calls == ["repo_ready"]
    assert second.by_name["repo_ready"].status == "done"


def test_partial_failure_is_never_reported_as_ready(root: Path):
    def broken(order):
        raise RuntimeError("не вышло")

    progress = onboarding.run(_order(), root=root,
                              steps={"domain_validated": broken})
    summary = progress.summary()
    assert summary["complete"] is False
    assert "domain_validated" in summary["failed"]
    assert summary["next_stage"] == "domain_validated"


def test_a_stage_without_a_runner_is_not_run_rather_than_passed(root: Path):
    progress = onboarding.run(
        _order(), root=root,
        steps={"domain_validated": lambda o: {"ok": True}})
    assert progress.by_name["domain_validated"].status == "done"
    assert progress.by_name["template_reserved"].status == "not_run"
    assert progress.complete is False


def test_blocked_stage_records_the_reason(root: Path):
    def blocked(order):
        raise StageBlocked("сервер не передан")

    progress = onboarding.run(_order(), root=root, steps={"domain_validated": blocked})
    stage = progress.by_name["domain_validated"]
    assert stage.status == "blocked"
    assert "сервер не передан" in stage.detail["reason"]


def test_dry_run_reaches_nothing_and_spends_nothing(root: Path, pool: Path):
    before = templates.free_templates(pool)
    progress = onboarding.run(
        _order(), root=root, dry_run=True,
        steps={"template_reserved":
               lambda o: onboarding.reserve_template_step(o, pool_path=pool)})
    assert templates.free_templates(pool) == before
    assert progress.complete is False


def test_repeating_the_order_spends_no_second_template(root: Path, pool: Path):
    steps = {"domain_validated": lambda o: {"ok": True},
             "template_reserved":
                 lambda o: onboarding.reserve_template_step(o, pool_path=pool)}
    first = onboarding.run(_order(), root=root, steps=steps)
    free_after = templates.free_templates(pool)
    assigned = first.by_name["template_reserved"].detail["template_id"]

    second = onboarding.run(_order(), root=root, steps=steps)
    assert templates.free_templates(pool) == free_after
    assert second.by_name["template_reserved"].detail["template_id"] == assigned


def test_two_orders_never_share_a_template(root: Path, pool: Path):
    steps = {"domain_validated": lambda o: {"ok": True},
             "template_reserved":
             lambda o: onboarding.reserve_template_step(o, pool_path=pool)}
    a = onboarding.run(_order(order_id="o-a", site_id="site-a", domain="a.test"),
                       root=root, steps=steps)
    b = onboarding.run(_order(order_id="o-b", site_id="site-b", domain="b.test"),
                       root=root, steps=steps)
    assert (a.by_name["template_reserved"].detail["template_id"]
            != b.by_name["template_reserved"].detail["template_id"])


def test_domain_check_separates_ns_from_address_and_https():
    order = _order()
    # NS есть, адрес ведёт не туда: для выката это не готовность.
    check = onboarding.validate_domain(order, probe=lambda d: {
        "ns": ["ns1.example.test"], "address_matches_target": False,
        "https_ready": False})
    assert check.ns_present is True
    assert check.ready_for_cutover is False

    ready = onboarding.validate_domain(order, probe=lambda d: {
        "ns": ["ns1.example.test"], "address_matches_target": True,
        "https_ready": True})
    assert ready.ready_for_cutover is True


def test_domain_check_without_a_probe_says_unmeasured_not_false():
    check = onboarding.validate_domain(_order())
    assert check.address_matches_target is None
    assert check.https_ready is None
    assert check.ready_for_cutover is False
    assert "проба DNS не передана" in check.reason


def test_progress_survives_a_restart(root: Path):
    onboarding.run(_order(), root=root,
                   steps={"domain_validated": lambda o: {"ok": True}})
    reloaded = onboarding.start(_order(), root=root)
    assert reloaded.by_name["domain_validated"].status == "done"
    assert reloaded.next_stage == "template_reserved"
