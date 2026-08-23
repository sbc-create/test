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
READ_ONLY_TOOLS = frozenset({"Read", "Glob", "Grep", "NotebookRead", "TodoWrite", "Task"})

# Tools that write inside the working tree. Safe under UNATTENDED_SAFE because
# the session works in its own branch and cannot push without authorization.
BRANCH_LOCAL_WRITE_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})

DECISION_MAP = {
    Decision.ALLOW: "allow",
    Decision.REQUIRE_APPROVAL: "ask",
    Decision.BLOCK: "deny",
}


def decide(payload: dict) -> dict:
    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    if tool in READ_ONLY_TOOLS:
        return _out("allow", f"{tool}: read-only инструмент")

    if tool in BRANCH_LOCAL_WRITE_TOOLS:
        path = str(tool_input.get("file_path", ""))
        if "/.claude/hooks/" in path or path.endswith("settings.json"):
            return _out("ask", "изменение самой защитной машинерии требует подтверждения")
        return _out("allow", f"{tool}: запись в пределах рабочей ветки")

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
            return _out("ask", verdict.reason)
        if verdict.decision is Decision.ALLOW:
            if stop:
                return _out("ask", f"обязательное подтверждение: {stop}")
            return _out("allow", verdict.reason)

        profile = unattended.evaluate(command)
        if profile.decision == unattended.ALLOW:
            return _out("allow", f"{unattended.PROFILE}: {profile.reason}")
        return _out("deny", f"{verdict.reason}; профиль: {profile.reason}")

    # Unknown tool: fail closed to a human decision.
    return _out("ask", f"неизвестный инструмент {tool!r} — решение передано человеку")


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
                _out("ask", "не удалось разобрать payload — fail closed"), ensure_ascii=False
            )
        )
        return 0
    print(json.dumps(decide(payload), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
