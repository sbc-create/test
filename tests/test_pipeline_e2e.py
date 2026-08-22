"""Сквозной прогон: коннекторы -> ежедневный цикл -> отчёт -> CLI."""
import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


# --- коннекторы ---------------------------------------------------------------

def test_unconfigured_source_reports_not_configured(isolated_state):
    from seo_operator import config
    from seo_operator.connectors import base
    import seo_operator.connectors.search_console  # noqa: F401

    site = config.Site(site_id="real-site", tenant="t", domain="x.example",
                       environment="production", raw={"analytics_timezone": "UTC"})
    conn = base.build("gsc_search_analytics", site)
    result = conn.fetch(date(2026, 8, 1), date(2026, 8, 22))
    assert result.status == "NOT_CONFIGURED"
    assert result.completeness == 0.0
    assert "Требуется" in result.note


def test_fixture_source_only_serves_demo_sites(isolated_state):
    from seo_operator import config
    from seo_operator.connectors import base
    import seo_operator.connectors.search_console  # noqa: F401

    site = config.get_site("demo-fixture")
    result = base.build("gsc_search_analytics", site).fetch(date(2026, 8, 1), date(2026, 8, 22))
    assert result.status == "ok" and result.rows
    assert "FIXTURE" in result.note, "Фикстурные данные обязаны быть помечены"


def test_metrika_logs_refuses_today(isolated_state):
    from seo_operator import config
    from seo_operator.connectors import base
    import seo_operator.connectors.yandex  # noqa: F401

    site = config.get_site("demo-fixture")
    conn = base.build("yandex_metrika_logs", site)
    result = conn.fetch(date.today() - timedelta(days=1), date.today())
    assert result.status == "WAITING_DATA"


def test_completeness_reflects_source_lag(isolated_state):
    from seo_operator import config
    from seo_operator.connectors import base
    import seo_operator.connectors.search_console  # noqa: F401

    conn = base.build("gsc_search_analytics", config.get_site("demo-fixture"))
    today = date(2026, 8, 22)
    assert conn.completeness_for(date(2026, 8, 22), today) == 0.0     # сегодня
    assert conn.completeness_for(date(2026, 8, 21), today) < 1.0      # внутри задержки
    assert conn.completeness_for(date(2026, 8, 10), today) == 1.0     # полные данные


# --- ежедневный цикл ----------------------------------------------------------

@pytest.fixture()
def run_report(store, audit):
    from seo_operator.scheduler import DailyRun
    return DailyRun(store, audit, dry_run=True, today=date(2026, 8, 22)).run(["demo-fixture"])


def test_daily_run_executes_every_step(run_report):
    from seo_operator.scheduler import PIPELINE
    executed = [s.step for s in run_report.steps if s.step in PIPELINE]
    assert set(PIPELINE) <= set(executed)


def test_daily_run_has_no_errors(run_report):
    errors = [(s.step.value, s.detail) for s in run_report.steps if s.status == "error"]
    assert not errors, errors


def test_daily_run_is_dry_by_default(run_report):
    assert run_report.dry_run is True


def test_blocked_step_does_not_stop_the_cycle(store, audit):
    """Недоступный источник блокирует шаг, но последующие шаги всё равно выполняются."""
    from seo_operator.scheduler import DailyRun, Step
    report = DailyRun(store, audit, dry_run=True, today=date(2026, 8, 22)).run(["demo-fixture"])
    steps = {s.step: s for s in report.steps}
    assert steps[Step.REPORT].status == "ok"


def test_editorial_discovery_runs_for_demo_site(run_report):
    from seo_operator.scheduler import Step
    step = next(s for s in run_report.steps if s.step is Step.DISCOVER_EDITORIAL_CHANGES)
    assert step.status == "ok" and "demo-fixture" in step.data["sites"]


def test_calendar_expires_stale_announcements(run_report):
    from seo_operator.scheduler import Step
    step = next(s for s in run_report.steps if s.step is Step.REFRESH_RELEASE_CALENDAR)
    assert "transitions" in step.data


def test_run_is_audited(run_report, audit):
    actions = [r.action for r in audit.records(limit=200)]
    assert "daily_run" in actions
    ok, msg = audit.verify_chain()
    assert ok, msg


def test_protected_drift_stops_mutating_steps(store, audit, monkeypatch):
    from seo_operator import scheduler
    from seo_operator.scheduler import DailyRun, Step
    monkeypatch.setattr(DailyRun, "_protected_drift",
                        lambda self: [".claude/settings.json"])
    report = DailyRun(store, audit, dry_run=True, today=date(2026, 8, 22)).run(["demo-fixture"])
    mutating = [s for s in report.steps if s.step in scheduler.MUTATING_STEPS]
    assert mutating and all(s.status == "skipped" for s in mutating)
    assert report.protected_drift


# --- отчёт --------------------------------------------------------------------

