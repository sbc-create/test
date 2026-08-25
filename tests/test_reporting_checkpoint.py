"""Ежемесячный отчёт (ТЗ §10) и финальный отчёт исполнителя (ТЗ §18)."""
import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

from seo_operator.forecast import capacity as cap
from seo_operator.metrics import north_star as ns
from seo_operator.reporting import checkpoint, monthly
from seo_operator.secrets import SecretLeak
from seo_operator.statuses import Confidence, Status, measured, not_measured

ROOT = Path(__file__).resolve().parents[1]
AS_OF = "2026-08-20"


def _portfolio(n_sites: int, per_day: int, measurable: bool = True) -> ns.PortfolioNorthStar:
    end = date(2026, 8, 20)
    days = 28 if measurable else 5
    points = {
        f"s{i}": [ns.DayPoint(f"s{i}", end - timedelta(days=d), ns.Engine.YANDEX,
                              per_day, 1.0, "yandex_metrika") for d in range(days)]
        for i in range(n_sites)}
    return ns.portfolio_north_star(points, date(2026, 8, 21))


def _forecast(n_mature: int, per_day: int, current_value: int | None):
    sites = [cap.SiteFact(f"s{i}", "anime", 200, per_day + i * 100, days_to_plateau=150)
             for i in range(n_mature)]
    current = (measured("organic_daily_unique", current_value, "metrika", "28д", AS_OF)
               if current_value is not None
               else not_measured("organic_daily_unique", "счётчики не подключены"))
    return cap.forecast(sites, current, AS_OF)


# ============================ Ежемесячный отчёт ============================

def test_monthly_report_states_the_gap_and_range():
    report = monthly.render(portfolio=_portfolio(10, 10_000),
                            forecast=_forecast(10, 10_000, 100_000),
                            month=date(2026, 8, 1))
    assert "Прогресс к 7 млн" in report
    assert "Разрыв:" in report
    assert "Требуется новых сайтов:" in report
    for label in ("Консервативный", "Базовый", "Оптимистичный"):
        assert label in report


def test_monthly_report_says_insufficient_data_instead_of_inventing_a_number():
    report = monthly.render(portfolio=_portfolio(2, 10_000, measurable=False),
                            forecast=_forecast(2, 10_000, None),
                            month=date(2026, 8, 1))
    assert "данных недостаточно" in report.lower()
    assert "была бы выдумкой" in report


def test_monthly_report_carries_the_dedup_caveat():
    report = monthly.render(portfolio=_portfolio(3, 10_000),
                            forecast=_forecast(10, 10_000, 30_000),
                            month=date(2026, 8, 1))
    assert "уникальной аудиторией портфеля нельзя" in report


def test_monthly_report_shows_engines_separately():
    report = monthly.render(portfolio=_portfolio(3, 10_000),
                            forecast=_forecast(10, 10_000, 30_000),
                            month=date(2026, 8, 1))
    assert "yandex:" in report and "google:" in report and "other:" in report


def test_monthly_report_does_not_hide_losses():
    report = monthly.render(portfolio=_portfolio(10, 10_000),
                            forecast=_forecast(10, 10_000, 100_000),
                            month=date(2026, 8, 1),
                            ledger_summary={"WIN": 3, "LOSS": 5, "ROLLED_BACK": 2, "OPEN": 1})
    assert "LOSS: 5" in report
    assert "Неудачных изменений: 7" in report
    assert "не скрыты" in report


def test_monthly_report_offers_alternative_to_buying_domains():
    report = monthly.render(portfolio=_portfolio(10, 10_000),
                            forecast=_forecast(10, 10_000, 100_000),
                            month=date(2026, 8, 1))
    assert "рост без новых доменов" in report.lower()


def test_monthly_report_reminds_owner_owns_domain_decisions():
    report = monthly.render(portfolio=_portfolio(10, 10_000),
                            forecast=_forecast(10, 10_000, 100_000),
                            month=date(2026, 8, 1))
    assert "не приобретает и не включает их самостоятельно" in report


def test_monthly_report_blocks_on_secret_leak():
    """Отчёт с секретом не публикуется — останавливаемся, а не чистим молча."""
    leaky = "y0_" + "z" * 30
    with pytest.raises(SecretLeak):
        monthly.render(portfolio=_portfolio(10, 10_000),
                       forecast=_forecast(10, 10_000, 100_000),
                       month=date(2026, 8, 1), risks=[f"токен засветился: {leaky}"])


# ============================ Checkpoint ============================

def _acceptance(all_pass: bool):
    evidence = {n: (all_pass, "проверено", "" if all_pass else "не выполнено")
                for n, _ in checkpoint.ACCEPTANCE_CRITERIA}
    return checkpoint.evaluate_acceptance(evidence)


def _build(**kw):
    base = dict(
        repo_root=ROOT, portfolio_total=1, portfolio_measured=0,
        metrika_access=Status.BLOCKED_SECRET.value,
        webmaster_access=Status.BLOCKED_SECRET.value,
        baseline=Status.NOT_MEASURED.value, target_gap=Status.NOT_MEASURED.value,
        required_range=Status.INCONCLUSIVE.value, daily_cycle_ok=True,
        weekly_report_ok=True, ledger_ok=True, experiment_engine_ok=True,
        restore_drill="pending", tests_result="372 passed", tests_ok=True,
        secret_scan="clean", secret_scan_ok=True, commit="abc123", pr="none",
        blockers=[], next_safe_action="подключить Secret Hub",
        acceptance=_acceptance(True))
    base.update(kw)
    return checkpoint.build(**base)


