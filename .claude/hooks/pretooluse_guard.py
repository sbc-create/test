#!/usr/bin/env python3
"""
PreToolUse hook. Fail-closed enforcement для UNATTENDED_SAFE.

Контракт: JSON на stdin -> JSON на stdout с hookSpecificOutput.permissionDecision.
Любая внутренняя ошибка => deny, а не молчаливый пропуск.
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HOOK_DIR))

AUDIT_PATH = Path(os.environ.get("SEO_STATE_DIR", ".seo-state")) / "permission-audit.jsonl"


def _emit(decision_dict: dict, exit_code: int = 0) -> None:
    sys.stdout.write(json.dumps(decision_dict, ensure_ascii=False))
    sys.stdout.flush()
    sys.exit(exit_code)


def _audit(record: dict) -> None:
    try:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with AUDIT_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass  # audit не должен ломать enforcement


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        _emit({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "[fail_closed] Не удалось прочитать hook input.",
            }
        })
        return

    try:
        from policy_engine import evaluate

        tool_name = payload.get("tool_name", "")
        tool_input = payload.get("tool_input", {}) or {}
        repo_root = payload.get("cwd") or os.getcwd()

        decision = evaluate(tool_name, tool_input, repo_root)
        _audit({
            "tool": tool_name,
            "decision": decision.permission,
            "rule": decision.rule,
            "reason": decision.reason,
        })
        _emit(decision.as_hook_output(tool_name))
    except Exception:
        _audit({"decision": "deny", "rule": "hook_exception", "trace": traceback.format_exc()[-500:]})
        _emit({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "[fail_closed] Ошибка policy engine — операция отклонена.",
            }
        })


if __name__ == "__main__":
    main()
