"""REQ-UNATTENDED: штатный цикл не запрашивает подтверждений.

Профиль UNATTENDED_SAFE работает без человека. Значит, у решения ровно два
исхода: `allow` или `deny`. Третий исход `ask` на неотвечающем терминале — это
не защита, а зависание: работа останавливается, а причина остановки нигде не
записана.

Файл доказывает две вещи сразу, и обе обязательны:

1. Штатный цикл разработки, тестирования, git-работы в собственной ветке,
   GitHub и staging проходит без единого `ask`.
2. Опасные и необратимые операции по-прежнему не проходят — они отвечают `deny`
   немедленно и попадают в журнал отказов.

Ослабление любого из двух списков ломает этот файл.
"""
from __future__ import annotations

import json

import pytest

from seo_operator import hookguard


def _decide(tool: str, **tool_input) -> tuple[str, str]:
    out = hookguard.decide({"tool_name": tool, "tool_input": tool_input})["hookSpecificOutput"]
    return out["permissionDecision"], out["permissionDecisionReason"]


# --------------------------------------------------------------------------
# Штатный цикл: ни одного подтверждения
# --------------------------------------------------------------------------
ROUTINE_COMMANDS = [
    "python3 -m pytest -q",
    "python3 -m pytest tests/unit -q",
    "python3 -m factory validate --site pilot-local",
    "python3 -m factory plan --site pilot-local",
    "python3 -m factory build --site pilot-local",
    "python3 -m factory verify --site pilot-local",
    "python3 -m factory deploy --site pilot-local --environment staging",
    "ruff check factory seo_operator",
    "git status --short",
    "git diff --stat",
    "git add -A",
    "git commit -m 'feat: yandex analytics'",
    "git push origin claude/yandex-analytics-automation",
    "npm ci",
    "pip install -r requirements.txt",
    "ls -la factory/analytics",
    "grep -rn counter factory/analytics",
    "./scripts/verify.sh",
    "./bin/seo-operator probe",
]

ROUTINE_TOOLS = [
    ("Read", {"file_path": "factory/analytics/yandex.py"}),
    ("Grep", {"pattern": "counter_id"}),
    ("Glob", {"pattern": "factory/**/*.py"}),
    ("Write", {"file_path": "factory/analytics/yandex.py"}),
    ("Edit", {"file_path": "tests/unit/test_yandex_analytics.py"}),
    ("mcp__github__create_pull_request", {}),
    ("mcp__github__pull_request_read", {}),
]


@pytest.mark.parametrize("command", ROUTINE_COMMANDS)
def test_routine_commands_never_ask(command: str) -> None:
    decision, reason = _decide("Bash", command=command)
    assert decision != "ask", f"подтверждение в штатном цикле: {command}"
    assert decision == "allow", f"штатная команда запрещена: {command} → {reason}"


@pytest.mark.parametrize("tool,payload", ROUTINE_TOOLS)
def test_routine_tools_never_ask(tool: str, payload: dict) -> None:
    decision, reason = _decide(tool, **payload)
    assert decision != "ask", f"подтверждение в штатном цикле: {tool}"
    assert decision == "allow", f"штатный инструмент запрещён: {tool} → {reason}"


# --------------------------------------------------------------------------
# Опасное остаётся запрещённым — но отвечает сразу, а не спрашивает
# --------------------------------------------------------------------------
DANGEROUS_COMMANDS = [
    "git push --force origin main",
    "git push -f origin claude/x",
    "git push origin main",
    "git push origin --delete claude/x",
    "git reset --hard origin/main",
    "git clean -fdx",
    "git filter-branch --all",
    "dropdb factory_anime",
    "psql -c 'DROP DATABASE factory_anime'",
    "rm -rf /srv",
    "terraform destroy",
    "aws s3 rb s3://site-factory-backups",
    "rm -rf /var/backups/site-factory",
    "aws route53 delete-hosted-zone --id Z1",
    "gh repo delete sbc-create/test",
    "claude --dangerously-skip-permissions",
    "git commit --no-verify -m x",
    "python3 -m factory deploy --site pilot-local --environment production",
]


@pytest.mark.parametrize("command", DANGEROUS_COMMANDS)
def test_dangerous_commands_are_denied_not_asked(command: str) -> None:
    decision, reason = _decide("Bash", command=command)
    assert decision == "deny", f"опасная команда не запрещена: {command} → {decision} {reason}"
    assert reason, "отказ обязан называть причину"


def test_editing_the_guard_itself_is_denied() -> None:
    decision, _ = _decide("Write", file_path="/srv/site-factory/repo/.claude/settings.json")
    assert decision == "deny"
    decision, _ = _decide("Edit", file_path="/srv/site-factory/repo/.claude/hooks/guard_rules.py")
    assert decision == "deny"


def test_unknown_tool_is_denied_not_asked() -> None:
    decision, reason = _decide("SomeToolNobodyDescribed")
    assert decision == "deny"
    assert "default-deny" in reason


def test_unparsable_payload_is_denied_not_asked(monkeypatch, tmp_path, capsys) -> None:
    import io

    monkeypatch.setenv(hookguard.DENIAL_LOG_ENV, str(tmp_path / "denials.jsonl"))
    monkeypatch.setattr("sys.stdin", io.StringIO("{ not json"))
    assert hookguard.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"