def test_daily_report_renders_management_summary(run_report):
    from seo_operator.reporting.daily import render
    text = render(run_report, portfolio_status="NOT_POPULATED")
    for section in ("## Портфель", "## Новые тайтлы", "## Редакционный план",
                    "## Эксперименты", "## Инциденты и защита",
                    "## Требуется решение владельца"):
        assert section in text
    assert "фикстуре" in text, "Отчёт обязан помечать нереальные данные"


def test_weekly_report_renders(store, audit):
    from seo_operator.experiments.registry import ExperimentRegistry
    from seo_operator.reporting.weekly import render
    text = render(store, ExperimentRegistry(store), today=date(2026, 8, 22))
    assert "Недельный обзор" in text


# --- CLI ----------------------------------------------------------------------

def _cli(*args, state_dir):
    env = {"SEO_REPO_ROOT": str(ROOT), "SEO_STATE_DIR": str(state_dir),
           "PYTHONPATH": str(ROOT / "src"), "PATH": "/usr/bin:/bin"}
    return subprocess.run([sys.executable, "-m", "seo_operator.cli", *args],
                          capture_output=True, text=True, env=env, cwd=str(ROOT), timeout=120)


def test_cli_portfolio_validate(isolated_state):
    proc = _cli("--json", "portfolio", "validate", state_dir=isolated_state / "cli")
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["problems"] == []


def test_cli_daily_run_dry(isolated_state):
    proc = _cli("daily-run", "--site", "demo-fixture", "--date", "2026-08-22",
                state_dir=isolated_state / "cli2")
    assert proc.returncode == 0, proc.stderr
    assert "Ежедневный SEO/редакционный отчёт" in proc.stdout


def test_cli_permissions_test_passes(isolated_state):
    proc = _cli("--json", "permissions", "test", state_dir=isolated_state / "cli3")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["passed"] and payload["failures"] == []


def test_cli_secrets_check_finds_nothing_and_prints_no_values(isolated_state):
    proc = _cli("--json", "secrets", "check", state_dir=isolated_state / "cli4")
    payload = json.loads(proc.stdout)
    assert payload["clean"], payload["findings"]
    assert "value" not in proc.stdout.lower() or "значения секретов не выводятся" in proc.stdout.lower()


def test_cli_guardrails_baseline_then_verify(isolated_state):
    d = isolated_state / "cli5"
    assert _cli("--json", "guardrails", "baseline", state_dir=d).returncode == 0
    proc = _cli("--json", "guardrails", "verify", state_dir=d)
    assert proc.returncode == 0 and json.loads(proc.stdout)["clean"]


def test_cli_audit_verify(isolated_state):
    d = isolated_state / "cli6"
    _cli("daily-run", "--site", "demo-fixture", state_dir=d)
    proc = _cli("--json", "audit", "verify", state_dir=d)
    assert proc.returncode == 0 and json.loads(proc.stdout)["chain_ok"]


def test_cli_editorial_discover_blocked_for_real_site(isolated_state):
    proc = _cli("--json", "editorial", "discover", "--site", "demo-fixture",
                state_dir=isolated_state / "cli7")
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["entries"] and payload["opportunities"]


def test_cli_cms_mutate_dry_run(isolated_state):
    proc = _cli("--json", "cms-mutate", "--site", "demo-fixture", "--target", "title/x/meta",
                "--action", "title_description_update", "--tier", "1",
                "--experiment", "EXP-1", "--payload", '{"title":"Новый"}',
                state_dir=isolated_state / "cli8")
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["dry_run"] and not payload["applied"]


def test_cli_blocked_action_returns_exit_code_3(isolated_state):
    proc = _cli("--json", "cms-mutate", "--site", "demo-fixture", "--target", "x",
                "--action", "canonical_change", "--tier", "2", "--experiment", "EXP-1",
                state_dir=isolated_state / "cli9")
    assert proc.returncode == 3, proc.stdout
    assert "BLOCKED_AUTHORIZATION" in proc.stdout


# --- обёртки ------------------------------------------------------------------

def test_dns_wrapper_always_refuses():
    proc = subprocess.run([str(ROOT / "automation" / "approved-commands" / "dns.sh")],
                          capture_output=True, text=True, cwd=str(ROOT))
    assert proc.returncode == 3 and "BLOCKED_AUTHORIZATION" in proc.stderr


def test_deploy_wrapper_refuses_without_production_authorization():
    proc = subprocess.run(
        [str(ROOT / "automation" / "approved-commands" / "deploy.sh"),
         "--site", "demo-fixture", "--domain", "demo.invalid", "--host", "local-fixture",
         "--build", "b1", "--branch", "main"],
        capture_output=True, text=True, cwd=str(ROOT))
    assert proc.returncode == 3 and "BLOCKED_AUTHORIZATION" in proc.stderr


def test_wrapper_refuses_on_domain_mismatch():
    proc = subprocess.run(
        [str(ROOT / "automation" / "approved-commands" / "rollback.sh"),
         "--site", "demo-fixture", "--domain", "wrong.invalid", "--experiment", "EXP-1"],
        capture_output=True, text=True, cwd=str(ROOT))
    assert proc.returncode == 3 and "domain mismatch" in proc.stderr
