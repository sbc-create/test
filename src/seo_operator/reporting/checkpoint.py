"""
Финальный отчёт исполнителя (ТЗ §18) и проверка критериев приёмки (ТЗ §17).

Отчёт собирается из ФАКТИЧЕСКИХ проверок, а не заполняется руками. Поле,
которое нечем подтвердить, получает значение из справочника статусов —
`pending`, `NOT_MEASURED`, `INCONCLUSIVE`, — но никогда `pass` по умолчанию.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable, Sequence

from ..secrets import assert_no_secret
from ..statuses import Status

# Порядок и имена полей зафиксированы ТЗ §18 — менять нельзя.
FIELD_ORDER = (
    "SEO_OPERATOR_CODE_READY", "LIVE_HOST_VERIFICATION", "PORTFOLIO_SITES_TOTAL",
    "PORTFOLIO_SITES_MEASURED", "METRIKA_ACCESS", "WEBMASTER_ACCESS",
    "BASELINE_ORGANIC_DAILY_UNIQUE", "TARGET_GAP", "REQUIRED_NEW_SITES_RANGE",
    "DAILY_CYCLE", "WEEKLY_REPORT", "ACTION_LEDGER", "EXPERIMENT_ENGINE",
    "RESTORE_DRILL", "TESTS", "SECRET_SCAN", "COMMIT", "PR", "BLOCKERS",
    "NEXT_SAFE_ACTION",
)


@dataclass
class AcceptanceCheck:
    """Один критерий приёмки первой рабочей версии (ТЗ §17)."""

    number: int
    description: str
    passed: bool
    evidence: str
    blocker: str = ""


# Тринадцать критериев ТЗ §17.
ACCEPTANCE_CRITERIA = (
    (1, "Обнаружить все зарегистрированные сайты и показать неполный инвентарь"),
    (2, "Проверить доступ к Метрике и Вебмастеру, не раскрывая токен"),
    (3, "Собрать минимум один полный день данных для пилотных сайтов"),
    (4, "Показать трафик, запросы, позиции, CTR, индексирование и диагностику"),
    (5, "Сопоставить данные с журналом действий"),
    (6, "Создать измеримую задачу с baseline и датой оценки"),
    (7, "Подготовить изменение, проверить на staging и сформировать evidence"),
    (8, "После разрешённой публикации проверить фактический production URL"),
    (9, "Сформировать ежедневный и недельный отчёт"),
    (10, "Честно показать разрыв до 7 млн и диапазон необходимого числа сайтов"),
    (11, "Пережить повторный запуск без дублей"),
    (12, "Восстановиться из backup на отдельном target"),
    (13, "Пройти CI, secret scan и live-host verification"),
)


@dataclass
class CheckpointReport:
    fields: dict[str, str] = field(default_factory=dict)
    acceptance: list[AcceptanceCheck] = field(default_factory=list)

    @property
    def acceptance_passed(self) -> bool:
        return all(c.passed for c in self.acceptance)

    def render_kv(self) -> str:
        """Формат §18 — ровно те поля и в том порядке."""
        lines = [f"{name}={self.fields.get(name, Status.NOT_MEASURED.value)}"
                 for name in FIELD_ORDER]
        text = "\n".join(lines)
        assert_no_secret(text, "checkpoint_report")
        return text

    def render_acceptance(self) -> str:
        lines = ["| # | Критерий | Статус | Доказательство / блокер |", "|---|---|---|---|"]
        for c in sorted(self.acceptance, key=lambda x: x.number):
            mark = "pass" if c.passed else "FAIL"
            detail = c.evidence if c.passed else (c.blocker or c.evidence)
            lines.append(f"| {c.number} | {c.description} | {mark} | {detail} |")
        return "\n".join(lines)


# Итоговая строка pytest: "550 passed in 5.03s", "3 failed, 547 passed in 6s".
_PYTEST_SUMMARY = re.compile(r"\d+\s+(passed|failed|error|skipped)")


def run_tests(repo_root: Path) -> tuple[bool, str]:
    """Фактический прогон, а не заявление о нём."""
    try:
        proc = subprocess.run(
            ["python3", "-m", "pytest", "tests/", "--no-header", "-p", "no:cacheprovider"],
            cwd=str(repo_root), capture_output=True, text=True, timeout=900,
            env={"PATH": "/usr/bin:/bin:/usr/local/bin", "SEO_REPO_ROOT": str(repo_root),
                 "PYTHONPATH": str(repo_root / "src")})
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"{Status.FAILED.value}: {type(exc).__name__}"

    # Строка прогресса из точек не является итогом — ищем строку со счётчиком.
    lines = [ln.strip() for ln in proc.stdout.strip().splitlines() if ln.strip()]
    summary = next((ln for ln in reversed(lines) if _PYTEST_SUMMARY.search(ln)), None)
    if summary is None:
        summary = f"{Status.NOT_MEASURED.value}: итоговая строка pytest не найдена"
    return proc.returncode == 0, summary[:160]


def build(*, repo_root: Path, portfolio_total: int, portfolio_measured: int,
          metrika_access: str, webmaster_access: str,
          baseline: str, target_gap: str, required_range: str,
          daily_cycle_ok: bool, weekly_report_ok: bool, ledger_ok: bool,
          experiment_engine_ok: bool, restore_drill: str,
          tests_result: str, tests_ok: bool, secret_scan: str, secret_scan_ok: bool,
          commit: str, pr: str, blockers: Sequence[str],
          next_safe_action: str, live_host_verification: str = "pending",
          acceptance: Sequence[AcceptanceCheck] = ()) -> CheckpointReport:
    """
    SEO_OPERATOR_CODE_READY=yes только если код собран, тесты зелёные, secret scan чист
    И все критерии приёмки пройдены. Иначе no — независимо от объёма написанного кода.
    """
    acceptance = list(acceptance)
    all_acceptance_ok = bool(acceptance) and all(c.passed for c in acceptance)
    code_ready = tests_ok and secret_scan_ok and all_acceptance_ok

    fields = {
        "SEO_OPERATOR_CODE_READY": "yes" if code_ready else "no",
        "LIVE_HOST_VERIFICATION": live_host_verification,
        "PORTFOLIO_SITES_TOTAL": str(portfolio_total),
        "PORTFOLIO_SITES_MEASURED": str(portfolio_measured),
        "METRIKA_ACCESS": metrika_access,
        "WEBMASTER_ACCESS": webmaster_access,
        "BASELINE_ORGANIC_DAILY_UNIQUE": baseline,
        "TARGET_GAP": target_gap,
        "REQUIRED_NEW_SITES_RANGE": required_range,
        "DAILY_CYCLE": "pass" if daily_cycle_ok else "fail",
        "WEEKLY_REPORT": "pass" if weekly_report_ok else "fail",
        "ACTION_LEDGER": "pass" if ledger_ok else "fail",
        "EXPERIMENT_ENGINE": "pass" if experiment_engine_ok else "fail",
        "RESTORE_DRILL": restore_drill,
        "TESTS": tests_result,
        "SECRET_SCAN": secret_scan,
        "COMMIT": commit,
        "PR": pr,
        "BLOCKERS": "; ".join(blockers) if blockers else "none",
        "NEXT_SAFE_ACTION": next_safe_action,
    }
    return CheckpointReport(fields=fields, acceptance=acceptance)


def evaluate_acceptance(evidence: dict[int, tuple[bool, str, str]]) -> list[AcceptanceCheck]:
    """
    evidence: номер критерия -> (пройден, доказательство, блокер).
    Критерий без записи считается НЕ пройденным: молчание не является успехом.
    """
    out = []
    for number, description in ACCEPTANCE_CRITERIA:
        passed, ev, blocker = evidence.get(
            number, (False, "проверка не выполнялась", "нет доказательства"))
        out.append(AcceptanceCheck(number=number, description=description,
                                   passed=passed, evidence=ev, blocker=blocker))
    return out