# --------------------------------------------------------------------------
# Ни один исход модуля не является подтверждением
# --------------------------------------------------------------------------
def test_module_has_no_ask_outcome() -> None:
    """Строковый `ask` не должен появиться в модуле снова."""
    from pathlib import Path

    source = Path(hookguard.__file__).read_text(encoding="utf-8")
    assert '"ask"' not in source, "в hookguard вернулся исход ask"
    assert "'ask'" not in source


def test_decision_map_has_no_ask() -> None:
    assert "ask" not in set(hookguard.DECISION_MAP.values())


def test_every_denial_is_recorded(monkeypatch, tmp_path) -> None:
    """Раз человека не спрашивают, отчёт обязан показать, что было запрещено."""
    log = tmp_path / "denials.jsonl"
    monkeypatch.setenv(hookguard.DENIAL_LOG_ENV, str(log))
    _decide("Bash", command="git push --force origin main")
    _decide("SomeToolNobodyDescribed")

    lines = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 2, "не каждый отказ попал в журнал"
    for entry in lines:
        assert entry["decision"] == "deny"
        assert entry["reason"]
        assert entry["profile"] == "UNATTENDED_SAFE"


def test_denial_log_is_redacted(monkeypatch, tmp_path) -> None:
    """Журнал отказов не должен сам стать местом, где оседает секрет."""
    from factory.redaction import PLACEHOLDER, forget_secrets, register_secret

    log = tmp_path / "denials.jsonl"
    monkeypatch.setenv(hookguard.DENIAL_LOG_ENV, str(log))
    secret = "y0_AgAAAAAfakefakefakefakefakefake"
    register_secret(secret)
    try:
        hookguard.record_denial("Bash", "проверка", f"curl -H 'Authorization: OAuth {secret}' https://x")
        text = log.read_text(encoding="utf-8")
        assert secret not in text
        assert PLACEHOLDER in text
    finally:
        forget_secrets()


# --------------------------------------------------------------------------
# Выкат: staging проходит сам, production проходит только по выполненным условиям
# --------------------------------------------------------------------------
STAGING_DEPLOYS = [
    # Форма без флага — штатная в tests/run-all.sh: окружение берётся из пакета.
    "python3 -m factory deploy --site pilot-local",
    "python3 -m factory deploy --site pilot-local --environment staging",
    "python3 -m factory rollback --site pilot-local",
    "python3 -m factory deploy --site site-a",
]


@pytest.mark.parametrize("command", STAGING_DEPLOYS)
def test_staging_deploys_need_no_confirmation(command: str) -> None:
    """Стенд пересоздаётся: останавливать его выкат вопросом — останавливать цикл."""
    decision, reason = _decide("Bash", command=command)
    assert decision == "allow", f"{command} → {decision}: {reason}"


UNKNOWN_TARGET_DEPLOYS = [
    # Не знать, куда метит команда, — не то же самое, что знать, что она безопасна.
    "python3 -m factory deploy --site does-not-exist",
    "python3 -m factory deploy",
]


@pytest.mark.parametrize("command", UNKNOWN_TARGET_DEPLOYS)
def test_deploys_with_an_unknown_target_are_denied(command: str) -> None:
    decision, reason = _decide("Bash", command=command)
    assert decision == "deny", f"{command} → {decision}: {reason}"


def test_production_deploy_of_a_fixture_package_is_denied_by_name() -> None:
    decision, reason = _decide(
        "Bash", command="python3 -m factory deploy --site pilot-local --environment production")
    assert decision == "deny"
    assert "fixture" in reason, reason


def test_targets_production_prefers_the_flag_over_the_package() -> None:
    from seo_operator import unattended

    production, why = unattended.targets_production(
        "python3 -m factory deploy --site pilot-local --environment production")
    assert production is True and "флаг" in why

    production, why = unattended.targets_production(
        "python3 -m factory deploy --site pilot-local")
    assert production is False and "environment=staging" in why


# --------------------------------------------------------------------------
# GitHub через штатный CLI
# --------------------------------------------------------------------------
GH_ROUTINE = [
    "gh pr create --base main --head claude/x --title t --body-file /tmp/claude-b.md",
    "gh pr list",
    "gh pr view 12 --json state",
    "gh pr comment 12 --body-file /tmp/claude-c.md",
    "gh pr checks 12",
    "gh issue list",
    "gh run list --limit 5",
    "gh run view 42 --log",
    "gh api repos/sbc-create/test/pulls/12",
    "gh api -X GET repos/sbc-create/test/commits",
    "gh repo view sbc-create/test",
    "gh --version",
]

GH_FORBIDDEN = [
    "gh repo delete sbc-create/test --yes",
    "gh repo transfer sbc-create/test other",
    "gh repo archive sbc-create/test",
    "gh release delete v1 --yes",
    "gh api -X DELETE repos/sbc-create/test/branches/main/protection",
    "gh api --method PUT repos/o/r/branches/main/protection",
    "gh secret set GH_TOKEN",
    "gh auth token",
]


@pytest.mark.parametrize("command", GH_ROUTINE)
def test_routine_github_work_is_autonomous(command: str) -> None:
    decision, reason = _decide("Bash", command=command)
    assert decision == "allow", f"{command} → {decision}: {reason}"


@pytest.mark.parametrize("command", GH_FORBIDDEN)
def test_irreversible_github_operations_are_denied(command: str) -> None:
    decision, reason = _decide("Bash", command=command)
    assert decision == "deny", f"{command} → {decision}: {reason}"
