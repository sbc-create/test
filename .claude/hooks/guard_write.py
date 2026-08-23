#!/usr/bin/env python3
"""PreToolUse hook для Edit/Write/NotebookEdit: защита путей.

Порядок тот же, что у Bash-хука: сначала запреты фабрики, потом профиль
UNATTENDED_SAFE. Правка файла внутри репозитория — обычная работа и не требует
подтверждения; всё, что ведёт наружу, остаётся на усмотрение permission rules.
"""
from __future__ import annotations

import json
import os
import sys

HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HOOK_DIR))
sys.path.insert(0, HOOK_DIR)
import guard_rules as rules  # noqa: E402

try:
    sys.path.insert(0, REPO_ROOT)
    from seo_operator import unattended
except Exception:  # pragma: no cover - профиль необязателен для запретов
    unattended = None


def _emit(decision: str, reason: str) -> None:
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": decision,
                "permissionDecisionReason": reason,
            }
        },
        sys.stdout,
    )


def decide(path: str) -> tuple[str, str]:
    verdict = rules.evaluate_write(path)
    if verdict.decision == rules.DENY:
        return "deny", f"[factory-guard {verdict.rule_id}] {verdict.reason}"
    if unattended is not None and path:
        profile = unattended.evaluate_path(path, REPO_ROOT)
        if profile.decision == unattended.ALLOW:
            return "allow", f"[{unattended.PROFILE}] {profile.reason}"
    return "pass", ""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    tool_input = payload.get("tool_input") or {}
    path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    decision, reason = decide(str(path))
    if decision != "pass":
        _emit(decision, reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
