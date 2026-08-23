#!/usr/bin/env python3
"""PreToolUse hook для Bash. Контракт stdin/stdout — по SRC-CC-HOOKS.

Два слоя, в строгом порядке:

1. `guard_rules` — запреты фабрики. Их вердикт окончателен: `deny` уходит
   наружу как есть и ничем не перекрывается.
2. `unattended` — профиль UNATTENDED_SAFE. Он умеет только повышать команду до
   `allow`, чтобы обычная разработка не останавливалась на подтверждениях.
   Всё, что профиль не опознал, остаётся без ответа: решают обычные permission
   rules, то есть по умолчанию спрашивают.

Если профиль недоступен (сломанное окружение, отсутствующий модуль), хук
работает как раньше: запреты действуют, разрешения не выдаются. Отказ выдать
разрешение безопасен, ошибочное разрешение — нет.
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


def decide(command: str) -> tuple[str, str]:
    """`(решение, причина)`. Решение `pass` означает «хук не высказывается»."""
    verdict = rules.evaluate_bash(command)
    if verdict.decision == rules.DENY:
        return "deny", f"[factory-guard {verdict.rule_id}] {verdict.reason}"
    if unattended is not None:
        profile = unattended.evaluate(command, REPO_ROOT)
        if profile.decision == unattended.ALLOW:
            return "allow", f"[{unattended.PROFILE}] {profile.reason}"
    return "pass", ""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        # Не разбираем ввод — не высказываемся, обычные permission rules продолжают действовать.
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    decision, reason = decide(command)
    if decision != "pass":
        _emit(decision, reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
