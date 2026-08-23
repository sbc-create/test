"""Bridge between the Claude Code PreToolUse hook and the guardrail rules.

Reads a hook payload on stdin, writes a permission decision on stdout. Keeping
this in Python means the hook and the pipeline share one rule set.
"""

from __future__ import annotations

import json
import sys

from seo_operator import unattended
from seo_operator.guardrails import ActionContext, Decision, classify

# Tools that only read. They are safe regardless of arguments.
READ_ONLY_TOOLS = frozenset(
    {"Read", "Glob", "Grep", "NotebookRead", "TodoWrite", "Task", "ToolSearch"}
)

# Бухгалтерия самого агента: список задач, планы, отчёты о находках. Эти
# инструменты не касаются файлов, сети и внешних систем — они меняют только
# состояние сессии. Под fail-closed их пришлось назвать явно: иначе
# UNATTENDED_NO_ASK закрывает собственный учёт работы и агент теряет
# возможность вести список задач.
SESSION_BOOKKEEPING_TOOLS = frozenset(
    {
        "TaskCreate",
        "TaskUpdate",
        "TaskList",
        "TaskGet",
        "TaskOutput",
        "TaskStop",
        "EnterPlanMode",
        "ExitPlanMode",
        "ListAgents",
        "ReportFindings",
        "Skill",
        "ScheduleWakeup",
        "AskUserQuestion",
    }
)

# Tools that write inside the working tree. Safe under UNATTENDED_SAFE because
# the session works in its own branch and cannot push without authorization.
BRANCH_LOCAL_WRITE_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})

# GitHub через штатные инструменты. Чтение и работа с pull request — обычная
# часть цикла; всё, что удаляет или переносит владение, остаётся за человеком.
GITHUB_READ_PREFIXES = (
    "mcp__github__get_",
    "mcp__github__list_",
    "mcp__github__search_",
    "mcp__github__issue_read",
    "mcp__github__pull_request_read",
    "mcp__github__actions_get",
    "mcp__github__actions_list",
)
GITHUB_WRITE_TOOLS = frozenset(
    {
        "mcp__github__create_pull_request",
        "mcp__github__update_pull_request",
        "mcp__github__create_branch",
        "mcp__github__add_comment_to_pending_review",
        "mcp__github__pull_request_review_write",
        "mcp__github__add_reply_to_pull_request_comment",
        "mcp__github__resolve_review_thread",
        "mcp__github__unresolve_review_thread",
        "mcp__github__update_pull_request_branch",
        "mcp__github__subscribe_pr_activity",
        "mcp__github__unsubscribe_pr_activity",
    }
)
#: Необратимое или выходящее за репозиторий — только через человека.
GITHUB_BLOCKED_TOOLS = frozenset(
    {
        "mcp__github__delete_file",
        "mcp__github__create_repository",
        "mcp__github__fork_repository",
        "mcp__github__run_secret_scanning",
    }
)

DECISION_MAP = {
    Decision.ALLOW: "allow",
    # UNATTENDED_NO_ASK: нет человека, который ответит на вопрос. То, что
    # раньше уходило на подтверждение, теперь закрывается и попадает в отчёт.
    Decision.REQUIRE_APPROVAL: "deny",
    Decision.BLOCK: "deny",
}


def decide(payload: dict) -> dict:
    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    if tool in READ_ONLY_TOOLS:
        return _out("allow", f"{tool}: read-only инструмент")

    if tool in SESSION_BOOKKEEPING_TOOLS:
        return _out("allow", f"{tool}: учёт работы внутри сессии, без внешних эффектов")

    if tool in BRANCH_LOCAL_WRITE_TOOLS:
        path = str(tool_input.get("file_path", ""))
        if "/.claude/hooks/" in path or path.endswith("settings.json"):
            return _out(
                "deny",
                "изменение самой защитной машинерии запрещено автоматике: "
                "правьте .claude/settings.json и .claude/hooks/* отдельным PR с ревью человека",
            )
        return _out("allow", f"{tool}: запись в пределах рабочей ветки")

    if tool in GITHUB_BLOCKED_TOOLS:
        return _out("deny", f"{tool}: необратимая операция над репозиторием")
    if tool.startswith(GITHUB_READ_PREFIXES):
        return _out("allow", f"{tool}: чтение данных GitHub")
    if tool in GITHUB_WRITE_TOOLS:
        return _out("allow", f"{tool}: работа с pull request в собственной ветке")

    if tool == "Bash":
        command = str(tool_input.get("command", ""))
        environment = payload.get("environment", "sandbox")
        verdict = classify(ActionContext(command=command, environment=environment))

        # Стоп-сигнал профиля сильнее разрешающего правила: `python3 -m factory
        # deploy … --environment production` подходит под «локальный python», но
        # необратимую операцию над production человек подтверждает сам.
        stop = unattended.mandatory_confirmation(command)

        # Явный запрет и требование подтверждения окончательны: профиль
        # UNATTENDED_SAFE не может их отменить, он работает только с командами,
        # которые не подошли ни под одно разрешающее правило (`default-deny`).
        # Раньше такая команда уходила на подтверждение целиком — включая
        # `PYTHONPATH=… python`, `timeout 300 git push origin claude/…` и любой
        # составной вызов, у которого обёртка сдвигала якорь `^`.
        if verdict.decision is Decision.BLOCK and verdict.rule != "default-deny":
            return _out("deny", verdict.reason)
        if verdict.decision is Decision.REQUIRE_APPROVAL:
            return _out("deny", verdict.reason)
        if verdict.decision is Decision.ALLOW:
            if stop:
                return _out("deny", f"остановлено профилем: {stop}")
            return _out("allow", verdict.reason)

        profile = unattended.evaluate(command)
        if profile.decision == unattended.ALLOW:
            return _out("allow", f"{unattended.PROFILE}: {profile.reason}")
        return _out("deny", f"{verdict.reason}; профиль: {profile.reason}")

    # Unknown tool: fail closed. Without a human in the loop the only safe
    # answer to "never seen this" is no.
    return _out("deny", f"неизвестный инструмент {tool!r} — запрещён по умолчанию")


def _out(decision: str, reason: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        print(
            json.dumps(
                _out("deny", "не удалось разобрать payload — fail closed"), ensure_ascii=False
            )
        )
        return 0
    print(json.dumps(decide(payload), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
