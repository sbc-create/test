#!/usr/bin/env python3
"""PreToolUse hook для Bash. Контракт stdin/stdout — по SRC-CC-HOOKS."""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guard_rules as rules  # noqa: E402


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        # Не разбираем ввод — не высказываемся, обычные permission rules продолжают действовать.
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    decision = rules.evaluate_bash(command)
    if decision.decision != rules.DENY:
        return 0
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"[factory-guard {decision.rule_id}] {decision.reason}",
            }
        },
        sys.stdout,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
