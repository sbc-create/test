"""REQ-STATES, REQ-DOD: Каждый отказной статус конвейера вызывается фактически, а не упоминается.

Мутационная проверка ревьюера показала: ворота QA после выката, авто-откат и
обработку гонки за блокировку можно было удалить, не уронив ни одного теста.
"""
import json
import multiprocessing as mp
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from factory import inventory, pipeline  # noqa: E402
from factory import verify as verify_mod  # noqa: E402
from factory.errors import DeployFailed  # noqa: E402
from factory.seo.model import Report  # noqa: E402
from factory.verify import Check  # noqa: E402


def _checks(failing_id: str, severity: str = "critical") -> tuple[list[Check], list[Report]]:
    report = Report(failing_id)
    report.counts = {"status": "ok"}
    checks = [
        Check("seo-lint", "cmd", 0, True, "artifacts/qa/x/seo-lint.json", {"status": "ok"}),
        Check(failing_id, "cmd", 1, False, f"artifacts/qa/x/{failing_id}.json", {"status": "ok"}, severity),
    ]
    return checks, [report]


@pytest.mark.slow
def test_failed_quality_gate_gives_qa_failed(temp_site, monkeypatch):
    site = temp_site()
    monkeypatch.setattr(verify_mod, "verify", lambda *a, **k: _checks("security-smoke"))
    outcome = pipeline.run_job(site, skip_browser=True)
    assert outcome.status == "QA_FAILED"
    data = json.loads(outcome.result_path.read_text(encoding="utf-8"))
    assert data["acceptance_complete"] is False
    assert any(b["field"] == "security-smoke" for b in data["blockers"])


@pytest.mark.slow
def test_failed_seo_gate_gives_blocked_seo(temp_site, monkeypatch):
    site = temp_site()
    monkeypatch.setattr(verify_mod, "verify", lambda *a, **k: _checks("seo-crawl"))
    outcome = pipeline.run_job(site, skip_browser=True)
    assert outcome.status == "BLOCKED_SEO"


@pytest.mark.slow
def test_unverified_restore_gives_deploy_failed(temp_site, monkeypatch):
    """Наличие архива не доказывает восстановимость: DONE при этом невозможен."""
    site = temp_site()
    from factory.targets.local_disposable import LocalDisposableTarget
    monkeypatch.setattr(LocalDisposableTarget, "restore", lambda self, ref, dest: False)
    outcome = pipeline.run_job(site, skip_browser=True)
    assert outcome.status == "DEPLOY_FAILED"
    data = json.loads(outcome.result_path.read_text(encoding="utf-8"))
    assert data["backup"]["restore_verified"] is False
    assert any(c["id"] == "backup-restore" and not c["passed"] for c in data["checks"])


@pytest.mark.slow
def test_failed_production_smoke_triggers_rollback(temp_site, pilot_package, monkeypatch):
    """Провал production smoke обязан привести к откату, а не к DONE."""
    from factory.targets.local_disposable import LocalDisposableTarget
    monkeypatch.setattr(inventory, "target", lambda ref: {
        "ref": "prod-test", "adapter": "local_disposable", "environments": ["production"],
        "root": "var/targets/test-prod-smoke", "bind_host": "127.0.0.1", "port_range": [8096, 8099],
        "production_capable": True})
    monkeypatch.setattr(inventory, "all_licenses", lambda: [
        {"ref": "lic-test", "covered_domain": "example.tld", "covers_subdomains": True, "version": "20.0"}])
    monkeypatch.setattr(verify_mod, "verify", lambda *a, **k: ([Check("seo-lint", "cmd", 0, True, "a.json", {"status": "ok"})], [Report("seo-lint")]))
    monkeypatch.setattr(LocalDisposableTarget, "health", lambda self: (False, "смоделированный провал smoke"))
    rolled = {"called": False}
    original_rollback = LocalDisposableTarget.rollback

    def spy(self):
        rolled["called"] = True
        try:
            return original_rollback(self)
        except DeployFailed:
            from factory.targets.base import DeployResult, now
            return DeployResult(self.site_id, self.environment, "", "previous", None, self.base_url(),
                                steps=[{"id": "switch_current", "status": "ok", "started_at": now(),
                                        "finished_at": now(), "exit_code": 0, "detail": "откат", "mutation": True}],
                                mutations=[{"target": str(self.root), "kind": "symlink", "detail": "откат", "at": now()}])
    monkeypatch.setattr(LocalDisposableTarget, "rollback", spy)

    def mutate(package):
        package.update({"environment": "production", "production_authorized": True, "fixture": False,
                        "domain": "example.tld", "canonical_url": "https://example.tld/",
                        "dle_license_ref": "lic-test", "dle_distribution_ref": "d", "target_ref": "prod-test",
                        "dle_distribution_sha256": "a" * 64, "ssh_host_ref": "h",
                        "authorized_by": "op", "authorized_at": "2026-08-21T00:00:00Z"})
        package["content_source"].update({"kind": "vk", "provenance": "лицензионная выгрузка",
                                          "rights_manifest_ref": "content/rights-manifest.yaml",
                                          "allowed_fields": ["title"], "rights_confirmed": True})
        package["vk_video"]["adapter"] = "disabled"
        package["vk_video"]["enabled"] = False
    site = temp_site(mutate)
    outcome = pipeline.run_job(site, skip_browser=True, allow_production=True)
    assert outcome.status == "ROLLED_BACK"
    assert rolled["called"], "auto_rollback_on_smoke_failure обязан вызвать откат"
    data = json.loads(outcome.result_path.read_text(encoding="utf-8"))
    assert any("Выполнен откат" in note for note in data["notes"])


def _hold_lock(site_id, ready, release):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from factory.locks import site_lock
    with site_lock(site_id, "staging"):
        ready.set()
        release.wait(30)


@pytest.mark.slow
def test_lock_contention_gives_quarantined_and_requeue(temp_site):
    site = temp_site()
    ctx = mp.get_context("fork")
    ready, release = ctx.Event(), ctx.Event()
    holder = ctx.Process(target=_hold_lock, args=(site, ready, release))
    holder.start()
    try:
        assert ready.wait(15)
        outcome = pipeline.run_job(site, skip_browser=True)
        assert outcome.status == "QUARANTINED"
        assert outcome.requeue is True, "гонка за блокировку возвращает задание в очередь"
        data = json.loads(outcome.result_path.read_text(encoding="utf-8"))
        assert data["mutations"] == []
    finally:
        release.set()
        holder.join(15)


@pytest.mark.slow
def test_interrupted_job_is_quarantined_not_crashing(temp_site):
    """Прерванное задание не должно ронять worker недопустимым переходом."""
    from factory.state import JobState
    site = temp_site()
    job = JobState.load_or_create(f"{site}-interrupted", site, "staging")
    job.transition("VALIDATING").transition("READY").transition("BUILDING").transition("BUILT")
    outcome = pipeline.run_job(site, job_id=job.job_id, skip_browser=True)
    assert outcome.status == "QUARANTINED"
    assert any("промежуточном состоянии" in b["reason"] for b in outcome.blockers)
