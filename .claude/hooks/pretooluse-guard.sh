#!/bin/bash
# PreToolUse guard: decides allow / ask / deny for every tool call.
#
# It delegates to seo_operator.guardrails so that the shell hook and the Python
# pipeline enforce exactly the same rules. Duplicating the rule list here would
# guarantee the two drift apart.
#
# Input  (stdin): the PreToolUse hook payload as JSON.
# Output (stdout): {"hookSpecificOutput": {"permissionDecision": "allow|ask|deny", ...}}
set -uo pipefail

cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}"

PY=".venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"

INPUT="$(cat)"

DECISION="$("$PY" -m seo_operator.hookguard <<<"$INPUT" 2>/dev/null)"
STATUS=$?

if [ $STATUS -ne 0 ] || [ -z "$DECISION" ]; then
  # Fail closed: if the guard itself cannot run, ask rather than allow.
  cat <<'FALLBACK'
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"guard недоступен — решение передано человеку (fail closed)"}}
FALLBACK
  exit 0
fi

echo "$DECISION"
exit 0
