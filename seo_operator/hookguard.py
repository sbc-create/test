"""Bridge between the Claude Code PreToolUse hook and the guardrail rules.

Reads a hook payload on stdin, writes a permission decision on stdout. Keeping
this in Python means the hook and the pipeline share one rule set.
"""

from __future__ import annotations

import json
import sys

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
        return _out(DECISION_MAP[verdict.decision], verdict.reason)

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