def test_checkpoint_has_exactly_the_spec_fields():
    report = _build()
    rendered = report.render_kv()
    names = [line.split("=", 1)[0] for line in rendered.splitlines()]
    assert names == list(checkpoint.FIELD_ORDER)


def test_code_ready_requires_tests_scan_and_acceptance():
    assert _build().fields["SEO_OPERATOR_CODE_READY"] == "yes"
    assert _build(tests_ok=False).fields["SEO_OPERATOR_CODE_READY"] == "no"
    assert _build(secret_scan_ok=False).fields["SEO_OPERATOR_CODE_READY"] == "no"
    assert _build(acceptance=_acceptance(False)).fields["SEO_OPERATOR_CODE_READY"] == "no"


def test_code_ready_is_no_without_any_acceptance_evidence():
    """Молчание не является успехом."""
    assert _build(acceptance=[]).fields["SEO_OPERATOR_CODE_READY"] == "no"


def test_missing_criterion_counts_as_failed():
    partial = checkpoint.evaluate_acceptance({1: (True, "ок", "")})
    assert len(partial) == len(checkpoint.ACCEPTANCE_CRITERIA)
    assert partial[0].passed
    assert not partial[1].passed
    assert "нет доказательства" in partial[1].blocker


def test_all_thirteen_criteria_present():
    assert len(checkpoint.ACCEPTANCE_CRITERIA) == 13
    assert checkpoint.ACCEPTANCE_CRITERIA[-1][0] == 13


def test_unmeasured_fields_use_status_vocabulary():
    report = _build()
    assert report.fields["BASELINE_ORGANIC_DAILY_UNIQUE"] == "NOT_MEASURED"
    assert report.fields["REQUIRED_NEW_SITES_RANGE"] == "INCONCLUSIVE"
    assert report.fields["LIVE_HOST_VERIFICATION"] == "pending"


def test_checkpoint_render_blocks_on_secret():
    leaky = "gh" + "p_" + "y" * 30
    report = _build(blockers=[f"токен в конфиге: {leaky}"])
    with pytest.raises(SecretLeak):
        report.render_kv()


def test_acceptance_table_marks_failures():
    report = _build(acceptance=_acceptance(False))
    table = report.render_acceptance()
    assert table.count("FAIL") == 13
    assert not report.acceptance_passed


def test_blockers_none_when_empty():
    assert _build().fields["BLOCKERS"] == "none"


# ============================ CLI новых команд ============================

def _cli(*args, state_dir):
    env = {"SEO_REPO_ROOT": str(ROOT), "SEO_STATE_DIR": str(state_dir),
           "PYTHONPATH": str(ROOT / "src"), "PATH": "/usr/bin:/bin:/usr/local/bin"}
    return subprocess.run([sys.executable, "-m", "seo_operator.cli", *args],
                          capture_output=True, text=True, env=env, cwd=str(ROOT), timeout=300)


def test_cli_northstar_reports_with_provenance(isolated_state):
    proc = _cli("--json", "northstar", "--date", "2026-08-22", state_dir=isolated_state / "ns")
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["headline"]["source"] == "yandex_metrika_organic"
    assert payload["dedup_mode"] == "none"
    assert "уникальной аудиторией портфеля нельзя" in payload["caveat"]
    assert set(payload["by_engine"]) == {"yandex", "google", "other"}


def test_cli_forecast_is_honest_about_small_portfolio(isolated_state):
    proc = _cli("--json", "forecast", "--date", "2026-08-22", state_dir=isolated_state / "fc")
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["required_new_sites_range"] == "INCONCLUSIVE"
    assert payload["blockers"]
    assert payload["gap"]["status"] == "READY"


def test_cli_access_audit_blocks_without_secret_hub(isolated_state):
    proc = _cli("--json", "access", "audit", state_dir=isolated_state / "aa")
    assert proc.returncode == 3
    payload = json.loads(proc.stdout)
    assert payload["ready"] == 0
    checks = {m["check"] for m in payload["missing_access"]}
    assert {"metrika", "webmaster"} <= checks


def test_cli_access_audit_never_prints_a_token(isolated_state):
    proc = _cli("access", "audit", state_dir=isolated_state / "aa2")
    assert "secret://metrika/demo-fixture" in proc.stdout
    for marker in ("AQAA", "y0_", "ghp_", "BEGIN"):
        assert marker not in proc.stdout


def test_cli_monthly_report_renders(isolated_state):
    proc = _cli("monthly-report", "--date", "2026-08-22", state_dir=isolated_state / "mr")
    assert proc.returncode == 0, proc.stderr
    assert "Прогресс к 7 млн" in proc.stdout
    assert "Требуется от владельца" in proc.stdout


def test_cli_checkpoint_reports_not_ready_without_live_host(isolated_state):
    # --no-tests: иначе checkpoint запустил бы весь набор тестов внутри теста.
    proc = _cli("--json", "checkpoint", "--no-tests", state_dir=isolated_state / "cp")
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["fields"]["SEO_OPERATOR_CODE_READY"] == "no"
    assert payload["fields"]["LIVE_HOST_VERIFICATION"] == "pending"
    failed = [c for c in payload["acceptance"] if not c["passed"]]
    assert failed, "Без живого хоста часть критериев обязана быть непройденной"


def test_checkpoint_skipped_tests_are_not_reported_as_passing(isolated_state):
    proc = _cli("--json", "checkpoint", "--no-tests", state_dir=isolated_state / "cp2")
    payload = json.loads(proc.stdout)
    assert "NOT_MEASURED" in payload["fields"]["TESTS"]
    assert payload["fields"]["SEO_OPERATOR_CODE_READY"] == "no"
